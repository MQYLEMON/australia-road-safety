# Power BI dashboard build guide

Step-by-step instructions to assemble `RoadSafety.pbix` from the star-schema
CSVs in `data/processed/powerbi/`. Written for Power BI Desktop (any recent
release).

## 1. Load the data

Get data → Text/CSV, load all six files:

| Table | Grain | Rows |
|---|---|---|
| `fact_fatalities` | one person killed | 55,360 |
| `fact_crashes` | one fatal crash | 49,903 |
| `dim_date` | one month | 418 |
| `dim_state` | one state/territory | 8 |
| `fact_population` | state × year | 280 |
| `forecast_monthly` | one forecast month | 12 |

In Power Query, check the type of every date column (`month_start`,
`crash_month`, `month`) is Date, and `date_key` columns are whole numbers.
Nothing else needs transforming — that is the point of doing the cleaning in
Python.

## 2. Model relationships

Model view → create (all many-to-one, single direction, filtering from dim to
fact):

```
fact_fatalities[date_key]  →  dim_date[date_key]
fact_crashes[date_key]     →  dim_date[date_key]
fact_fatalities[state]     →  dim_state[state]
fact_crashes[state]        →  dim_state[state]
fact_population[state]     →  dim_state[state]
forecast_monthly[month]    →  dim_date[month_start]
```

Then:

- Mark `dim_date` as a date table (column `month_start`).
- Hide `date_key`, `crash_id` and other join keys from report view.
- Sort `dim_date[month_name]` by `dim_date[month]`.
- Create the measures from [dax_measures.md](dax_measures.md) in a `_Measures` table.

The population table deliberately has **no relationship to dim_date** — the
year link is handled with `TREATAS` inside the `Population` measure (see the
measure file for why).

## 3. Report pages

### Page 1 — National overview

- **KPI cards**: `Total Deaths` (with a relative-date filter for latest 12
  months), `Deaths YoY %`, `Deaths per 100k`, `Multi-Fatality Crash %`.
- **Line chart**: `Total Deaths` by `dim_date[year]` — the 35-year decline.
  Add `Deaths per 100k` on the secondary axis (or a second line chart) to
  show the per-capita story; add a note that 2023 is a partial year.
- **Line chart (forecast)**: `Total Deaths`, `Forecast Deaths`,
  `Forecast Lo95`, `Forecast Hi95` by `dim_date[month_start]`, filtered to
  2018 onwards. This reproduces the notebook's forecast chart, live.
- Year range slicer (`dim_date[year]`) synced across pages.

### Page 2 — States and geography

- **Filled map or bar**: `Deaths per 100k` by `dim_state[state_name]` — use
  per-capita, not raw counts; call out NT ≈ 4× the national rate.
- **Bar**: `Total Deaths` by state (raw counts for context).
- **Matrix**: state × year heat map of `Deaths per 100k` (conditional
  formatting on the values).
- **Small multiples line**: `Total Deaths` by year, small multiples by state.

### Page 3 — People and risk windows

- **Clustered bar**: `Total Deaths` by `age_group`, legend `gender`.
- **Bar**: `Total Deaths` by `road_user`.
- **Matrix heat map**: `day_of_week` rows × `hour` columns, values
  `Total Deaths` with conditional formatting — the weekend-night signature.
- **Cards**: `Male Share %`, `Weekend Night Share %`.

### Page 4 — Crash characteristics

- **Bar**: `Total Crashes` by `speed_zone` (sorted by the zone order, not
  count — set a sort column if needed).
- **Donut or bar**: `crash_type` split.
- **Line**: share of crashes with truck involvement by year
  (measure: filtered `Total Crashes` over all crashes).
- **Card + decomposition tree**: `Multi-Fatality Crash %` decomposed by
  state / speed_zone / crash_type — mirrors the severity model's findings
  (NT, high-speed zones and holiday periods push severity up).

## 4. Design notes

- Theme: a restrained palette (dark blue for actuals, red/orange reserved for
  the forecast and risk callouts) reads better than default rainbow colours.
- Every page answers a question in its title ("Where is the per-capita risk?"
  not "State analysis").
- Add a text footer on each page: *Source: BITRE ARDD (CC BY 3.0 AU), ABS ERP
  (CC BY 4.0). Data to Oct 2023; crash dates at month grain.*

## 5. Publish / screenshot

When the report is assembled, export page screenshots to
`powerbi/screenshots/` (File → Export or just window captures) and link them
from the README. If you have a Power BI Service workspace, publish and add the
public "Publish to web" link to the README instead — but screenshots are
enough for a portfolio repo.
