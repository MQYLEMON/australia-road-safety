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

> When more than one year is in context (e.g. a 5-year page filter), `Population`
> sums across years, which keeps `Deaths per 100k` an *annualised average* —
> exactly what the state comparison page wants.

## Time intelligence

Month-grain facts mean the built-in time intelligence works off
`dim_date[month_start]` (mark `dim_date` as a date table on this column).

```dax
Deaths PY =
CALCULATE ( [Total Deaths], SAMEPERIODLASTYEAR ( dim_date[month_start] ) )
```

```dax
Deaths YoY % =
DIVIDE ( [Total Deaths] - [Deaths PY], [Deaths PY] )
```

```dax
Deaths Rolling 12M =
CALCULATE (
    [Total Deaths],
    DATESINPERIOD ( dim_date[month_start], MAX ( dim_date[month_start] ), -12, MONTH )
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

## Forecast overlay

`forecast_monthly.csv` (from `02_modeling.ipynb`) relates to `dim_date` via its
`month` column → `dim_date[month_start]`.

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
