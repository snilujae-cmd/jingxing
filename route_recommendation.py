"""Compare direct routes using completed records from one simulation run.

The times returned here describe a *playback* of simulated passenger records.
They are not a vehicle arrival forecast, a seat guarantee, or live operations data.
"""

from __future__ import annotations

from math import isfinite

import numpy as np
import pandas as pd

from user_data_adapter import RunData


def _direction(value: object) -> str | None:
    """Normalize the direction encodings used by Admin and legacy User CSVs."""
    label = str(value).strip()
    if label in {"1", "1.0", "去程", "OUT", "out"}:
        return "去程"
    if label in {"-1", "-1.0", "返程", "IN", "in"}:
        return "返程"
    return None


def _candidate_routes(
    stop_order: pd.DataFrame, origin_station_id: str, destination_station_id: str
) -> list[tuple[str, str]]:
    required = {"route_id", "station_id", "stop_sequence"}
    missing = required - set(stop_order.columns)
    if missing:
        raise ValueError(f"route_stop_order 缺少字段：{', '.join(sorted(missing))}")

    candidates: list[tuple[str, str]] = []
    for route_id, group in stop_order.groupby("route_id", sort=True):
        group = group.copy()
        group["stop_sequence"] = pd.to_numeric(group["stop_sequence"], errors="coerce")
        if group["stop_sequence"].isna().any() or group["stop_sequence"].duplicated().any():
            continue  # An ambiguous order cannot support a direction claim.
        stations = group.sort_values("stop_sequence")["station_id"].astype(str).tolist()
        if stations.count(origin_station_id) != 1 or stations.count(destination_station_id) != 1:
            continue
        start, end = stations.index(origin_station_id), stations.index(destination_station_id)
        if start != end:
            candidates.append((str(route_id), "去程" if start < end else "返程"))
    return candidates


def recommend_direct_routes(
    stop_order: pd.DataFrame,
    run: RunData,
    origin_station_id: str,
    destination_station_id: str,
    replay_time_min: float,
) -> list[dict]:
    """Return all direct routes, with observed playback times where available.

    Each route uses its earliest *complete* exact-OD passenger record whose
    boarding occurs strictly after ``replay_time_min``. If no such record exists,
    every numeric field is ``None``. Completed options are sorted by the total
    interval from replay time to that passenger's alighting, then options
    without observations follow. A shorter observed interval is not a claim
    that this route would be faster for a new passenger.
    """
    try:
        replay_time_min = float(replay_time_min)
    except (TypeError, ValueError) as exc:
        raise ValueError("回放时刻必须是有限数字") from exc
    if not isfinite(replay_time_min):
        raise ValueError("回放时刻必须是有限数字")

    if origin_station_id == destination_station_id:
        return []
    candidates = _candidate_routes(stop_order, origin_station_id, destination_station_id)
    if not candidates:
        return []

    people = run.passenger_results
    required = {"route_id", "origin_station_id", "destination_station_id",
                "direction", "boarding_time_min", "alighting_time_min"}
    missing = required - set(people.columns)
    if missing:
        raise ValueError(f"passenger_results 缺少精确 OD 比较所需字段：{', '.join(sorted(missing))}")

    records = people.loc[
        people["origin_station_id"].astype(str).eq(origin_station_id)
        & people["destination_station_id"].astype(str).eq(destination_station_id)
    ].copy()
    records["boarding_time_min"] = pd.to_numeric(
        records["boarding_time_min"], errors="coerce"
    ).astype(float)
    records["alighting_time_min"] = pd.to_numeric(
        records["alighting_time_min"], errors="coerce"
    ).astype(float)
    records = records.loc[
        np.isfinite(records["boarding_time_min"])
        & np.isfinite(records["alighting_time_min"])
        & records["boarding_time_min"].gt(replay_time_min)
        & records["alighting_time_min"].gt(records["boarding_time_min"])
    ].copy()
    records["normalized_direction"] = records["direction"].map(_direction)

    options: list[dict] = []
    for route_id, direction in candidates:
        matches = records.loc[
            records["route_id"].astype(str).eq(route_id)
            & records["normalized_direction"].eq(direction)
        ].sort_values(["boarding_time_min", "alighting_time_min"], kind="stable")
        option = {
            "route_id": route_id,
            "direction": direction,
            "boarding_time_min": None,
            "alighting_time_min": None,
            "replay_wait_min": None,
            "ride_time_min": None,
            "total_replay_min": None,
            "observed_passenger_id": None,
        }
        if not matches.empty:
            row = matches.iloc[0]
            board = float(row["boarding_time_min"])
            alight = float(row["alighting_time_min"])
            option.update({
                "boarding_time_min": board,
                "alighting_time_min": alight,
                "replay_wait_min": board - replay_time_min,
                "ride_time_min": alight - board,
                "total_replay_min": alight - replay_time_min,
                "observed_passenger_id": (
                    str(row["passenger_id"])
                    if "passenger_id" in row and pd.notna(row["passenger_id"]) else None
                ),
            })
        options.append(option)

    return sorted(options, key=lambda option: (
        option["total_replay_min"] is None,
        option["total_replay_min"] if option["total_replay_min"] is not None else float("inf"),
        option["route_id"],
    ))
