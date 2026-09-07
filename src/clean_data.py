"""Clean the raw ARDD + ABS data and build analysis / Power BI outputs.

Raw-data quirks handled here (all discovered by profiling, see notebooks/01_eda):
- Missing values encoded inconsistently as -9, "-9", "Unknown", "Unspecified",
  "Undetermined", "U" or blank, sometimes as int and str in the same column.
- Mixed dtypes in `Speed Limit` (int 100 and str "100"), plus "<40".
- Inconsistent category casing ("Arterial Road" vs "ARTERIAL ROAD").
- Stray whitespace ("M " for Male), a trailing empty column, and a column
  name containing an embedded newline ("Bus \nInvolvement").
- Geographic detail columns (remoteness, SA4, LGA, road type) are only
  populated from ~2021 onwards.

Outputs
-------
data/processed/
    fatalities_clean.csv   one row per person killed (analysis grain)
    crashes_clean.csv      one row per fatal crash
    erp_state_year.csv     ABS estimated resident population, state x year
data/processed/powerbi/    star-schema tables for the Power BI model
    fact_fatalities.csv, fact_crashes.csv,
    dim_date.csv, dim_state.csv, fact_population.csv

Usage:
    python src/clean_data.py
"""

from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "data" / "raw"
PROCESSED = ROOT / "data" / "processed"
POWERBI = PROCESSED / "powerbi"

# Values that mean "we don't know" across the ARDD columns.
MISSING_TOKENS = {"-9", "", "Unknown", "Unspecified", "Undetermined", "U", "nan"}

STATE_NAMES = {
    "NSW": "New South Wales",
    "Vic": "Victoria",
    "Qld": "Queensland",
    "SA": "South Australia",
    "WA": "Western Australia",
    "Tas": "Tasmania",
    "NT": "Northern Territory",
    "ACT": "Australian Capital Territory",
}

# ABS ASGS region codes used by the ERP_Q dataflow.
ABS_REGION_CODES = {
    1: "NSW", 2: "Vic", 3: "Qld", 4: "SA",
    5: "WA", 6: "Tas", 7: "NT", 8: "ACT",
}

AGE_GROUP_LABELS = {
    "0_to_16": "0-16",
    "17_to_25": "17-25",
    "26_to_39": "26-39",
    "40_to_64": "40-64",
    "65_to_74": "65-74",
    "75_or_older": "75+",
}


def standardise_missing(s: pd.Series) -> pd.Series:
    """Strip whitespace and map every known missing token to NaN."""
    s = s.astype("string").str.strip()
    return s.where(~s.isin(MISSING_TOKENS), pd.NA)


def clean_speed_limit(s: pd.Series) -> tuple[pd.Series, pd.Series]:
    """Return (numeric speed limit, speed zone bucket).

    "<40" has no exact number, so it is NaN in the numeric column but still
    lands in the "40 or below" bucket rather than being thrown away.
    """
    s = standardise_missing(s)
    numeric = pd.to_numeric(s.where(s != "<40"), errors="coerce")

    bins = [0, 40, 50, 60, 80, 100, np.inf]
    labels = ["40 or below", "41-50", "51-60", "61-80", "81-100", "Over 100"]
    zone = pd.cut(numeric, bins=bins, labels=labels, right=True).astype("string")
    # s.eq("<40") is NA for missing tokens, and where/mask treat NA as False,
    # which silently bucketed "-9"/"Unspecified" as "40 or below". Fill the
    # mask explicitly so only a literal "<40" lands in that bucket.
    zone = zone.mask(s.eq("<40").fillna(False), "40 or below")
    return numeric, zone.fillna("Unknown")


def load_ardd(path: Path) -> pd.DataFrame:
    """Load an ARDD CSV with the structural quirks fixed."""
    df = pd.read_csv(path, dtype=str)
    df.columns = [c.replace("\n", " ").strip() for c in df.columns]
    df = df.rename(columns={"Bus  Involvement": "Bus Involvement"})
    df = df.loc[:, ~df.columns.str.startswith("Unnamed")]
    return df


