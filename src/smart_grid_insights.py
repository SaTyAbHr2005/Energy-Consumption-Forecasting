"""Forecast-based smart-grid insights and decision-support calculations.

This module deliberately separates measured historical consumption, model
predictions, and illustrative tariff/load-shifting scenarios.  It does not
control appliances or connect to a live meter.
"""

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable, Optional
import json

import numpy as np
import pandas as pd


@dataclass(frozen=True)
class TOUConfig:
    """Illustrative tariff used only for simulation (INR/kWh)."""

    off_peak_rate: float = 3.0
    normal_rate: float = 6.0
    peak_rate: float = 10.0
    peak_start: int = 17
    peak_end: int = 22

    def __post_init__(self) -> None:
        for value in (self.off_peak_rate, self.normal_rate, self.peak_rate):
            if value < 0:
                raise ValueError("Tariff rates must be non-negative")
        if not 0 <= self.peak_start < 24 or not 0 <= self.peak_end <= 24:
            raise ValueError("Tariff hours must be between 0 and 24")


def _empty_frame(columns: Iterable[str]) -> pd.DataFrame:
    return pd.DataFrame(columns=list(columns))


def validate_prediction_data(data: pd.DataFrame) -> pd.DataFrame:
    """Normalize prediction columns and reject invalid energy/timestamp data."""
    required = {"timestamp", "predicted"}
    missing = required - set(data.columns)
    if missing:
        raise ValueError(f"Prediction data is missing required columns: {sorted(missing)}")
    out = data.copy()
    out["timestamp"] = pd.to_datetime(out["timestamp"], errors="raise")
    out["predicted"] = pd.to_numeric(out["predicted"], errors="raise")
    if out["predicted"].isna().any() or (out["predicted"] < 0).any():
        raise ValueError("Predicted consumption must be finite and non-negative")
    return out.sort_values("timestamp").reset_index(drop=True)


def detect_peaks(predicted: pd.Series, threshold: float) -> pd.Series:
    """Return high-demand flags using the project's inclusive threshold rule."""
    if threshold < 0:
        raise ValueError("Peak threshold must be non-negative")
    return predicted >= threshold


def classify_demand(
    values: pd.Series, high_threshold: float, critical_threshold: Optional[float] = None
) -> pd.Series:
    """Classify demand as Normal, High, or Critical.

    Critical defaults to the 99th percentile of the supplied values, while
    remaining strictly above the high threshold.  Callers should prefer a
    persisted project threshold when one exists.
    """
    if critical_threshold is None:
        critical_threshold = max(float(values.quantile(0.99)), high_threshold)
    if critical_threshold < high_threshold:
        raise ValueError("Critical threshold must be at least the high threshold")
    return pd.Series(
        np.select(
            [values >= critical_threshold, values >= high_threshold],
            ["Critical", "High"],
            default="Normal",
        ),
        index=values.index,
        dtype="object",
    )


def build_peak_demand_forecast(
    predictions: pd.DataFrame,
    threshold: float,
    critical_threshold: Optional[float] = None,
) -> pd.DataFrame:
    """Build the dashboard-ready peak forecast table."""
    data = validate_prediction_data(predictions)
    result = pd.DataFrame(
        {
            "timestamp": data["timestamp"],
            "predicted_consumption": data["predicted"],
            "threshold": float(threshold),
        }
    )
    result["is_peak"] = detect_peaks(result["predicted_consumption"], threshold)
    result["demand_level"] = classify_demand(
        result["predicted_consumption"], threshold, critical_threshold
    )
    return result[
        ["timestamp", "predicted_consumption", "demand_level", "is_peak", "threshold"]
    ]


