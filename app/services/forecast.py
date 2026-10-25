import pandas as pd


def select_forecast_as_of(
    forecasts: pd.DataFrame,
    decision_cutoff: pd.Timestamp,
) -> pd.DataFrame:
    """
    Return the latest eligible forecast for each delivery interval.

    Expected columns:
      start_time, publish_time, forecast_mw
    """
    columns = ["start_time", "publish_time", "forecast_mw"]

    if forecasts.empty:
        return pd.DataFrame(columns=columns)

    df = forecasts[columns].copy()
    df["start_time"] = pd.to_datetime(df["start_time"], utc=True)
    df["publish_time"] = pd.to_datetime(df["publish_time"], utc=True)

    cutoff = pd.Timestamp(decision_cutoff)
    if cutoff.tzinfo is None:
        raise ValueError("decision_cutoff must include a timezone.")
    cutoff = cutoff.tz_convert("UTC")

    df = df[df["publish_time"] <= cutoff]
    df = df.dropna(subset=["start_time", "publish_time", "forecast_mw"])

    # Sort oldest to newest, then keep the last eligible publication per interval.
    df = df.sort_values(["start_time", "publish_time"])
    return (
        df.drop_duplicates(subset=["start_time"], keep="last")
        .sort_values("start_time")
        .reset_index(drop=True)
    )