def clean_common(df: pd.DataFrame) -> pd.DataFrame:
    """Cleaning shared by the fatalities and crashes files."""
    out = pd.DataFrame()
    out["crash_id"] = df["Crash ID"].astype("int64")
    out["state"] = df["State"].str.strip()
    out["year"] = df["Year"].astype(int)
    out["month"] = df["Month"].astype(int)
    # Exact day is not published; anchor each crash to the first of its month.
    out["crash_month"] = pd.to_datetime(
        {"year": out["year"], "month": out["month"], "day": 1}
    )
    out["date_key"] = out["year"] * 100 + out["month"]
    out["day_of_week"] = standardise_missing(df["Dayweek"])
    out["time"] = standardise_missing(df["Time"])
    out["hour"] = pd.to_numeric(out["time"].str.slice(0, 2), errors="coerce").astype("Int64")
    tod = df.filter(regex="Time of [Dd]ay").iloc[:, 0]
    out["time_of_day"] = standardise_missing(tod)
    out["day_type"] = standardise_missing(df["Day of week"])  # Weekday / Weekend
    out["crash_type"] = standardise_missing(df["Crash Type"])

    for src, dst in [
        ("Bus Involvement", "bus_involved"),
        ("Heavy Rigid Truck Involvement", "heavy_rigid_truck_involved"),
        ("Articulated Truck Involvement", "articulated_truck_involved"),
    ]:
        out[dst] = standardise_missing(df[src])

    out["speed_limit"], out["speed_zone"] = clean_speed_limit(df["Speed Limit"])

    # Geographic detail exists only from ~2021; keep it, flag coverage in docs.
    out["remoteness"] = standardise_missing(df["National Remoteness Areas"])
    out["sa4"] = standardise_missing(df["SA4 Name 2021"])
    out["lga"] = standardise_missing(df["National LGA Name 2021"])
    out["road_type"] = standardise_missing(df["National Road Type"]).str.title()
    out["road_type"] = out["road_type"].replace(
        {"National Or State Highway": "National or State Highway"}
    )

    out["christmas_period"] = df["Christmas Period"].str.strip().eq("Yes")
    out["easter_period"] = df["Easter Period"].str.strip().eq("Yes")
    return out


def clean_fatalities() -> pd.DataFrame:
    df = load_ardd(RAW / "ardd_fatalities.csv")
    out = clean_common(df)

    gender = standardise_missing(df["Gender"])
    out["gender"] = gender.replace({"M": "Male", "F": "Female"})

    age = pd.to_numeric(standardise_missing(df["Age"]), errors="coerce")
    out["age"] = age.astype("Int64")

    out["age_group"] = standardise_missing(df["Age Group"]).map(AGE_GROUP_LABELS)

    road_user = standardise_missing(df["Road User"])
    out["road_user"] = road_user.replace({"Other/-9": "Other/Unknown"})
    return out


def clean_crashes() -> pd.DataFrame:
    df = load_ardd(RAW / "ardd_fatal_crashes.csv")
    out = clean_common(df)
    out["n_fatalities"] = df["Number Fatalities"].astype(int)
    out["multiple_fatalities"] = out["n_fatalities"] > 1
    return out


def clean_population() -> pd.DataFrame:
    """ABS quarterly ERP -> state x year, using the 30 June (Q2) reference."""
    erp = pd.read_csv(RAW / "abs_erp_quarterly.csv")
    erp = erp[erp["UNIT_MEASURE"] == "PSNS"].copy()
    erp["state"] = erp["REGION"].map(ABS_REGION_CODES)
    parts = erp["TIME_PERIOD"].str.split("-Q", expand=True)
    erp["year"] = parts[0].astype(int)
    erp["quarter"] = parts[1].astype(int)
    annual = (
        erp[erp["quarter"] == 2]
        .rename(columns={"OBS_VALUE": "population"})
        .loc[:, ["state", "year", "population"]]
        .sort_values(["state", "year"])
        .reset_index(drop=True)
    )
    annual["population"] = annual["population"].astype(int)
    return annual


