import json
from pathlib import Path
from typing import Any

import pandas as pd

from backend.config import ANALYTICS, METRICS, PREDICTIONS


def _json(name: str) -> dict[str, Any]:
    path = METRICS / name
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def summary() -> dict[str, Any]:
    return _json("smart_grid_summary.json")


def insights() -> dict[str, Any]:
    return _json("energy_insights.json")


def tou() -> dict[str, Any]:
    return _json("tou_summary.json")


def _records(path: Path, limit: int = 5000) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    frame = pd.read_csv(path).head(limit).copy()
    for column in frame.select_dtypes(include=["datetime64[ns]"]).columns:
        frame[column] = frame[column].dt.isoformat()
    return frame.where(pd.notna(frame), None).to_dict(orient="records")


def peaks() -> list[dict[str, Any]]:
    return _records(METRICS / "peak_demand_forecast.csv")


def load_shifting() -> list[dict[str, Any]]:
    return _records(METRICS / "load_shift_recommendations.csv")


def sensitivity() -> list[dict[str, Any]]:
    return _records(METRICS / "load_shift_sensitivity.csv")


def recommendations() -> list[dict[str, Any]]:
    return summary().get("recommendations", [])


def hourly() -> list[dict[str, Any]]:
    return _records(ANALYTICS / "hourly_profile.csv", 24)


def daily() -> list[dict[str, Any]]:
    return _records(ANALYTICS / "daily_consumption.csv")


def weekday() -> list[dict[str, Any]]:
    return _records(ANALYTICS / "weekday_profile.csv", 7)


def forecast(horizon: int) -> list[dict[str, Any]]:
    path = PREDICTIONS / "xgboost_predictions.parquet"
    if not path.exists():
        return []
    frame = pd.read_parquet(path)
    frame = frame[frame["horizon"] == horizon][["timestamp", "predicted"]].copy()
    frame["timestamp"] = pd.to_datetime(frame["timestamp"]).map(lambda value: value.isoformat())
    return frame.rename(columns={"predicted": "predicted_consumption"}).to_dict(orient="records")

