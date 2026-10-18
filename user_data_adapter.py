"""景行智调 User 数据适配器。

支持 User 原有的 2026-10-16 CSV 和 Admin V1 输出的 2026-10-17 CSV。
仅转换已有数据/计算历史累计量；绝不伪造车辆路段进度或实时到站预测。
"""
from __future__ import annotations

from dataclasses import dataclass
from io import BytesIO
from pathlib import Path
from typing import Mapping
from zipfile import BadZipFile, ZipFile

import numpy as np
import pandas as pd

CSV_NAMES = ("od_flow.csv", "station_state.csv", "vehicle_state.csv", "passenger_results.csv")
MAX_ZIP_BYTES = 25 * 1024 * 1024
MAX_CSV_BYTES = 12 * 1024 * 1024


class DataContractError(ValueError):
    """缺少字段、不同仿真混用或其他接口错误。"""


@dataclass
class RunData:
    run_id: str
    od_flow: pd.DataFrame
    station_state: pd.DataFrame
    vehicle_state: pd.DataFrame
    passenger_results: pd.DataFrame
    schema_kind: str
    source_label: str


def load_run_folder(folder: str | Path, stations: pd.DataFrame) -> RunData:
    folder = Path(folder)
    tables = {}
    for name in CSV_NAMES:
        filename = folder / name
        if not filename.is_file():
            raise DataContractError(f"缺少文件：{filename}")
        tables[name] = pd.read_csv(filename, encoding="utf-8-sig")
    return normalize_tables(tables, stations, f"文件夹：{folder.name}")


def load_run_zip(data: bytes, stations: pd.DataFrame) -> RunData:
    if len(data) > MAX_ZIP_BYTES:
        raise DataContractError("压缩包大于25MB，请先精简后导入。")
    try:
        with ZipFile(BytesIO(data)) as z:
            tables = {}
            for name in CSV_NAMES:
                members = [i for i in z.infolist() if not i.is_dir() and Path(i.filename).name == name]
                if len(members) != 1:
                    raise DataContractError(f"压缩包内要求恰好一份 {name}，实际找到 {len(members)} 份")
                if members[0].file_size > MAX_CSV_BYTES:
                    raise DataContractError(f"{name} 超过12MB文件大小限制。")
                tables[name] = pd.read_csv(BytesIO(z.read(members[0])), encoding="utf-8-sig")
    except BadZipFile as exc:
        raise DataContractError("不是有效的ZIP压缩包。") from exc
    return normalize_tables(tables, stations, "上传的Admin结果ZIP")


def load_admin_result(result: Mapping, stations: pd.DataFrame) -> RunData:
    """同一 Streamlit 网站可直接读取 Admin session_state['last_result']。"""
    try:
        tables = {name: pd.DataFrame(result[name.removesuffix(".csv")]) for name in CSV_NAMES}
    except KeyError as exc:
        raise DataContractError(f"Admin内存结果缺少 {exc.args[0]}") from exc
    return normalize_tables(tables, stations, "当前浏览器的Admin最新仿真")


def _require(df: pd.DataFrame, columns: set[str], name: str) -> None:
    missing = columns - set(df.columns)
    if missing:
        raise DataContractError(f"{name} 缺少字段：{', '.join(sorted(missing))}")


