-- Road safety analysis in SQL (SQLite dialect).
-- Run all queries with: python src/run_sql_analysis.py
-- Each query is titled with a "-- @title:" line the runner prints.

-- @title: 1. Annual deaths with year-over-year change (window: LAG)
WITH annual AS (
    SELECT year, COUNT(*) AS deaths
    FROM fatalities
    WHERE year < 2023          -- 2023 is a partial year
    GROUP BY year
)
SELECT
    year,
    deaths,
    deaths - LAG(deaths) OVER (ORDER BY year)                    AS yoy_change,
    ROUND(100.0 * (deaths - LAG(deaths) OVER (ORDER BY year))
          / LAG(deaths) OVER (ORDER BY year), 1)                 AS yoy_pct
FROM annual
ORDER BY year DESC
LIMIT 10;

-- @title: 2. Rolling 12-month death toll (window frame over months)
WITH monthly AS (
    SELECT crash_month, COUNT(*) AS deaths
    FROM fatalities
    GROUP BY crash_month
)
SELECT
    crash_month,
    deaths,
    SUM(deaths) OVER (
        ORDER BY crash_month
        ROWS BETWEEN 11 PRECEDING AND CURRENT ROW
    ) AS rolling_12m
FROM monthly
ORDER BY crash_month DESC
LIMIT 12;

-- @title: 3. States ranked by per-capita fatality rate, 2018-2022 (CTE + join + RANK)
WITH state_deaths AS (
    SELECT state, year, COUNT(*) AS deaths
    FROM fatalities
    WHERE year BETWEEN 2018 AND 2022
    GROUP BY state, year
),
rates AS (
    SELECT
        d.state,
        AVG(d.deaths)                                        AS avg_deaths,
        AVG(100000.0 * d.deaths / p.population)              AS per_100k
    FROM state_deaths d
    JOIN population p ON p.state = d.state AND p.year = d.year
    GROUP BY d.state
)
SELECT
    RANK() OVER (ORDER BY per_100k DESC) AS risk_rank,
    r.state,
    s.state_name,
    ROUND(r.avg_deaths, 1)  AS avg_annual_deaths,
    ROUND(r.per_100k, 2)    AS deaths_per_100k
FROM rates r
JOIN dim_state s ON s.state = r.state
ORDER BY risk_rank;

-- @title: 4. The weekend-night signature by state (conditional aggregation)
SELECT
    state,
    COUNT(*)                                                            AS deaths,
    ROUND(100.0 * SUM(CASE WHEN day_type = 'Weekend'
                            AND time_of_day = 'Night'
                           THEN 1 ELSE 0 END) / COUNT(*), 1)            AS weekend_night_pct,
    ROUND(100.0 * SUM(CASE WHEN time_of_day = 'Night'
                           THEN 1 ELSE 0 END) / COUNT(*), 1)            AS night_pct
FROM fatalities
WHERE year BETWEEN 2018 AND 2022
GROUP BY state
ORDER BY weekend_night_pct DESC;

-- @title: 5. Road-user mix by decade (pivot with CASE)
SELECT
    (year / 10) * 10                                                     AS decade,
    COUNT(*)                                                             AS deaths,
    ROUND(100.0 * SUM(road_user = 'Driver') / COUNT(*), 1)               AS driver_pct,
    ROUND(100.0 * SUM(road_user = 'Passenger') / COUNT(*), 1)            AS passenger_pct,
    ROUND(100.0 * SUM(road_user = 'Pedestrian') / COUNT(*), 1)           AS pedestrian_pct,
    ROUND(100.0 * SUM(road_user = 'Motorcycle rider') / COUNT(*), 1)     AS motorcyclist_pct,
    ROUND(100.0 * SUM(road_user = 'Pedal cyclist') / COUNT(*), 1)        AS cyclist_pct
FROM fatalities
GROUP BY decade
ORDER BY decade;

-- @title: 6. Multi-fatality crash rate by speed zone (fact-to-fact comparison)
SELECT
    speed_zone,
    COUNT(*)                                               AS crashes,
    SUM(multiple_fatalities)                               AS multi_fatality,
    ROUND(100.0 * SUM(multiple_fatalities) / COUNT(*), 2)  AS multi_pct,
    ROUND(AVG(n_fatalities), 3)                            AS avg_deaths_per_crash
FROM crashes
WHERE speed_zone != 'Unknown'
GROUP BY speed_zone
ORDER BY multi_pct DESC;
