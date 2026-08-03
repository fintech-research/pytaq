# PyTAQ

Process NYSE TAQ trade and quote data with [Ibis](https://ibis-project.org/).

PyTAQ implements the standard cleaning and liquidity-metric pipeline for TAQ data, following [Holden and Jacobsen (2014)](https://doi.org/10.1111/jofi.12127). Because it is written against Ibis rather than a single engine, the same code runs on the WRDS postgres server and on local copies of the data.

## Three ways to use it

| | What it is | Install | Good for |
|---|---|---|---|
| On the WRDS cloud | Run on WRDS's own machines, against their postgres server | `pytaq[postgres]` | Anything, the data is local to the compute |
| Local, remote data | Run on your laptop, query the WRDS postgres server | `pytaq[postgres]` | **Small queries only** |
| Local, local data | Run on your laptop, against local TAQ files | `pytaq[duckdb]` | Bulk work |

Only the first step differs. Cleaning and metrics are identical in all three.

A word of warning on the middle path: querying the WRDS server from your own machine runs the as-of joins and window functions remotely, over the network, on a shared server. It is fine for a few symbols or part of a day and slow for anything more. See [Performance](guide/performance.md) for the pattern to use instead.

## A short example

```python
import datetime

from pytaq import local, process_day

con = local.connect()
date = datetime.date(2020, 1, 2)

day = process_day(
    local.get_trades(con, "data/", date, symbols=["AAPL"]),
    local.get_official_complete_nbbo(con, "data/", date, symbols=["AAPL"]),
    date=date,
)

print(day.execute())  # one row per symbol
```

`process_day` runs the whole Holden and Jacobsen pipeline: clean, match trades to the quote in force a millisecond earlier, sign, and aggregate. Every intermediate stage is on the returned object, and every option is a keyword argument. The individual functions remain available if you would rather assemble it yourself.

## What it does

**Cleaning.** Merges the separate date and time columns into a timestamp, merges the root and suffix into a symbol, and applies the Holden and Jacobsen filters: quote conditions, cancelled quotes, crossed markets, withdrawn quotes, abnormal spreads, NBBO eligibility.

**NBBO construction.** Builds the official complete NBBO from the NBBO and quote files, or reads WRDS's own version.

**Metrics.** Quoted and effective spreads, realized spreads and price impacts, time-weighted and dollar-weighted averages, lock and cross indicators.

**Trade signing.** Lee-Ready, EMO and CLNV, plus BJZ for identifying retail trades.

## Where to start

- [Installation](getting-started/installation.md), which extra you need
- [Quick start](getting-started/quickstart.md), a worked example for each of the three paths
- [Methodology and defaults](guide/methodology.md), every choice PyTAQ makes and why
- [Performance](guide/performance.md), which path to use for what
- [Troubleshooting](guide/troubleshooting.md)
- [Holden and Jacobsen conformance](reference/holden-jacobsen.md), where PyTAQ matches the paper and where it deliberately does not

## A note on backends

Use **DuckDB** for local work. Ibis 12's polars backend implements no window functions at all, and much of PyTAQ depends on them, so the `polars` extra cannot run the full pipeline.
