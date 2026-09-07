"""Unit tests for the cleaning pipeline.

The unit tests run on small synthetic frames and need no downloaded data;
the integration tests at the bottom run only when the processed outputs
exist locally (they are skipped in CI, where data/ is not built).
"""
import pandas as pd
import pytest

from src.clean_data import (
    PROCESSED,
    STATE_NAMES,
    clean_common,
    clean_speed_limit,
    standardise_missing,
)

# ---------------------------------------------------------------- unit tests

def test_standardise_missing_maps_all_missing_tokens_to_na():
    s = pd.Series(["-9", "Unknown", "Unspecified", "U", "", "Undetermined", None])
    out = standardise_missing(s)
    assert out.isna().all()


def test_standardise_missing_strips_whitespace_and_keeps_values():
    s = pd.Series(["M ", " Female", "Driver"])
    out = standardise_missing(s)
    assert list(out) == ["M", "Female", "Driver"]


def test_clean_speed_limit_handles_mixed_and_special_values():
    s = pd.Series(["100", "60", "<40", "-9", "Unspecified", "5"])
    numeric, zone = clean_speed_limit(s)

    assert numeric.tolist()[:2] == [100.0, 60.0]
    assert pd.isna(numeric.iloc[2]), "'<40' has no exact number"
    assert pd.isna(numeric.iloc[3]) and pd.isna(numeric.iloc[4])

    assert zone.tolist() == [
        "81-100", "51-60", "40 or below", "Unknown", "Unknown", "40 or below",
    ]


def _minimal_raw_frame() -> pd.DataFrame:
    """Two synthetic rows shaped like the raw ARDD extract."""
    return pd.DataFrame({
        "Crash ID": ["20231001", "19891002"],
        "State": ["NSW", "Vic "],
        "Year": ["2023", "1989"],
        "Month": ["7", "12"],
        "Dayweek": ["Friday", "Sunday"],
        "Time": ["23:15", "-9"],
        "Day of week": ["Weekday", "Weekend"],
        "Time of day": ["Night", "Day"],
        "Crash Type": ["Single", "Multiple"],
        "Bus Involvement": ["No", "-9"],
        "Heavy Rigid Truck Involvement": ["No", "Yes"],
        "Articulated Truck Involvement": ["No", "No"],
        "Speed Limit": ["110", "<40"],
        "National Remoteness Areas": ["Unknown", None],
        "SA4 Name 2021": [None, None],
        "National LGA Name 2021": [None, None],
        "National Road Type": ["ARTERIAL ROAD", None],
        "Christmas Period": ["No", "Yes"],
        "Easter Period": ["No", "No"],
    })


def test_clean_common_builds_month_anchor_and_date_key():
    out = clean_common(_minimal_raw_frame())
    assert out.loc[0, "crash_month"] == pd.Timestamp("2023-07-01")
    assert out.loc[0, "date_key"] == 202307
    assert out.loc[1, "date_key"] == 198912


def test_clean_common_normalises_categories_and_flags():
    out = clean_common(_minimal_raw_frame())
    assert out.loc[1, "state"] == "Vic", "whitespace stripped"
    assert out.loc[0, "hour"] == 23
    assert pd.isna(out.loc[1, "time"]) and pd.isna(out.loc[1, "hour"])
    assert pd.isna(out.loc[1, "bus_involved"]), "-9 involvement becomes NA"
    assert out.loc[0, "road_type"] == "Arterial Road", "casing normalised"
    assert bool(out.loc[1, "christmas_period"]) is True
    assert bool(out.loc[0, "christmas_period"]) is False


# --------------------------------------------------------- integration tests

needs_data = pytest.mark.skipif(
    not (PROCESSED / "fatalities_clean.csv").exists(),
    reason="processed data not built (run src/download_data.py + src/clean_data.py)",
)


@needs_data
def test_processed_fatalities_integrity():
    fat = pd.read_csv(PROCESSED / "fatalities_clean.csv", low_memory=False)
    crashes = pd.read_csv(PROCESSED / "crashes_clean.csv", low_memory=False)

    assert crashes["crash_id"].is_unique
    assert fat["crash_id"].isin(crashes["crash_id"]).all(), "orphan fatalities"
    assert set(fat["state"].unique()) <= set(STATE_NAMES)
    assert fat["year"].between(1989, 2030).all()
    assert crashes["n_fatalities"].ge(1).all()


@needs_data
def test_star_schema_keys_align():
    powerbi = PROCESSED / "powerbi"
    dim_date = pd.read_csv(powerbi / "dim_date.csv")
    fact = pd.read_csv(powerbi / "fact_fatalities.csv", low_memory=False)

    assert dim_date["date_key"].is_unique, "dim_date must be month grain"
    assert fact["date_key"].isin(dim_date["date_key"]).all()
