from datetime import date, datetime, time, timedelta, timezone
from typing import Any

import httpx
import pandas as pd

BASE_URL = "https://data.elexon.co.uk/bmrs/api/v1/datasets"
TIMEOUT = 30.0


class ElexonAPIError(RuntimeError):
    pass


def _extract_rows(payload: Any) -> list[dict]:
    """Support either a bare list or an object containing data."""
    if isinstance(payload, list):
        return payload

    if isinstance(payload, dict) and isinstance(payload.get("data"), list):
        return payload["data"]

    raise ElexonAPIError(
        "Unexpected Elexon response: expected a list or an object with a data list."
    )


async def _get_rows(
    client: httpx.AsyncClient,
    dataset: str,
    params: dict,
) -> list[dict]:
    url = f"{BASE_URL}/{dataset}/stream"

    try:
        response = await client.get(url, params=params)
        response.raise_for_status()
        return _extract_rows(response.json())
    except (httpx.HTTPError, ValueError) as exc:
        raise ElexonAPIError(
            f"Failed to retrieve {dataset} from Elexon: {exc}"
        ) from exc


def _utc_iso(value: datetime) -> str:
    """Format a timezone-aware datetime for an Elexon query."""
    if value.tzinfo is None:
        raise ValueError("Datetime must include a timezone.")
    return value.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")



async def fetch_actuals(delivery_date: date) -> pd.DataFrame:
    """
    Fetch national wind generation for one UTC delivery day.
    Filter by publication time, then retain delivery intervals for the target day.
    """
    start = datetime.combine(delivery_date, time.min, tzinfo=timezone.utc)
    end = start + timedelta(days=1)

    params = {
        "publishDateTimeFrom": _utc_iso(start),
        "publishDateTimeTo": _utc_iso(end + timedelta(hours=1)),
    }

    async with httpx.AsyncClient(timeout=TIMEOUT) as client:
        rows = await _get_rows(client, "FUELHH", params)

    df = pd.DataFrame(rows)
    if df.empty:
        return pd.DataFrame(columns=["start_time", "actual_mw"])

    required = {"startTime", "fuelType", "generation"}
    if not required.issubset(df.columns):
        raise ElexonAPIError(
            f"FUELHH response is missing fields: "
            f"{sorted(required - set(df.columns))}"
        )

    # Keep national wind generation only.
    df = df[
        df["fuelType"].astype(str).str.upper() == "WIND"
    ].copy()

    df["start_time"] = pd.to_datetime(
        df["startTime"], utc=True, errors="coerce"
    )
    df["actual_mw"] = pd.to_numeric(
        df["generation"], errors="coerce"
    )

    df = df.dropna(subset=["start_time", "actual_mw"])

    # Keep delivery intervals for the requested day, not publication dates.
    df = df[
        (df["start_time"] >= start)
        & (df["start_time"] < end)
    ]

    # Keep the latest revision for each interval, if publication times exist.
    if "publishTime" in df.columns:
        df["publish_time"] = pd.to_datetime(
            df["publishTime"], utc=True, errors="coerce"
        )
        df = df.sort_values("publish_time", na_position="first")

    df = df.drop_duplicates(
        subset=["start_time"], keep="last"
    )

    return (
        df[["start_time", "actual_mw"]]
        .sort_values("start_time")
        .reset_index(drop=True)
    )


async def fetch_forecasts(
    delivery_date: date,
    decision_cutoff: datetime,
) -> pd.DataFrame:
    """
    Fetch WINDFOR forecasts for the delivery day.

    The publication window ends at decision_cutoff, so forecasts published
    after the purchasing decision cannot leak into the analysis.
    """
    if decision_cutoff.tzinfo is None:
        raise ValueError("decision_cutoff must include a timezone.")

    start = datetime.combine(delivery_date, time.min, tzinfo=timezone.utc)
    end = start + timedelta(days=1)

    params = {
        # The API filters by forecast publication time. Confirm these exact
        # parameter names against the current WINDFOR dataset documentation.
        "publishDateTimeFrom": "2025-12-01T00:00:00Z",
        "publishDateTimeTo": _utc_iso(decision_cutoff),
    }

    async with httpx.AsyncClient(timeout=TIMEOUT) as client:
        rows = await _get_rows(client, "WINDFOR", params)

    df = pd.DataFrame(rows)
    if df.empty:
        return pd.DataFrame(
            columns=["start_time", "publish_time", "forecast_mw"]
        )

    required = {"startTime", "publishTime", "generation"}
    if not required.issubset(df.columns):
        raise ElexonAPIError(
            f"WINDFOR response is missing fields: {sorted(required - set(df.columns))}"
        )

    df["start_time"] = pd.to_datetime(df["startTime"], utc=True, errors="coerce")
    df["publish_time"] = pd.to_datetime(
        df["publishTime"], utc=True, errors="coerce"
    )
    df["forecast_mw"] = pd.to_numeric(df["generation"], errors="coerce")
    df = df.dropna(subset=["start_time", "publish_time", "forecast_mw"])

    cutoff = pd.Timestamp(decision_cutoff).tz_convert("UTC")
    df = df[
        (df["start_time"] >= start)
        & (df["start_time"] < end)
        & (df["publish_time"] <= cutoff)
    ]

    return df[
        ["start_time", "publish_time", "forecast_mw"]
    ].sort_values(["start_time", "publish_time"]).reset_index(drop=True)