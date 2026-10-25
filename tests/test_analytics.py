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







# import pandas as pd
# import pytest

# from app.services.analytics import build_analysis


# def test_calculates_metrics_correctly():
#     actuals = pd.DataFrame([
#         {"start_time": "2026-01-15T10:00:00Z", "actual_mw": 100},
#         {"start_time": "2026-01-15T10:30:00Z", "actual_mw": 200},
#     ])

#     forecasts = pd.DataFrame([
#         {
#             "start_time": "2026-01-15T10:00:00Z",
#             "publish_time": "2026-01-14T11:00:00Z",
#             "forecast_mw": 110,
#         },
#         {
#             "start_time": "2026-01-15T10:30:00Z",
#             "publish_time": "2026-01-14T11:00:00Z",
#             "forecast_mw": 180,
#         },
#     ])

#     metrics, points = build_analysis(
#         actuals,
#         forecasts,
#         pd.Timestamp("2026-01-14T12:00:00Z"),
#         "2026-01-15",
#     )

#     assert metrics["matched_intervals"] == 2
#     assert metrics["mae_mw"] == pytest.approx(15)
#     assert metrics["rmse_mw"] == pytest.approx((250) ** 0.5)
#     assert metrics["bias_mw"] == pytest.approx(-5)
#     assert metrics["max_absolute_error_mw"] == pytest.approx(20)
#     assert len(points) == 2


# def test_reports_missing_forecast():
#     actuals = pd.DataFrame([
#         {"start_time": "2026-01-15T10:00:00Z", "actual_mw": 100},
#     ])
#     forecasts = pd.DataFrame(
#         columns=["start_time", "publish_time", "forecast_mw"]
#     )

#     metrics, _ = build_analysis(
#         actuals,
#         forecasts,
#         pd.Timestamp("2026-01-14T12:00:00Z"),
#         "2026-01-15",
#     )

#     assert metrics["matched_intervals"] == 0
#     assert metrics["missing_forecast_intervals"] == 1
#     assert metrics["mae_mw"] is None