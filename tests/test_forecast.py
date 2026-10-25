import pandas as pd

from app.services.forecast import select_forecast_as_of


def test_selects_latest_forecast_before_cutoff():
    forecasts = pd.DataFrame([
        {
            "start_time": "2026-01-15T10:00:00Z",
            "publish_time": "2026-01-14T08:00:00Z",
            "forecast_mw": 100,
        },
        {
            "start_time": "2026-01-15T10:00:00Z",
            "publish_time": "2026-01-14T11:00:00Z",
            "forecast_mw": 120,
        },
        {
            "start_time": "2026-01-15T10:00:00Z",
            "publish_time": "2026-01-14T13:00:00Z",
            "forecast_mw": 140,
        },
    ])

    result = select_forecast_as_of(
        forecasts,
        pd.Timestamp("2026-01-14T12:00:00Z"),
    )

    assert len(result) == 1
    assert result.iloc[0]["forecast_mw"] == 120
    assert result.iloc[0]["publish_time"] == pd.Timestamp(
        "2026-01-14T11:00:00Z"
    )


def test_returns_empty_when_no_forecast_is_eligible():
    forecasts = pd.DataFrame([
        {
            "start_time": "2026-01-15T10:00:00Z",
            "publish_time": "2026-01-14T13:00:00Z",
            "forecast_mw": 140,
        },
    ])

    result = select_forecast_as_of(
        forecasts,
        pd.Timestamp("2026-01-14T12:00:00Z"),
    )

    assert result.empty