def normalize_tables(tables: Mapping[str, pd.DataFrame], stations: pd.DataFrame, source: str) -> RunData:
    """将两套CSV统一为User内部使用的稳定表结构。"""
    for name in CSV_NAMES:
        if name not in tables:
            raise DataContractError(f"缺少 {name}")
        _require(tables[name], {"run_id"}, name)

    ids: set[str] = set()
    for name in CSV_NAMES:
        values = tables[name]["run_id"].dropna().astype(str).unique().tolist()
        if len(values) != 1:
            raise DataContractError(f"{name} 必须恰好对应一个run_id（目前{len(values)}个）")
        ids.add(values[0])
    if len(ids) != 1:
        raise DataContractError("4份CSV的run_id不同，不能混合读取！")
    run_id = next(iter(ids))

    od = tables["od_flow.csv"].copy()
    station = tables["station_state.csv"].copy()
    vehicle = tables["vehicle_state.csv"].copy()
    passenger = tables["passenger_results.csv"].copy()
    _require(od, {"route_id", "origin_station_id", "destination_station_id", "window_start_min"}, "od_flow.csv")
    _require(station, {"time_min", "route_id", "station_id", "route_station_seq"}, "station_state.csv")
    _require(vehicle, {"time_min", "route_id", "vehicle_id", "station_id", "capacity", "status"}, "vehicle_state.csv")
    _require(passenger, {"route_id", "origin_station_id", "arrival_time_min"}, "passenger_results.csv")

    if "passengers" in od.columns:
        od = od.rename(columns={"passengers": "demand_count"})
    _require(od, {"demand_count"}, "od_flow.csv")

    passenger = passenger.rename(columns={
        "board_time_min": "boarding_time_min", "alight_time_min": "alighting_time_min",
        "wait_min": "wait_time_min"})
    for c in ("boarding_time_min", "alighting_time_min", "wait_time_min", "vehicle_id"):
        if c not in passenger.columns:
            passenger[c] = np.nan

    station_names = (stations.drop_duplicates("station_id")
                     .set_index("station_id")["station_name"].to_dict())

    if {"direction", "queue_length"}.issubset(station.columns):
        # Admin格式：同一个站点/时刻分去程和返程两行，转成 User 使用的一行。
        grouping = ["run_id", "time_min", "route_id", "station_id", "route_station_seq"]
        station["direction"] = pd.to_numeric(station["direction"], errors="coerce")
        station["queue_length"] = pd.to_numeric(station["queue_length"], errors="raise")
        if station["direction"].isna().any() or not station["direction"].isin([1, -1]).all():
            raise DataContractError("Admin站点direction必须是1或-1。")
        if (station["queue_length"] < 0).any():
            raise DataContractError("站点排队人数不能为负。")
        station["waiting_forward"] = np.where(station["direction"] == 1, station["queue_length"], 0)
        station["waiting_reverse"] = np.where(station["direction"] == -1, station["queue_length"], 0)
        station = (station.groupby(grouping, as_index=False)[["waiting_forward", "waiting_reverse"]]
                   .sum())
        station["waiting_total"] = station["waiting_forward"] + station["waiting_reverse"]
        station["station_name"] = station["station_id"].map(station_names).fillna(station["station_id"])
        # 根据逐人客流事件计算站点累计到达/上车人数，不能取各站最大值代替全景区总数。
        _require(passenger, {"origin_route_station_seq", "boarding_time_min"}, "passenger_results.csv")
        for field, time_col in [("arrivals_cumulative", "arrival_time_min"),
                                ("boarded_cumulative", "boarding_time_min")]:
            station[field] = 0
            for (route, seq), idx in station.groupby(["route_id", "route_station_seq"]).groups.items():
                person = passenger[(passenger["route_id"] == route) &
                                   (passenger["origin_route_station_seq"] == seq)]
                moments = np.sort(pd.to_numeric(person[time_col], errors="coerce").dropna().to_numpy(dtype=float))
                snaps = station.loc[idx, "time_min"].to_numpy(dtype=float)
                station.loc[idx, field] = np.searchsorted(moments, snaps + 1e-9, side="right")
        kind = "admin_v1"
    else:
        # User 旧格式原样保留（可兼容两版样例）。
        _require(station, {"station_name", "waiting_forward", "waiting_reverse", "waiting_total",
                           "arrivals_cumulative", "boarded_cumulative"}, "station_state.csv")
        kind = "user_legacy"

    if "load" in vehicle.columns:
        vehicle = vehicle.rename(columns={"load": "onboard"})
    _require(vehicle, {"onboard"}, "vehicle_state.csv")
    if kind == "admin_v1":
        numeric_direction = pd.to_numeric(vehicle["direction"], errors="coerce")
        vehicle["direction"] = numeric_direction.map({1: "去程", -1: "返程"}).fillna("待命")
        vehicle["from_station_id"] = np.nan
        vehicle["to_station_id"] = np.nan
        vehicle["segment_progress"] = np.nan
    else:
        for c in ("from_station_id", "to_station_id", "segment_progress"):
            if c not in vehicle.columns:
                vehicle[c] = np.nan
    vehicle["station_name"] = vehicle["station_id"].map(station_names).fillna(vehicle["station_id"])

    for df in (station, vehicle, passenger, od):
        for c in ("time_min", "arrival_time_min", "boarding_time_min", "alighting_time_min"):
            if c in df.columns:
                df[c] = pd.to_numeric(df[c], errors="coerce")

    if not np.isfinite(station["time_min"]).all() or not np.isfinite(vehicle["time_min"]).all():
        raise DataContractError("时刻字段包含无效数值。")
    if (vehicle["onboard"] > vehicle["capacity"]).any() or (vehicle["onboard"] < 0).any():
        raise DataContractError("车辆载客人数存在超载或负值。")

    return RunData(run_id, od, station, vehicle, passenger, kind, source)
