from typing import Any, Optional

from pydantic import BaseModel


class HealthResponse(BaseModel):
    status: str
    service: str


class UploadResponse(BaseModel):
    valid: bool
    records: int
    start_timestamp: Optional[str] = None
    end_timestamp: Optional[str] = None
    interval: Optional[str] = None
    warnings: list[str] = []
    errors: list[str] = []
    forecasting_readiness: Optional[str] = None
    upload_id: Optional[str] = None


class ForecastPoint(BaseModel):
    timestamp: str
    predicted_consumption: float


class ForecastResponse(BaseModel):
    model: str
    horizon: int
    forecast: list[ForecastPoint]


class RecommendationResponse(BaseModel):
    recommendations: list[dict[str, Any]]