def energy_insights(
    historical: pd.DataFrame, peak_threshold: float, top_n: int = 5
) -> dict[str, Any]:
    """Calculate deterministic household statistics from measured history."""
    if historical.empty:
        return {
            "record_count": 0,
            "average_hourly_consumption": None,
            "maximum_hourly_consumption": None,
            "minimum_hourly_consumption": None,
            "average_daily_consumption": None,
            "weekday_average": None,
            "weekend_average": None,
            "highest_consumption_hour": None,
            "lowest_consumption_hour": None,
            "peak_demand_frequency": 0.0,
            "top_5_highest_consumption_hours": [],
            "top_5_lowest_consumption_hours": [],
        }
    if "timestamp" not in historical or "energy_kwh" not in historical:
        raise ValueError("Historical data must contain timestamp and energy_kwh")
    data = historical[["timestamp", "energy_kwh"]].copy()
    data["timestamp"] = pd.to_datetime(data["timestamp"], errors="raise")
    data["energy_kwh"] = pd.to_numeric(data["energy_kwh"], errors="raise")
    data = data.dropna().sort_values("timestamp")
    data["hour"] = data["timestamp"].dt.hour
    data["date"] = data["timestamp"].dt.date
    data["is_weekend"] = data["timestamp"].dt.dayofweek >= 5
    hourly = data.groupby("hour")["energy_kwh"].mean()
    daily = data.groupby("date")["energy_kwh"].sum()
    top = data.nlargest(top_n, "energy_kwh")[["timestamp", "energy_kwh"]]
    bottom = data.nsmallest(top_n, "energy_kwh")[["timestamp", "energy_kwh"]]
    return {
        "record_count": int(len(data)),
        "average_hourly_consumption": float(data["energy_kwh"].mean()),
        "maximum_hourly_consumption": float(data["energy_kwh"].max()),
        "minimum_hourly_consumption": float(data["energy_kwh"].min()),
        "average_daily_consumption": float(daily.mean()),
        "weekday_average": float(data.loc[~data["is_weekend"], "energy_kwh"].mean()),
        "weekend_average": float(data.loc[data["is_weekend"], "energy_kwh"].mean()),
        "highest_consumption_hour": int(hourly.idxmax()),
        "lowest_consumption_hour": int(hourly.idxmin()),
        "peak_demand_frequency": float((data["energy_kwh"] >= peak_threshold).mean()),
        "top_5_highest_consumption_hours": [
            {"timestamp": row.timestamp.isoformat(), "energy_kwh": float(row.energy_kwh)}
            for row in top.itertuples(index=False)
        ],
        "top_5_lowest_consumption_hours": [
            {"timestamp": row.timestamp.isoformat(), "energy_kwh": float(row.energy_kwh)}
            for row in bottom.itertuples(index=False)
        ],
    }


def tou_period(hour: int, config: TOUConfig = TOUConfig()) -> str:
    """Return the configured illustrative TOU period for an hour."""
    if hour >= config.peak_start and hour < config.peak_end:
        return "peak"
    if hour < 6 or hour >= 22:
        return "off_peak"
    return "normal"


def tou_rate(hour: int, config: TOUConfig = TOUConfig()) -> float:
    return {
        "off_peak": config.off_peak_rate,
        "normal": config.normal_rate,
        "peak": config.peak_rate,
    }[tou_period(hour, config)]


def calculate_tou_cost(
    consumption: pd.DataFrame, config: TOUConfig = TOUConfig(), value_column: str = "consumption_kwh"
) -> pd.DataFrame:
    """Calculate hourly simulated TOU cost and retain the source schedule."""
    if consumption.empty:
        return _empty_frame(
            ["timestamp", value_column, "tou_period", "rate_inr_per_kwh", "simulated_cost_inr"]
        )
    if "timestamp" not in consumption or value_column not in consumption:
        raise ValueError(f"Consumption must contain timestamp and {value_column}")
    out = consumption[["timestamp", value_column]].copy()
    out["timestamp"] = pd.to_datetime(out["timestamp"], errors="raise")
    out[value_column] = pd.to_numeric(out[value_column], errors="raise")
    if (out[value_column] < 0).any():
        raise ValueError("Consumption must be non-negative")
    out["tou_period"] = out["timestamp"].dt.hour.map(lambda h: tou_period(int(h), config))
    out["rate_inr_per_kwh"] = out["timestamp"].dt.hour.map(lambda h: tou_rate(int(h), config))
    out["simulated_cost_inr"] = out[value_column] * out["rate_inr_per_kwh"]
    return out


