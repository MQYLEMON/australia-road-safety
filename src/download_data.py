"""Download the raw data for the Australian road safety analysis.

Sources:
1. BITRE Australian Road Deaths Database (ARDD), via data.gov.au
   https://data.gov.au/data/dataset/australian-road-deaths-database
   Licence: Creative Commons Attribution 3.0 Australia (CC BY 3.0 AU)
2. ABS quarterly Estimated Resident Population (ERP) by state, via the
   ABS Data API (SDMX): https://data.api.abs.gov.au
   Licence: Creative Commons Attribution 4.0 International

The data.gov.au mirror covers 1989-01 to 2023-10. BITRE publishes newer
monthly extracts at https://www.bitre.gov.au/statistics/safety/fatal_road_crash_database
— update the URLs below to point at a newer extract if you have access.

Usage:
    python src/download_data.py
"""

from pathlib import Path
from urllib.request import Request, urlopen

RAW_DIR = Path(__file__).resolve().parents[1] / "data" / "raw"

BASE = "https://data.gov.au/data/dataset/5b530fb8-526e-4fbf-b0f6-aa24e84e4277/resource"

# ABS Data API: ERP_Q dataflow, key = MEASURE.SEX.AGE.REGION.FREQ
# 1 = Estimated Resident Population, 3 = Persons, TOT = all ages,
# regions 1-8 = NSW, Vic, Qld, SA, WA, Tas, NT, ACT
ABS_ERP_URL = (
    "https://data.api.abs.gov.au/rest/data/ABS,ERP_Q,1.0.0/"
    "1.3.TOT.1+2+3+4+5+6+7+8.Q"
    "?startPeriod=1989-Q1&endPeriod=2023-Q4&format=csv"
)

RESOURCES = {
    "ardd_fatalities.csv": f"{BASE}/fd646fdc-7788-4bea-a736-e4aeb0dd09a8/download/ardd_fatalities.csv",
    "ardd_fatal_crashes.csv": f"{BASE}/d54f7465-74b8-4fff-8653-37e724d0ebbb/download/ardd_fatal_crashes.csv",
    "ardd_dictionary.pdf": f"{BASE}/59055fed-d4f1-4a81-b3ee-75cb438009c6/download/ardd_dictionary.pdf",
    "calendar.csv": f"{BASE}/7cbb2e91-cda6-42ed-94ad-cc7df097e82e/download/calendar.csv",
    "abs_erp_quarterly.csv": ABS_ERP_URL,
}


def download(url: str, dest: Path) -> None:
    req = Request(url, headers={"User-Agent": "Mozilla/5.0 (ARDD analysis project)"})
    with urlopen(req) as resp, open(dest, "wb") as f:
        f.write(resp.read())
    print(f"  {dest.name}: {dest.stat().st_size / 1e6:.1f} MB")


def main() -> None:
    RAW_DIR.mkdir(parents=True, exist_ok=True)
    print(f"Downloading ARDD resources to {RAW_DIR}")
    for name, url in RESOURCES.items():
        dest = RAW_DIR / name
        if dest.exists():
            print(f"  {name}: already present, skipping")
            continue
        download(url, dest)
    print("Done.")


if __name__ == "__main__":
    main()
