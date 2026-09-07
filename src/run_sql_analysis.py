"""Execute every query in sql/analysis.sql and print the results.

Usage:
    python src/load_to_sqlite.py      # once, to build the database
    python src/run_sql_analysis.py
"""

import sqlite3
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
DB_PATH = ROOT / "data" / "road_safety.db"
SQL_PATH = ROOT / "sql" / "analysis.sql"


def main() -> None:
    sql = SQL_PATH.read_text(encoding="utf-8")
    queries = [q.strip() for q in sql.split(";") if q.strip()]

    pd.set_option("display.width", 120)
    with sqlite3.connect(DB_PATH) as conn:
        for q in queries:
            title = next(
                (line.split("@title:", 1)[1].strip()
                 for line in q.splitlines()
                 if line.strip().startswith("-- @title:")),
                "(untitled)",
            )
            print(f"\n{'=' * 70}\n{title}\n{'=' * 70}")
            print(pd.read_sql_query(q, conn).to_string(index=False))


if __name__ == "__main__":
    main()
