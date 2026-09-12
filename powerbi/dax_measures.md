# DAX measure library

All measures live in a dedicated `_Measures` table (Home → Enter data → create an
empty table named `_Measures`, then add measures to it). Names are referenced by
the [build guide](build_guide.md).

## Core counts

```dax
Total Deaths = COUNTROWS ( fact_fatalities )
```

```dax
Total Crashes = COUNTROWS ( fact_crashes )
```

```dax
Deaths per Crash =
DIVIDE ( [Total Deaths], [Total Crashes] )
```

## Population and per-capita rates

`fact_population` is annual (30 June ERP) and keyed by `state` + `year`, so it
relates to `dim_state` directly but needs `TREATAS` to pick up the year from
the date dimension:

```dax
Population =
CALCULATE (
    SUM ( fact_population[population] ),
    TREATAS ( VALUES ( dim_date[year] ), fact_population[year] )
)
```

```dax
Deaths per 100k =
DIVIDE ( [Total Deaths], [Population] ) * 100000
```

```dax
National Deaths per 100k = CALCULATE ( [Deaths per 100k], ALL ( dim_state ) )
```

`ALL(dim_state)` drops the state filter while leaving the date filter intact,
so this returns the national rate for whatever period is selected. Bind it to
the reference line on the per-state bar chart (Analytics → constant line →
`fx` → field value) rather than typing a number: a hard-coded 4.49 is only
correct for 2018-2022 and starts disagreeing with the rest of the page the
moment the slicer moves.

> When more than one year is in context (e.g. a 5-year page filter), `Population`
> sums across years, which keeps `Deaths per 100k` an *annualised average* —
> exactly what the state comparison page wants.

## Time intelligence

Time intelligence runs off `dim_date[date]`, the gapless daily column the
table is marked as a date table on. Use `dim_date[month_start]` for grouping
and axes, never as the argument to a time-intelligence function.

```dax
Deaths PY =
CALCULATE ( [Total Deaths], SAMEPERIODLASTYEAR ( dim_date[date] ) )
```

```dax
Deaths YoY % =
DIVIDE ( [Total Deaths] - [Deaths PY], [Deaths PY] )
```

```dax
Deaths Rolling 12M =
CALCULATE (
    [Total Deaths],
    DATESINPERIOD ( dim_date[date], MAX ( dim_date[date] ), -12, MONTH )
)
```

## Severity and profile

```dax
Multi-Fatality Crash % =
DIVIDE (
    CALCULATE ( [Total Crashes], fact_crashes[multiple_fatalities] = TRUE () ),
    [Total Crashes]
)
```

```dax
Male Share % =
DIVIDE (
    CALCULATE ( [Total Deaths], fact_fatalities[gender] = "Male" ),
    CALCULATE ( [Total Deaths], NOT ISBLANK ( fact_fatalities[gender] ) )
)
```

```dax
Truck Involvement % =
DIVIDE (
    CALCULATE (
        [Total Crashes],
        FILTER (
            fact_crashes,
            fact_crashes[heavy_rigid_truck_involved] = "Yes"
                || fact_crashes[articulated_truck_involved] = "Yes"
        )
    ),
    [Total Crashes]
)
```

```dax
Weekend Night Share % =
DIVIDE (
    CALCULATE (
        [Total Deaths],
        fact_fatalities[day_type] = "Weekend",
        fact_fatalities[time_of_day] = "Night"
    ),
    [Total Deaths]
)
```

## Display units on cards

Recent Power BI card visuals abbreviate large numbers ("55K") with no
display-unit setting to turn it off, and they override the measure's own format
string. Where an exact figure matters on a card, wrap it:

```dax
Total Deaths Label = FORMAT ( [Total Deaths], "#,0" )
```

The result is text, so it cannot be aggregated or sorted — use it only on cards
and keep `[Total Deaths]` everywhere else. Chart axes and data labels do expose
a display-unit setting, so they need no workaround.

## Forecast overlay

`forecast_monthly.csv` (from `02_modeling.ipynb`) relates to `dim_date` via its
`month` column → `dim_date[date]`. `dim_date` runs 12 months past the last
observed month so those rows exist; `dim_date[has_actuals]` separates the
observed region from the forecast horizon.

```dax
Forecast Deaths = SUM ( forecast_monthly[forecast] )
```

```dax
Forecast Lo95 = SUM ( forecast_monthly[lo95] )
```

```dax
Forecast Hi95 = SUM ( forecast_monthly[hi95] )
```

Plot `[Total Deaths]`, `[Forecast Deaths]`, `[Forecast Lo95]`, `[Forecast Hi95]`
on one line chart; actuals and forecast never overlap in time, so the lines
join cleanly at Oct/Nov 2023.
