# Australian Road Safety Analysis

End-to-end analytics project on 35 years of Australian road fatality data:
**Python data pipeline → statistical modeling → Power BI dashboard**, built
entirely on open government data.

> **Headline findings**
>
> 1. Australia's per-capita road toll fell **~73%** between 1989 and 2022
>    (16.7 → 4.5 deaths per 100k) — but progress has stalled since ~2015.
> 2. The **Northern Territory's per-capita fatality rate is ~4× the national
>    average**; raw counts (NSW highest) tell the wrong story.
> 3. **Weekend nights** are the deadliest window — but the Christmas period,
>    contrary to folklore, is **no deadlier per day** than the rest of the
>    year. Given a fatal crash *does* happen at Christmas, however, the odds
>    it kills more than one person are **~1.4× higher** (fuller cars).
> 4. A SARIMA model projects **~1,200 deaths** for the 12 months after the
>    data ends (Nov 2023 – Oct 2024), with a calibrated 95% band designed to
>    flag months where the toll drifts above trend.

![National trend](reports/figures/01_national_trend.png)

## Project structure

```
├── data/                  (git-ignored; rebuilt by the two scripts below)
│   ├── raw/               ARDD + ABS downloads, untouched
│   └── processed/         cleaned tables + Power BI star schema
├── src/
│   ├── download_data.py   fetch ARDD (data.gov.au) + ABS ERP (SDMX API)
│   └── clean_data.py      cleaning, integrity checks, star-schema export
├── notebooks/
│   ├── 01_eda.ipynb       exploratory analysis (executed, with narrative)
│   └── 02_modeling.ipynb  SARIMA forecast + crash-severity classification
├── powerbi/
│   ├── build_guide.md     step-by-step dashboard assembly instructions
│   └── dax_measures.md    full DAX measure library
└── reports/figures/       publication-ready charts from the notebooks
```

## Reproduce

```bash
pip install -r requirements.txt
python src/download_data.py     # ~12 MB from data.gov.au + ABS API
python src/clean_data.py        # cleaned tables + Power BI star schema
jupyter notebook notebooks/     # run 01 then 02
```

Then follow [powerbi/build_guide.md](powerbi/build_guide.md) to assemble the
dashboard in Power BI Desktop.

## Data engineering

The raw ARDD is realistically messy, and all handling is documented in
[`src/clean_data.py`](src/clean_data.py):

- missing values encoded five different ways (`-9` as int *and* str,
  `Unknown`, `Unspecified`, `U`, blanks) — normalised to a single convention;
- mixed dtypes within one column (`Speed Limit`: `100` and `"100"` and `"<40"`);
- inconsistent category casing (`Arterial Road` vs `ARTERIAL ROAD`) and stray
  whitespace (`"M "` for Male);
- a column name containing an embedded newline, plus a trailing phantom column;
- integrity checks asserted on every run: unique crash IDs, no orphan
  fatalities, fatality counts reconciling between the two files.

The Power BI model is a proper **star schema** (month-grain date dimension —
ARDD publishes no day-of-month — state dimension, two fact tables, annual
population fact joined via `TREATAS`). Per-capita rates use ABS 30-June
Estimated Resident Population fetched live from the ABS Data API.

## Modeling

| Model | Task | Result |
|---|---|---|
| SARIMA (0,1,2)(1,1,1)₁₂ | 12-month national fatality forecast | MAPE **13.1%** on a 24-month holdout vs 13.9% seasonal-naive; the near-tie is itself a finding — the post-2015 plateau is close to a seasonal random walk, so the calibrated interval matters more than the point forecast |
| Logistic regression / random forest | P(multi-fatality \| fatal crash) | ROC-AUC **0.70**, PR-AUC 0.18 vs 8.5% base rate; key associations: NT (OR 2.3), speed zones >80 km/h (OR 1.6–1.9), Christmas period (OR 1.4), bus/articulated-truck involvement |

Both notebooks state their caveats explicitly: the severity model measures
*associations among fatal crashes* (no exposure denominator, no occupancy or
restraint data), not causal effects.

## Data sources & licences

| Source | Used for | Licence |
|---|---|---|
| [BITRE Australian Road Deaths Database](https://data.gov.au/data/dataset/australian-road-deaths-database) (data.gov.au) | fatalities & crashes, Jan 1989 – Oct 2023 | CC BY 3.0 AU |
| [ABS Estimated Resident Population](https://www.abs.gov.au/statistics/people/population/national-state-and-territory-population/latest-release) via the [ABS Data API](https://data.api.abs.gov.au) | state populations for per-capita rates | CC BY 4.0 |

BITRE publishes newer monthly extracts on its own site; `download_data.py`
takes a URL swap to use them.

## Limitations

- Crash dates are published at **month grain**; hour-of-day exists but not the
  calendar day, so daily seasonality (long weekends etc.) is approximated via
  BITRE's Christmas/Easter period flags.
- Geographic detail (remoteness, LGA, road type) only exists from ~2021.
- 2023 is a partial year (to October) and recent months are preliminary.
- Fatalities only — no injury or exposure (VKT) data, so no crash-rate
  denominators beyond population.
