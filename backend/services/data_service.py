import tempfile
from pathlib import Path
from typing import Any

from src.user_data_validator import validate_user_csv
from backend.services.user_analysis_service import store_upload


def validate_upload(contents: bytes, filename: str, user_id: str) -> dict[str, Any]:
    """Validate an upload through the existing Module 2 validator."""
    if not filename.lower().endswith(".csv"):
        return {"valid": False, "records": 0, "warnings": [], "errors": ["File is not a CSV."]}
    with tempfile.NamedTemporaryFile(suffix=".csv", delete=False) as handle:
        path = Path(handle.name)
        handle.write(contents)
    try:
        result = validate_user_csv(path)
    finally:
        path.unlink(missing_ok=True)
    result["valid"] = result.get("status") in {"VALID", "VALID_WITH_WARNINGS"}
    if result["valid"]:
        result["upload_id"] = store_upload(contents, filename, user_id, result)
    result["interval"] = result.pop("detected_interval", None)
    result.pop("status", None)
    return result
