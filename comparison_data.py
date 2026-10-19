"""Validated, read-only summaries of one fair three-strategy comparison.

The simulator and its four CSV contracts are unchanged. This metadata contains
actual computed metrics and queue snapshots, plus the exact common inputs.
"""
from __future__ import annotations

from collections.abc import Mapping, Sequence
from datetime import datetime, timezone
import hashlib
import json
import math
from numbers import Integral, Real

import numpy as np


SCHEMA_VERSION = 1
COMPARISON_NAME = "comparison.json"
MAX_COMPARISON_BYTES = 2 * 1024 * 1024
STRATEGIES = ("fixed", "dynamic", "optimized")
STRATEGY_LABELS = {"fixed": "固定调度", "dynamic": "动态阈值调度", "optimized": "滚动预测优化"}
COUNT_METRICS = ("total_arrivals", "served", "completed", "onboard_end", "unserved", "total_departures")
VALUE_METRICS = ("avg_wait", "max_wait", "p95_wait", "over_ratio", "service_rate",
                 "avg_observed_wait_all", "total_wait_person_min", "vehicle_busy_minutes")
METRICS = COUNT_METRICS + VALUE_METRICS


class ComparisonDataError(ValueError):
    """The comparison is incomplete, inconsistent, or from a different run."""


def _json_bytes(value) -> bytes:
    try:
        return json.dumps(value, sort_keys=True, ensure_ascii=False,
                          allow_nan=False, separators=(",", ":")).encode("utf-8")
    except (TypeError, ValueError, OverflowError) as exc:
        raise ComparisonDataError("比较结果包含不可序列化或非有限数值") from exc


def _finite(value, field: str, integer=False):
    expected = Integral if integer else Real
    if isinstance(value, bool) or not isinstance(value, expected):
        raise ComparisonDataError(f"比较字段 {field} 类型无效")
    try:
        finite = math.isfinite(float(value))
    except (ValueError, OverflowError):
        finite = False
    if not finite or value < 0:
        raise ComparisonDataError(f"比较字段 {field} 必须为非负有限数值")
    return int(value) if integer else float(value)


