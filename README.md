# PyTAQ

Process NYSE TAQ trade and quote data with [Ibis](https://ibis-project.org/).

PyTAQ implements the standard cleaning and liquidity-metric pipeline for TAQ data, following [Holden and Jacobsen (2014)](https://doi.org/10.1111/jofi.12127). Because it is written against Ibis rather than a single engine, the same code runs on the WRDS postgres server and on local copies of the data.

## Installation

The Ibis backends are optional; which one you need depends on where your data lives.

```bash
pip install 'pytaq[duckdb]'      # local TAQ files
pip install 'pytaq[postgres]'    # WRDS postgres server
pip install 'pytaq[all]'         # both
```

Python 3.13 or later.

## Usage

Three supported paths. Only opening the data differs; cleaning and metrics are identical in all three.

1. **On the WRDS cloud**, against their postgres server
2. **Locally, remote data**, querying the WRDS postgres server
3. **Locally, local data**, against local TAQ files

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

print(day.execute())  # one row per symbol, the standard measures
```

`process_day` runs the standard Holden and Jacobsen pipeline: clean, match trades to quotes one millisecond back, sign, and aggregate. Every intermediate stage is on the returned object (`day.signed`, `day.effective_spreads`, and so on) if you need to inspect or extend it, and every underlying option is a keyword argument.

The stages are also available individually if you would rather assemble them yourself.

Nothing runs until `.execute()`. Ibis builds an expression and hands the whole thing to the engine.

## What it does

- **Cleaning** following Holden and Jacobsen: quote conditions, cancelled quotes, crossed markets, withdrawn quotes, abnormal spreads, NBBO eligibility. Every filter is a keyword argument
- **NBBO construction**, either from WRDS's official complete NBBO or rebuilt from the NBBO and quote files
- **Metrics**: quoted and effective spreads, realized spreads and price impacts, time- and dollar-weighted averages, lock and cross indicators
- **Trade signing**: Lee-Ready, EMO, CLNV, and BJZ for identifying retail trades

## Backends

Use DuckDB for local work. Ibis 12's polars backend implements no window functions, and much of PyTAQ depends on them, so the `polars` extra cannot run the full pipeline.

## Documentation

Full documentation is built with MkDocs:

```bash
uv run mkdocs serve
```

## Development

```bash
git clone https://github.com/fintech-research/pytaq.git
cd pytaq
uv sync
uv run pre-commit install
uv run pytest
```

There is no CI; pre-commit is the gate. It runs `ruff` and `ty`.

## Status

The package is in active development and the API may still change. `TO_VERIFY.md` lists claims that need real TAQ data to confirm.

## License

BSD 3-Clause. See [LICENSE](LICENSE).
