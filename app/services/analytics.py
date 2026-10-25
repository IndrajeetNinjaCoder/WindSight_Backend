
import math

import pandas as pd


def _iso_utc(value):
    """Convert a pandas timestamp to an ISO-8601 UTC string."""
    if pd.isna(value):
        return None

    timestamp = pd.Timestamp(value)
    if timestamp.tzinfo is None:
        timestamp = timestamp.tz_localize("UTC")
    else:
        timestamp = timestamp.tz_convert("UTC")

    return timestamp.isoformat().replace("+00:00", "Z")


def build_analysis(actuals, forecasts, decision_cutoff, delivery_date):
    """
    Evaluate forecasts against actual generation on a 30-minute grid.

    Actuals: 48 half-hourly intervals per day.
    Forecasts: currently hourly in the WINDFOR dataset.
    Accuracy metrics use only intervals with both forecast and actual data.
    """
    actuals = actuals.copy()
    forecasts = forecasts.copy()

    cutoff = pd.Timestamp(decision_cutoff)
    if cutoff.tzinfo is None:
        raise ValueError("decision_cutoff must include a timezone.")
    cutoff = cutoff.tz_convert("UTC")

    # Normalize actual generation data.
    if not actuals.empty:
        actuals["start_time"] = pd.to_datetime(
            actuals["start_time"], utc=True, errors="coerce"
        )
        actuals["actual_mw"] = pd.to_numeric(
            actuals["actual_mw"], errors="coerce"
        )
        actuals = actuals.dropna(subset=["start_time", "actual_mw"])

    # Normalize forecast data.
    if not forecasts.empty:
        forecasts["start_time"] = pd.to_datetime(
            forecasts["start_time"], utc=True, errors="coerce"
        )
        forecasts["publish_time"] = pd.to_datetime(
            forecasts["publish_time"], utc=True, errors="coerce"
        )
        forecasts["forecast_mw"] = pd.to_numeric(
            forecasts["forecast_mw"], errors="coerce"
        )
        forecasts = forecasts.dropna(
            subset=["start_time", "publish_time", "forecast_mw"]
        )

        # Exclude forecasts published after the buying decision.
        forecasts = forecasts[forecasts["publish_time"] <= cutoff]

        # Select the latest eligible forecast for each delivery interval.
        forecasts = (
            forecasts.sort_values("publish_time")
            .drop_duplicates(subset=["start_time"], keep="last")
        )

    # Use the requested delivery date, not the earliest available record.
    day = pd.Timestamp(delivery_date)
    if day.tzinfo is None:
        day = day.tz_localize("UTC")
    else:
        day = day.tz_convert("UTC")
    day = day.normalize()

    # Build all 48 half-hourly delivery intervals.
    expected_intervals = pd.DataFrame({
        "start_time": pd.date_range(
            start=day,
            periods=48,
            freq="30min",
        )
    })

    # Keep records for the selected delivery day only.
    day_end = day + pd.Timedelta(days=1)

    actuals = actuals[
        (actuals["start_time"] >= day)
        & (actuals["start_time"] < day_end)
    ].drop_duplicates(subset=["start_time"], keep="last")

    forecasts = forecasts[
        (forecasts["start_time"] >= day)
        & (forecasts["start_time"] < day_end)
    ]

    # Merge forecast and actual values onto the 48-interval grid.
    forecast_columns = (
        forecasts[["start_time", "forecast_mw", "publish_time"]]
        if not forecasts.empty
        else pd.DataFrame(
            columns=["start_time", "forecast_mw", "publish_time"]
        )
    )

    actual_columns = (
        actuals[["start_time", "actual_mw"]]
        if not actuals.empty
        else pd.DataFrame(columns=["start_time", "actual_mw"])
    )

    result = (
        expected_intervals
        .merge(forecast_columns, on="start_time", how="left")
        .merge(actual_columns, on="start_time", how="left")
        .sort_values("start_time")
        .reset_index(drop=True)
    )

    # Calculate metrics only for intervals with both values.
    matched = result.dropna(
        subset=["forecast_mw", "actual_mw"]
    ).copy()

    if matched.empty:
        mae = rmse = bias = max_error = None
    else:
        matched["error_mw"] = (
            matched["forecast_mw"] - matched["actual_mw"]
        )
        matched["absolute_error_mw"] = matched["error_mw"].abs()

        mae = float(matched["absolute_error_mw"].mean())
        rmse = float(math.sqrt((matched["error_mw"] ** 2).mean()))
        bias = float(matched["error_mw"].mean())
        max_error = float(matched["absolute_error_mw"].max())

    result["error_mw"] = result["forecast_mw"] - result["actual_mw"]
    result["absolute_error_mw"] = result["error_mw"].abs()

    points = []
    for _, row in result.iterrows():
        points.append({
            "start_time": _iso_utc(row["start_time"]),
            "forecast_mw": (
                float(row["forecast_mw"])
                if pd.notna(row["forecast_mw"]) else None
            ),
            "actual_mw": (
                float(row["actual_mw"])
                if pd.notna(row["actual_mw"]) else None
            ),
            "error_mw": (
                float(row["error_mw"])
                if pd.notna(row["error_mw"]) else None
            ),
            "absolute_error_mw": (
                float(row["absolute_error_mw"])
                if pd.notna(row["absolute_error_mw"]) else None
            ),
            "forecast_publish_time": _iso_utc(row["publish_time"]),
        })

    metrics = {
        "mae_mw": mae,
        "rmse_mw": rmse,
        "bias_mw": bias,
        "max_absolute_error_mw": max_error,
        "matched_intervals": int(len(matched)),
        "missing_forecast_intervals": int(
            result["forecast_mw"].isna().sum()
        ),
        "missing_actual_intervals": int(
            result["actual_mw"].isna().sum()
        ),
    }

    return metrics, points