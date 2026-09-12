import pandas as pd
import pytest
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.smart_grid_insights import (
    TOUConfig, build_peak_demand_forecast, calculate_tou_cost, classify_demand,
    detect_peaks, recommend_load_shifts, tou_rate,
)


def frame(values, start="2024-01-01"):
    return pd.DataFrame({
        "timestamp": pd.date_range(start, periods=len(values), freq="h"),
        "predicted": values,
    })


def test_peak_detection_and_severity():
    values = pd.Series([1.0, 2.0, 3.0])
    assert detect_peaks(values, 2.0).tolist() == [False, True, True]
    assert classify_demand(values, 2.0, 3.0).tolist() == ["Normal", "High", "Critical"]


def test_tou_rates_and_cost():
    config = TOUConfig(off_peak_rate=1, normal_rate=2, peak_rate=4)
    assert tou_rate(2, config) == 1
    assert tou_rate(12, config) == 2
    assert tou_rate(18, config) == 4
    costs = calculate_tou_cost(pd.DataFrame({
        "timestamp": pd.to_datetime(["2024-01-01 02:00", "2024-01-01 18:00"]),
        "consumption_kwh": [2.0, 3.0],
    }), config)
    assert costs["simulated_cost_inr"].tolist() == [2.0, 12.0]


def test_load_shift_is_capped_and_avoids_peaks():
    data = frame([1.0, 4.0, 1.0, 1.2], start="2024-01-01 16:00")
    shifts = recommend_load_shifts(data, 2.0, shiftable_fraction=.20)
    assert len(shifts) == 1
    assert shifts.iloc[0]["shiftable_energy_kwh"] <= 4.0 * .20
    assert shifts.iloc[0]["destination_predicted_kwh"] < 2.0
    assert shifts.iloc[0]["estimated_savings"] == pytest.approx(
        shifts.iloc[0]["estimated_cost_before"] - shifts.iloc[0]["estimated_cost_after"]
    )


def test_no_negative_savings_and_empty_data():
    assert recommend_load_shifts(frame([]), 2.0).empty
    with pytest.raises(ValueError):
        recommend_load_shifts(frame([3.0]), 2.0, 1.1)


def test_configurable_fraction_and_peak_table():
    result = build_peak_demand_forecast(frame([1.0, 2.1]), 2.0, 3.0)
    assert result["is_peak"].tolist() == [False, True]
    assert result["demand_level"].tolist() == ["Normal", "High"]