def tou_summary(costs: pd.DataFrame, value_column: str = "consumption_kwh") -> dict[str, float]:
    """Summarize energy and simulated cost by TOU period."""
    result: dict[str, float] = {}
    for period in ("off_peak", "normal", "peak"):
        rows = costs[costs["tou_period"] == period]
        result[f"{period}_energy_kwh"] = float(rows[value_column].sum())
        result[f"{period}_cost_inr"] = float(rows["simulated_cost_inr"].sum())
    result["total_energy_kwh"] = float(costs[value_column].sum())
    result["total_simulated_cost_inr"] = float(costs["simulated_cost_inr"].sum())
    return result


def recommend_load_shifts(
    forecast: pd.DataFrame,
    peak_threshold: float,
    shiftable_fraction: float = 0.20,
    config: TOUConfig = TOUConfig(),
) -> pd.DataFrame:
    """Pair high-demand source hours with cheaper, non-peak destination hours."""
    if not 0 <= shiftable_fraction <= 1:
        raise ValueError("shiftable_fraction must be between 0 and 1")
    data = validate_prediction_data(forecast)
    columns = [
        "source_timestamp", "source_predicted_kwh", "destination_timestamp",
        "destination_predicted_kwh", "peak_threshold", "shiftable_energy_kwh",
        "peak_rate", "destination_rate", "estimated_cost_before",
        "estimated_cost_after", "estimated_savings",
    ]
    if data.empty:
        return _empty_frame(columns)
    data["period"] = data["timestamp"].dt.hour.map(lambda h: tou_period(int(h), config))
    peaks = data[data["predicted"] >= peak_threshold].sort_values("predicted", ascending=False)
    destinations = data[
        (data["predicted"] < peak_threshold)
        & (data["period"] != "peak")
    ].sort_values(["rate", "predicted"] if "rate" in data else ["predicted"])
    # Prefer destinations with a lower simulated rate and lower demand.
    destinations = destinations.assign(rate=destinations["timestamp"].dt.hour.map(lambda h: tou_rate(int(h), config)))
    destinations = destinations.sort_values(["rate", "predicted"])
    used: set[pd.Timestamp] = set()
    rows = []
    for source in peaks.itertuples(index=False):
        excess = max(float(source.predicted) - peak_threshold, 0.0)
        amount = min(float(source.predicted) * shiftable_fraction, excess)
        if amount <= 0:
            continue
        candidates = destinations[
            (~destinations["timestamp"].isin(used))
            & (destinations["timestamp"] != source.timestamp)
            & (destinations["rate"] < tou_rate(int(source.timestamp.hour), config))
        ]
        if candidates.empty:
            continue
        destination = candidates.iloc[0]
        # A destination receives at most its own conservative flexible share.
        amount = min(amount, float(destination["predicted"]) * shiftable_fraction)
        if amount <= 0:
            continue
        before = amount * tou_rate(int(source.timestamp.hour), config)
        after = amount * float(destination["rate"])
        savings = before - after
        if savings <= 0:
            continue
        used.add(destination["timestamp"])
        rows.append(
            {
                "source_timestamp": source.timestamp,
                "source_predicted_kwh": float(source.predicted),
                "destination_timestamp": destination["timestamp"],
                "destination_predicted_kwh": float(destination["predicted"]),
                "peak_threshold": float(peak_threshold),
                "shiftable_energy_kwh": float(amount),
                "peak_rate": float(tou_rate(int(source.timestamp.hour), config)),
                "destination_rate": float(destination["rate"]),
                "estimated_cost_before": float(before),
                "estimated_cost_after": float(after),
                "estimated_savings": float(savings),
            }
        )
    return pd.DataFrame(rows, columns=columns)