def _text(value, field: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ComparisonDataError(f"比较字段 {field} 缺失")
    return value


def _metrics(result: Mapping) -> dict:
    try:
        values = {key: _finite(result[key], key, key in COUNT_METRICS) for key in METRICS}
    except KeyError as exc:
        raise ComparisonDataError(f"比较指标缺少 {exc.args[0]}") from exc
    total, served = values["total_arrivals"], values["served"]
    if total != served + values["unserved"] or served != values["completed"] + values["onboard_end"]:
        raise ComparisonDataError("比较指标中的乘客数量不守恒")
    expected_rate = served / total if total else 0.0
    if not math.isclose(values["service_rate"], expected_rate, abs_tol=1e-9):
        raise ComparisonDataError("比较服务率与乘客数量不一致")
    if values["over_ratio"] > 1 or values["service_rate"] > 1:
        raise ComparisonDataError("比较比例超出0到1范围")
    if values["p95_wait"] > values["max_wait"] + 1e-8 or values["avg_wait"] > values["max_wait"] + 1e-8:
        raise ComparisonDataError("比较候车指标不一致")
    if not math.isclose(values["avg_observed_wait_all"] * total,
                        values["total_wait_person_min"], rel_tol=1e-8, abs_tol=1e-6):
        raise ComparisonDataError("比较全体观测候车指标不一致")
    return values


def _queue_series(records: Sequence, run_id: str) -> list[dict]:
    totals: dict[float, int] = {}
    for row in records:
        if not isinstance(row, Mapping) or row.get("run_id") != run_id:
            raise ComparisonDataError("比较排队快照混入不同运行编号")
        try:
            moment = _finite(row["time_min"], "time_min")
            queue = _finite(row["queue_length"], "queue_length", integer=True)
        except KeyError as exc:
            raise ComparisonDataError(f"比较排队快照缺少 {exc.args[0]}") from exc
        totals[moment] = totals.get(moment, 0) + queue
    return [{"time_min": t, "waiting_total": totals[t]} for t in sorted(totals)]


def _comparison_id(metadata: Mapping) -> str:
    content = {key: value for key, value in metadata.items() if key not in {"comparison_id", "published_at"}}
    return "cmp-" + hashlib.sha256(_json_bytes(content)).hexdigest()[:16]


def build_comparison(results: Sequence[Mapping], selected_result: Mapping) -> dict:
    """Build one detached summary; reject mixed inputs before publishing."""
    if not isinstance(results, (list, tuple)) or len(results) != 3:
        raise ComparisonDataError("发布比较必须包含固定、动态和优化三种策略")
    if any(not isinstance(item, Mapping) for item in results):
        raise ComparisonDataError("比较结果格式无效")
    lookup = {item.get("strategy"): item for item in results}
    if set(lookup) != set(STRATEGIES):
        raise ComparisonDataError("比较策略重复或不完整")
    first = lookup[STRATEGIES[0]]
    try:
        params = first["params"]
        params_bytes = _json_bytes(params)
        seed = _finite(first["seed"], "seed", integer=True)
        demand_signature = _text(first["demand_signature"], "demand_signature")
        selected_id = _text(selected_result["run_id"], "selected_run_id")
        rows = []
        for strategy in STRATEGIES:
            result = lookup[strategy]
            if (_json_bytes(result["params"]) != params_bytes or result["seed"] != seed
                    or result["demand_signature"] != demand_signature):
                raise ComparisonDataError("三策略的场景参数、随机种子或客流签名不同，不能发布比较")
            run_id = _text(result["run_id"], "run_id")
            rows.append({"strategy": strategy, "run_id": run_id, "metrics": _metrics(result),
                         "queue_series": _queue_series(result["station_state"], run_id)})
        selected = next((r for r in rows if r["run_id"] == selected_id), None)
        if selected is None or selected["strategy"] != selected_result["strategy"]:
            raise ComparisonDataError("发布的单次仿真不属于本组三策略比较")
        if (_json_bytes(selected_result["params"]) != params_bytes
                or selected_result["seed"] != seed
                or selected_result["demand_signature"] != demand_signature
                or _metrics(selected_result) != selected["metrics"]
                or _queue_series(selected_result["station_state"], selected_id) != selected["queue_series"]):
            raise ComparisonDataError("发布的单次仿真与对应比较结果不一致")
    except KeyError as exc:
        raise ComparisonDataError(f"比较结果缺少 {exc.args[0]}") from exc
    metadata = {
        "schema_version": SCHEMA_VERSION,
        "published_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "selected_run_id": selected_id, "seed": seed, "demand_signature": demand_signature,
        "params": json.loads(params_bytes), "strategies": rows,
    }
    metadata["comparison_id"] = _comparison_id(metadata)
    return validate_comparison(metadata, selected_id)


def validate_comparison(metadata: Mapping, selected_run_id: str | None = None) -> dict:
    """Validate a published summary without changing or fabricating values."""
    if (not isinstance(metadata, dict) or type(metadata.get("schema_version")) is not int
            or metadata.get("schema_version") != SCHEMA_VERSION):
        raise ComparisonDataError("不支持的三策略比较格式版本")
    _json_bytes(metadata)  # Reject NaN/infinity anywhere, including common params.
    try:
        selected = _text(metadata["selected_run_id"], "selected_run_id")
        if selected_run_id is not None and selected != selected_run_id:
            raise ComparisonDataError("三策略比较与当前四份CSV的运行编号不一致")
        _text(metadata["demand_signature"], "demand_signature")
        _finite(metadata["seed"], "seed", integer=True)
        timestamp = datetime.fromisoformat(_text(metadata["published_at"], "published_at"))
        if timestamp.tzinfo is None:
            raise ComparisonDataError("比较发布时间缺少时区")
        params = metadata["params"]
        if not isinstance(params, dict) or not {"duration_min", "arrival_rate", "fleet", "scenario_type"} <= params.keys():
            raise ComparisonDataError("比较缺少完整场景参数")
        duration = _finite(params["duration_min"], "duration_min")
        rows = metadata["strategies"]
        if not isinstance(rows, list) or len(rows) != 3:
            raise ComparisonDataError("比较策略不完整")
        strategies, run_ids, arrivals, grids = set(), set(), set(), []
        for row in rows:
            if not isinstance(row, dict) or row.get("strategy") not in STRATEGIES:
                raise ComparisonDataError("比较策略名称无效")
            strategies.add(row["strategy"])
            run_ids.add(_text(row["run_id"], "run_id"))
            values = _metrics(row["metrics"])
            arrivals.add(values["total_arrivals"])
            series = row["queue_series"]
            if not isinstance(series, list) or not series:
                raise ComparisonDataError("比较缺少真实排队快照")
            times = []
            for point in series:
                if not isinstance(point, dict):
                    raise ComparisonDataError("比较排队快照格式无效")
                moment = _finite(point["time_min"], "time_min")
                _finite(point["waiting_total"], "waiting_total", integer=True)
                if moment > duration + 1e-4 or (times and moment <= times[-1]):
                    raise ComparisonDataError("比较排队快照时刻无效或重复")
                times.append(moment)
            grids.append(times)
        if strategies != set(STRATEGIES) or len(run_ids) != 3 or selected not in run_ids:
            raise ComparisonDataError("比较策略或运行编号重复、缺失")
        if len(arrivals) != 1 or any(grid != grids[0] for grid in grids[1:]):
            raise ComparisonDataError("三策略到达人数或排队快照时刻不一致")
        if _text(metadata["comparison_id"], "comparison_id") != _comparison_id(metadata):
            raise ComparisonDataError("比较内容校验失败，可能是不完整或损坏的结果")
    except (KeyError, TypeError) as exc:
        raise ComparisonDataError("比较结果字段缺失或类型无效") from exc
    except ValueError as exc:
        if isinstance(exc, ComparisonDataError):
            raise
        raise ComparisonDataError("比较发布时间格式无效") from exc
    return metadata


def encode_comparison(metadata: Mapping) -> bytes:
    validate_comparison(metadata)
    contents = _json_bytes(metadata)
    if len(contents) > MAX_COMPARISON_BYTES:
        raise ComparisonDataError("三策略比较元数据超过2MB限制")
    return contents


def decode_comparison(contents: bytes, selected_run_id: str) -> dict:
    if len(contents) > MAX_COMPARISON_BYTES:
        raise ComparisonDataError("三策略比较元数据超过2MB限制")
    try:
        metadata = json.loads(contents.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError, RecursionError) as exc:
        raise ComparisonDataError("三策略比较元数据不是有效的UTF-8 JSON") from exc
    return validate_comparison(metadata, selected_run_id)


def validate_selected_run(metadata: Mapping, run) -> None:
    """Check the selected summary against the actual published CSV records."""
    row = next(item for item in metadata["strategies"] if item["run_id"] == run.run_id)
    metrics = row["metrics"]
    people = run.passenger_results
    boarded = people["boarding_time_min"].notna()
    counts = {
        "total_arrivals": len(people), "served": int(boarded.sum()),
        "completed": int(people["alighting_time_min"].notna().sum()),
        "onboard_end": int(people["status"].eq("onboard").sum()),
        "unserved": int(people["status"].eq("waiting").sum()),
    }
    if any(metrics[key] != value for key, value in counts.items()):
        raise ComparisonDataError("三策略指标与所发布CSV的乘客记录不一致")
    arrivals = people["arrival_time_min"].to_numpy(dtype=float)
    boarding = people.loc[boarded, "boarding_time_min"].to_numpy(dtype=float)
    waits = people.loc[boarded, "wait_time_min"].to_numpy(dtype=float)
    if (not np.isfinite(arrivals).all() or not np.isfinite(boarding).all()
            or not np.isfinite(waits).all() or (waits < 0).any()
            or not np.allclose(waits, boarding - arrivals[boarded.to_numpy()], rtol=0, atol=1.6e-5)):
        raise ComparisonDataError("所发布CSV的候车与上下车时间记录不一致")
    computed = {
        "avg_wait": float(np.mean(waits)) if len(waits) else 0.0,
        "max_wait": float(np.max(waits)) if len(waits) else 0.0,
        "p95_wait": float(np.percentile(waits, 95)) if len(waits) else 0.0,
    }
    # The exporter rounds passenger timestamps/waits to five decimals. A real
    # wait just above 15 can round to 15, so bound the threshold ratio by this
    # known rounding uncertainty instead of declaring a correct archive bad.
    ratio_low = float(np.mean(waits > 15 + 6e-6)) if len(waits) else 0.0
    ratio_high = float(np.mean(waits >= 15 - 6e-6)) if len(waits) else 0.0
    if not ratio_low - 1e-12 <= metrics["over_ratio"] <= ratio_high + 1e-12:
        raise ComparisonDataError("三策略超时比例与所发布CSV的候车记录不一致")
    duration = float(metadata["params"]["duration_min"])
    observed = people["boarding_time_min"].fillna(duration).to_numpy(dtype=float) - arrivals
    computed["avg_observed_wait_all"] = float(np.mean(observed)) if len(observed) else 0.0
    for key, value in computed.items():
        if not math.isclose(metrics[key], value, rel_tol=0, abs_tol=1.1e-5):
            raise ComparisonDataError(f"三策略指标 {key} 与所发布CSV的候车记录不一致")
    if not math.isclose(metrics["total_wait_person_min"], float(np.sum(observed)),
                        rel_tol=0, abs_tol=max(1.1e-5, len(observed) * 1.1e-5)):
        raise ComparisonDataError("三策略总候车人分钟与所发布CSV的候车记录不一致")
    grouped = run.station_state.groupby("time_min")["waiting_total"].sum()
    series = [{"time_min": float(t), "waiting_total": int(n)} for t, n in grouped.items()]
    if series != row["queue_series"]:
        raise ComparisonDataError("三策略曲线与所发布CSV的站点记录不一致")
