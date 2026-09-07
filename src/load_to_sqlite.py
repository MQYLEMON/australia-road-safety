"""Load the processed tables into a local SQLite database.

Creates data/road_safety.db with the same star schema the Power BI model
uses, so the SQL analyses in sql/analysis.sql run against real tables.

Usage:
    python src/load_to_sqlite.py
"""

import sqlite3
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
PROCESSED = ROOT / "data" / "processed"
DB_PATH = ROOT / "data" / "road_safety.db"

TABLES = {
    "fatalities": PROCESSED / "fatalities_clean.csv",
    "crashes": PROCESSED / "crashes_clean.csv",
    "population": PROCESSED / "erp_state_year.csv",
    "dim_date": PROCESSED / "powerbi" / "dim_date.csv",
    "dim_state": PROCESSED / "powerbi" / "dim_state.csv",
}

INDEXES = [
    "CREATE INDEX IF NOT EXISTS idx_fat_state_year ON fatalities (state, year)",
    "CREATE INDEX IF NOT EXISTS idx_fat_crash ON fatalities (crash_id)",
    "CREATE INDEX IF NOT EXISTS idx_crash_state_year ON crashes (state, year)",
    "CREATE INDEX IF NOT EXISTS idx_pop_state_year ON population (state, year)",
]


def main() -> None:
    with sqlite3.connect(DB_PATH) as conn:
        for name, path in TABLES.items():
            df = pd.read_csv(path, low_memory=False)
            df.to_sql(name, conn, if_exists="replace", index=False)
            print(f"  {name}: {len(df):,} rows")
        for stmt in INDEXES:
            conn.execute(stmt)
    print(f"Database ready: {DB_PATH}")


if __name__ == "__main__":
    main()
