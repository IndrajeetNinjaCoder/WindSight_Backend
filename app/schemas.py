from datetime import datetime, date
from pydantic import BaseModel


class AnalysisPoint(BaseModel):
    start_time: datetime
    forecast_mw: float | None
    actual_mw: float | None
    error_mw: float | None
    absolute_error_mw: float | None
    forecast_publish_time: datetime | None


class Metrics(BaseModel):
    mae_mw: float | None
    rmse_mw: float | None
    bias_mw: float | None
    max_absolute_error_mw: float | None
    matched_intervals: int
    missing_forecast_intervals: int
    missing_actual_intervals: int


class AnalysisResponse(BaseModel):
    delivery_date: date
    decision_cutoff: datetime
    metrics: Metrics
    points: list[AnalysisPoint]