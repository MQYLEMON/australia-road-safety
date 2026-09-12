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
| `dim_date` | one day | 13,088 |
| `dim_state` | one state/territory | 8 |
| `fact_population` | state × year | 280 |
| `forecast_monthly` | one forecast month | 12 |

In Power Query, check the type of every date column (`date`, `month_start`,
`crash_month`, `month`) is Date, and `date_key` columns are whole numbers.
Nothing else needs transforming — that is the point of doing the cleaning in
Python.

## 2. Model relationships

`dim_date` is **daily and gapless**: Power BI refuses to mark a month-grain
table as a date table ("dates in the date column cannot have gaps"), and the
DAX time-intelligence functions assume a contiguous daily column. ARDD
publishes no day-of-month, so every fact row is anchored to its month start
and joins on that date. Many facts therefore land on the 1st of the month —
correct at month grain, and the report never plots at day grain.

Model view → create (all many-to-one, single direction, filtering from dim to
fact):

```
fact_fatalities[crash_month]  →  dim_date[date]
fact_crashes[crash_month]     →  dim_date[date]
fact_fatalities[state]        →  dim_state[state]
fact_crashes[state]           →  dim_state[state]
fact_population[state]        →  dim_state[state]
forecast_monthly[month]       →  dim_date[date]
fact_fatalities[day_of_week]  →  dim_day[day_name]      (page 3, see below)
```

Do **not** join on `date_key`: in a daily dimension it repeats for every day of
a month, so it cannot be the "one" side of a relationship. It stays in the
model only as a convenient integer for slicing.

Delete anything auto-detect adds beyond these six — in particular
`fact_fatalities[crash_id]` ↔ `fact_crashes[crash_id]` (fact tables must not
filter each other) and any `fact_population[year]` ↔ `dim_date[year]` link,
which would break the per-capita measures.

Then:

- Mark `dim_date` as a date table (column `date`).
- Hide `date_key`, `crash_id` and other join keys from report view.
- Sort `dim_date[month_name]` by `dim_date[month]`.
- Turn off Options → Current file → Data load → Auto date/time; the model has
  its own date table and the hidden auto tables only add confusion.
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

- **Clustered column**: `Total Deaths` by `age_group`, legend `gender`.
  `age_group`'s labels happen to sort correctly alphabetically, so no sort
  column is needed — but the axis still defaults to sorting by value, so set
  Sort axis → `age_group` → ascending.
- **Bar**: `Total Deaths` by `road_user`.
- **Matrix heat map**: `dim_day[day_name]` rows × `hour` columns, values
  `Total Deaths`, background colour on. Filter `hour` is not blank to drop the
  53 records with no recorded time, which otherwise render as an unlabelled
  first column.
- **Cards**: `Male Share %`, `Weekend Night Share %`.

**The `dim_day` table exists because of a Power BI restriction.** The obvious
approach — a `SWITCH` calculated column mapping `day_of_week` to 1-7, then
sorting `day_of_week` by it — is rejected with a circular dependency error: a
column cannot be sorted by a column derived from itself. Putting the mapping in
its own table breaks the cycle:

```dax
dim_day =
DATATABLE (
    "day_name", STRING,
    "day_num", INTEGER,
    {
        { "Monday", 1 }, { "Tuesday", 2 }, { "Wednesday", 3 },
        { "Thursday", 4 }, { "Friday", 5 }, { "Saturday", 6 }, { "Sunday", 7 }
    }
)
```

Sort `dim_day[day_name]` by `dim_day[day_num]`, relate
`fact_fatalities[day_of_week]` → `dim_day[day_name]` (many-to-one, single
direction, **active**), and put `day_name` on the matrix rows.

### Page 4 — Crash characteristics

- **Column**: `Total Crashes` by `speed_zone`. Sort axis → `speed_zone` →
  ascending; the labels sort correctly alphabetically.
- **Column**: `Multi-Fatality Crash %` by `speed_zone`, `Unknown` excluded by a
  visual filter. Sorted by zone rather than by value, this reads as a
  dose-response curve — 3.1% in 41-50 zones to 12.9% above 100 — instead of a
  bare ranking. Keep it beside the volume chart: one says where crashes happen,
  the other says where they kill.
- **Line**: `Truck Involvement %` by year, x-axis type categorical, sorted by
  `year` ascending. Say in the title that the 2001-02 jump is a reporting
  change; presenting it as a real trend would be wrong.
- **Decomposition tree**: `Multi-Fatality Crash %` explained by `speed_zone`,
  `state`, `crash_type` — mirrors the severity model's findings.

**Every field on page 4 must come from `fact_crashes`.** Both fact tables carry
identically named columns (`speed_zone`, `state`, `crash_type`, `day_of_week`),
and they are deliberately unrelated to each other, so a `fact_fatalities`
column paired with a `fact_crashes` measure silently returns the grand total
for every category — flat bars, or a decomposition tree whose branches all show
the same number. Collapse the table you are not using in the Data pane while
building a page.

## 4. Design notes

- Theme: a restrained palette (dark blue for actuals, red/orange reserved for
  the forecast and risk callouts) reads better than default rainbow colours.
- Every page answers a question in its title ("Where is the per-capita risk?"
  not "State analysis").
- Add a text footer on each page: *Source: BITRE ARDD (CC BY 3.0 AU), ABS ERP
  (CC BY 4.0). Data to Oct 2023; crash dates at month grain.*

## 5. Publish / screenshot

Page captures live in `powerbi/screenshots/` and are embedded in the README.
To refresh them after a change: collapse the side panes, press Ctrl+F1 to
collapse the ribbon, then capture just the canvas.

If you have a Power BI Service workspace you can publish and add a "Publish to
web" link as well, but for a portfolio repo the screenshots plus the committed
`.pbix` are enough.
