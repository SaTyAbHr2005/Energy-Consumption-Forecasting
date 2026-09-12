import sys
from pathlib import Path
from unittest.mock import patch

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from backend.services.user_analysis_service import (
    generate_forecast,
    smart_grid_analysis,
    store_upload,
)


def _upload(level: float, hours: int = 200) -> str:
    frame = pd.DataFrame(
        {
            "timestamp": pd.date_range("2026-01-01", periods=hours, freq="h"),
            "energy_consumption": [level + (index % 24) * 0.02 for index in range(hours)],
        }
    )
    with patch("backend.services.auth_service.supabase_admin"):
        return store_upload(frame.to_csv(index=False).encode("utf-8"), "fixture.csv", "test_user", {})

def test_user_forecast_requires_model_history():
    upload_id = _upload(0.8, hours=24)
    with patch("backend.services.auth_service.supabase_admin.table") as mock_table:
        mock_table.return_value.select.return_value.eq.return_value.execute.return_value.data = [{"user_id": "test_user"}]
        result = generate_forecast(upload_id, 1, "test_user")
    assert result["status"] == "insufficient_history"
    assert result["required_hours"] == 169

def test_user_profiles_produce_user_specific_forecasts_and_insights():
    with patch("backend.services.auth_service.supabase_admin.table") as mock_table:
        mock_table.return_value.select.return_value.eq.return_value.execute.return_value.data = [{"user_id": "test_user"}]
        low = generate_forecast(_upload(0.3), 1, "test_user")
        high = generate_forecast(_upload(2.0), 1, "test_user")
    
    assert low["source"] == "user_upload"
    assert low["forecast"][0]["predicted_consumption"] != high["forecast"][0]["predicted_consumption"]

    analysis = smart_grid_analysis(high)
    assert analysis["source"] == "user_upload"
    assert analysis["smart_grid"]["threshold_type"] == "User Dataset Threshold"
