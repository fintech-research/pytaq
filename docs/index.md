# PyTAQ

Process NYSE TAQ trade and quote data with [Ibis](https://ibis-project.org/).

PyTAQ implements the standard cleaning and liquidity-metric pipeline for TAQ data, following [Holden and Jacobsen (2014)](https://doi.org/10.1111/jofi.12127). Because it is written against Ibis rather than a single engine, the same code runs on the WRDS postgres server and on local copies of the data.

## Three ways to use it

| | What it is | Install |
|---|---|---|
| On the WRDS cloud | Run on WRDS's own machines, against their postgres server | `pytaq[postgres]` |
| Local, remote data | Run on your laptop, query the WRDS postgres server | `pytaq[postgres]` |
| Local, local data | Run on your laptop, against local TAQ files | `pytaq[duckdb]` |

Only the first step differs. Cleaning and metrics are identical in all three.

## A short example

```python
import datetime

from pytaq import clean_trades, local

con = local.connect()
raw = local.get_trades(con, "data/", datetime.date(2020, 1, 2), symbols=["AAPL"])
trades = clean_trades(raw)

print(trades.execute().head())
```

## What it does

**Cleaning.** Merges the separate date and time columns into a timestamp, merges the root and suffix into a symbol, and applies the Holden and Jacobsen filters: quote conditions, cancelled quotes, crossed markets, withdrawn quotes, abnormal spreads, NBBO eligibility.

**NBBO construction.** Builds the official complete NBBO from the NBBO and quote files, or reads WRDS's own version.

**Metrics.** Quoted and effective spreads, realized spreads and price impacts, time-weighted and dollar-weighted averages, lock and cross indicators.

**Trade signing.** Lee-Ready, EMO and CLNV, plus BJZ for identifying retail trades.

## Where to start

- [Installation](getting-started/installation.md), which extra you need
- [Quick start](getting-started/quickstart.md), a worked example for each of the three paths
- [API reference](api/cleaning.md)

## A note on backends

Use **DuckDB** for local work. Ibis 12's polars backend implements no window functions at all, and much of PyTAQ depends on them, so the `polars` extra cannot run the full pipeline.