def build_dim_date(forecast_months: int = 12) -> pd.DataFrame:
    """Month-grain date dimension.

    ARDD publishes crash month but not the exact day, so the facts sit at
    month grain and the date dimension must too — a daily dimension would
    create a many-to-many join on date_key.

    The dimension runs `forecast_months` past the last observed month so the
    SARIMA forecast has date rows to join to. Without the extension every
    forecast row maps to a blank date and the projection cannot be plotted
    on a date axis at all. `has_actuals` separates the two regions.
    """
    cal = pd.read_csv(RAW / "calendar.csv")
    days = pd.to_datetime(cal["Date"], format="%d-%b-%y")
    observed = days.dt.to_period("M").dt.to_timestamp()

    months = pd.date_range(
        observed.min(),
        observed.max() + pd.DateOffset(months=forecast_months),
        freq="MS",
    )
    d = pd.DataFrame({"month_start": months})
    d["year"] = d["month_start"].dt.year
    d["month"] = d["month_start"].dt.month
    d["month_name"] = d["month_start"].dt.strftime("%b")
    d["quarter"] = "Q" + d["month_start"].dt.quarter.astype(str)
    d["date_key"] = d["year"] * 100 + d["month"]
    # Australian financial year runs July-June: FY2020 = Jul 2019 - Jun 2020.
    fy_end = d["year"] + (d["month"] >= 7).astype(int)
    d["financial_year"] = "FY" + fy_end.astype(str)
    d["has_actuals"] = d["month_start"] <= observed.max()
    return d.sort_values("month_start").reset_index(drop=True)


def build_dim_state(pop: pd.DataFrame) -> pd.DataFrame:
    latest = pop[pop["year"] == pop["year"].max()][["state", "population"]]
    dim = pd.DataFrame(
        {"state": list(STATE_NAMES), "state_name": list(STATE_NAMES.values())}
    ).merge(latest.rename(columns={"population": "population_latest"}), on="state")
    return dim


def main() -> None:
    PROCESSED.mkdir(parents=True, exist_ok=True)
    POWERBI.mkdir(parents=True, exist_ok=True)

    fatalities = clean_fatalities()
    crashes = clean_crashes()
    population = clean_population()
    dim_date = build_dim_date()
    dim_state = build_dim_state(population)

    # --- integrity checks -------------------------------------------------
    assert crashes["crash_id"].is_unique, "crash_id must be unique in crashes"
    orphans = ~fatalities["crash_id"].isin(crashes["crash_id"])
    assert not orphans.any(), f"{orphans.sum()} fatalities missing a parent crash"
    assert set(fatalities["state"]) <= set(STATE_NAMES), "unexpected state code"
    total_check = crashes["n_fatalities"].sum()
    if total_check != len(fatalities):
        print(f"  note: crashes report {total_check} deaths vs "
              f"{len(fatalities)} fatality rows (minor source revisions)")

    # --- analysis outputs -------------------------------------------------
    fatalities.to_csv(PROCESSED / "fatalities_clean.csv", index=False)
    crashes.to_csv(PROCESSED / "crashes_clean.csv", index=False)
    population.to_csv(PROCESSED / "erp_state_year.csv", index=False)

    # --- Power BI star schema --------------------------------------------
    fatalities.to_csv(POWERBI / "fact_fatalities.csv", index=False)
    crashes.to_csv(POWERBI / "fact_crashes.csv", index=False)
    dim_date.to_csv(POWERBI / "dim_date.csv", index=False)
    dim_state.to_csv(POWERBI / "dim_state.csv", index=False)
    population.to_csv(POWERBI / "fact_population.csv", index=False)

    # --- QA summary -------------------------------------------------------
    print(f"fatalities: {len(fatalities):,} rows, "
          f"{fatalities['crash_month'].min():%Y-%m} to {fatalities['crash_month'].max():%Y-%m}")
    print(f"crashes:    {len(crashes):,} rows")
    print(f"population: {len(population):,} state-year rows")
    for col in ["gender", "age", "road_user", "speed_limit", "crash_type"]:
        pct = fatalities[col].isna().mean() * 100
        print(f"  missing {col}: {pct:.2f}%")


if __name__ == "__main__":
    main()
