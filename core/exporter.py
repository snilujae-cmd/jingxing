"""同一次仿真导出四个CSV；约定共用 run_id，time_min 为仿真分钟。

三份现有User端CSV的原始样例未包含在本次Admin压缩包中，因此请在合并User
时核对真实表头；本文件不擅自覆盖/修改用户先前交付的数据文件。
"""
import csv
import io
from pathlib import Path
import zipfile

SCHEMAS = {
    "od_flow.csv": ["run_id", "window_start_min", "route_id", "origin_station_id",
                    "origin_route_station_seq", "destination_station_id",
                    "destination_route_station_seq", "passengers"],
    "station_state.csv": ["run_id", "time_min", "station_id", "route_station_seq",
                          "route_id", "direction", "queue_length", "oldest_wait_min"],
    "vehicle_state.csv": ["run_id", "time_min", "vehicle_id", "route_id",
                          "station_id", "route_station_seq", "direction", "status", "load", "capacity"],
    "passenger_results.csv": ["run_id", "passenger_id", "route_id", "origin_station_id",
                              "origin_route_station_seq", "destination_station_id",
                              "destination_route_station_seq", "direction", "arrival_time_min",
                              "board_time_min", "alight_time_min", "wait_min", "status"],
}

def csv_content(result, name):
    if name not in SCHEMAS:
        raise ValueError(f"未知CSV输出名称: {name}")
    rows = result[name.removesuffix(".csv")]
    buffer = io.StringIO(newline="")
    writer = csv.DictWriter(buffer, fieldnames=SCHEMAS[name], extrasaction="ignore")
    writer.writeheader()
    writer.writerows(rows)
    return buffer.getvalue().encode("utf-8-sig")


def zip_content(result):
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as z:
        for name in SCHEMAS:
            z.writestr(name, csv_content(result, name))
    return buffer.getvalue()


def write_exports(result, folder):
    path = Path(folder)
    path.mkdir(parents=True, exist_ok=True)
    for name in SCHEMAS:
        (path / name).write_bytes(csv_content(result, name))
    return path