def daily_savings_analysis(
    baseline: pd.DataFrame, shifts: pd.DataFrame, config: TOUConfig = TOUConfig()
) -> pd.DataFrame:
    """Calculate baseline and potential optimized simulated cost by day."""
    base = calculate_tou_cost(baseline, config)
    if base.empty:
        return _empty_frame(
            ["date", "baseline_cost", "optimized_simulated_cost", "estimated_savings",
             "savings_percentage", "energy_shifted"]
        )
    result = base.assign(date=base["timestamp"].dt.date).groupby("date", as_index=False).agg(
        baseline_cost=("simulated_cost_inr", "sum")
    )
    if shifts.empty:
        result["estimated_savings"] = 0.0
        result["energy_shifted"] = 0.0
    else:
        savings = shifts.assign(date=shifts["source_timestamp"].dt.date).groupby("date").agg(
            estimated_savings=("estimated_savings", "sum"),
            energy_shifted=("shiftable_energy_kwh", "sum"),
        )
        result = result.join(savings, on="date").fillna(0.0)
    result["optimized_simulated_cost"] = result["baseline_cost"] - result["estimated_savings"]
    result["savings_percentage"] = np.where(
        result["baseline_cost"] > 0,
        result["estimated_savings"] / result["baseline_cost"] * 100,
        0.0,
    )
    return result[
        ["date", "baseline_cost", "optimized_simulated_cost", "estimated_savings",
         "savings_percentage", "energy_shifted"]
    ]


def generate_recommendations(
    historical: pd.DataFrame,
    forecast_table: pd.DataFrame,
    insights: dict[str, Any],
    peak_threshold: float,
) -> list[dict[str, str]]:
    """Generate rules backed by calculated historical/forecast metrics."""
    recommendations: list[dict[str, str]] = []
    if forecast_table.empty:
        return recommendations
    evening = forecast_table[
        forecast_table["timestamp"].dt.hour.isin([17, 18, 19, 20, 21])
    ]
    if not evening.empty and float(evening["predicted_consumption"].mean()) >= peak_threshold:
        recommendations.append({
            "recommendation": "Shift flexible loads away from the evening peak.",
            "reason": "Forecasted evening demand meets or exceeds the high-demand threshold.",
            "priority": "High",
            "supporting_metric": f"Mean predicted evening demand = {evening['predicted_consumption'].mean():.2f} kWh",
        })
    if insights.get("weekend_average") is not None and insights.get("weekday_average") is not None:
        if insights["weekend_average"] > insights["weekday_average"] * 1.10:
            recommendations.append({
                "recommendation": "Review appliance usage during high-consumption weekend periods.",
                "reason": "Measured weekend consumption is materially higher than weekday consumption.",
                "priority": "Medium",
                "supporting_metric": f"Weekend average = {insights['weekend_average']:.2f} vs weekday = {insights['weekday_average']:.2f} kWh/hour",
            })
    if int(forecast_table["is_peak"].sum()) >= 2:
        recommendations.append({
            "recommendation": "Consider shifting flexible loads away from repeated high-demand periods.",
            "reason": "Multiple predicted periods exceed the high-demand threshold.",
            "priority": "Medium",
            "supporting_metric": f"Predicted peak periods = {int(forecast_table['is_peak'].sum())}",
        })
    if "timestamp" in historical and "energy_kwh" in historical and not historical.empty:
        h = historical.assign(hour=pd.to_datetime(historical["timestamp"]).dt.hour)
        overnight = float(h.loc[h["hour"].isin([0, 1, 2, 3, 4, 5]), "energy_kwh"].mean())
        overall = float(h["energy_kwh"].mean())
        if overall and overnight > overall * 1.15:
            recommendations.append({
                "recommendation": "Review always-on loads during overnight hours.",
                "reason": "Measured overnight consumption is unusually high relative to the household average.",
                "priority": "Low",
                "supporting_metric": f"Overnight average = {overnight:.2f} vs overall = {overall:.2f} kWh/hour",
            })
    return recommendations


def json_dump(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        json.dump(value, handle, indent=2, default=str)
