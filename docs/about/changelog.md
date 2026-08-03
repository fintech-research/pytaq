# Changelog

All notable changes to PyTAQ are documented here.

The format follows [Keep a Changelog](https://keepachangelog.com/en/1.0.0/), and the project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.4.0] - 2026-08-03

Four corrections found by implementing the same pipeline in SAS and reading Holden and Jacobsen's own September 2013 code line by line. Three change published numbers.

### Breaking

- **Time in force is now a duration in seconds, not a count of second boundaries.** `compute_quote_inforce` used `delta(unit="second")`, which truncates both sides to the second before subtracting, so a quote replaced 900ms later scored 0 and one replaced 200ms later scored 1 if it straddled a boundary. DTAQ quote lives are overwhelmingly sub-second, so most quotes carried zero weight and every time-weighted quoted spread was driven by the minority that straddled a boundary. H&J difference a fractional-second time (`inforce = abs(dif(InterpolatedTime))`), which is what this now returns. **Time-weighted quoted spreads change for every symbol-day**
- **`process_day` now excludes locked and crossed quotes from quoted spreads, and drops quotes before the trade window before time-weighting them.** It previously did neither: the lock and cross filter lived in `compute_weighted_spreads`, which `process_day` never calls, and one window was used throughout. H&J do both, in that order. `quoted_spread_start_time=None` and `exclude_locked_crossed=False` restore the old behaviour
- **Cleaned tables keep `timestamp_ns`.** `TRADES_COLS_CLEAN` and `OFF_NBBO_COLS_CLEAN` dropped it, so inside `process_day` the one-millisecond lag, the T+horizon match and the tick-test ordering all silently fell back to the microsecond `timestamp`, contradicting the documented nanosecond precision. Matches can now shift by up to a microsecond, so effective and realized spreads change on trades near a quote update

### Fixed

- **Weighted averages guard a zero denominator.** DuckDB returns null for a float division by zero while postgres raises `division_by_zero`, so an all-null measure or an all-zero weight column failed on one backend and not the other

### Changed

- The conformance table records two things that reading the published code corrected: H&J's price impact is `ES$ - RS$` with an **unsigned** effective spread, which diverges from PyTAQ's `2·D·(M₅ - M)` for EMO and CLNV on trades the tick test decided, and their weighted-average denominators sum the full weight column, which PyTAQ deliberately does not follow

## [0.3.0] - 2026-08-03

Completion of the pandas-to-Ibis refactor, validation against real WRDS data, and everything needed to publish.

### Breaking

- **Output columns are now snake_case throughout.** `DollarEffectiveSpread` becomes `effective_spread_dollar`, `BuySellLR` becomes `buysell_lr`, `DollarRealizedSpread_LR5min` becomes `realized_spread_dollar_lr_5min`, and the `_SW` / `_DW` weighting suffixes become `_share_weighted` / `_dollar_weighted`. Three naming conventions coexisted; settling on one before publishing is cheaper than after
- **Percent measures now follow Holden and Jacobsen by default**, dividing the dollar measure by the reference midpoint rather than taking a log difference. `percent_method="log"` restores the previous behaviour
- **Trades are matched to the NBBO one millisecond earlier**, as H&J specify, rather than contemporaneously. `lag=timedelta(0)` restores the previous behaviour
- **Quote filters neutralise a side rather than deleting the row.** The `delete_*` arguments are renamed `exclude_*`, and `filter_withdrawned_quotes` becomes `neutralize_withdrawn_quotes`
- **`sign_tick` returns a table** rather than a column
- **`requires-python` is now `>=3.13`**

### Added

- `process_day()`, running the standard Holden and Jacobsen pipeline for one date in a single call and returning every intermediate stage. The stage ordering carries constraints that are easy to get subtly wrong and produce plausible-looking wrong numbers

- `pytaq.local`, reading TAQ data from local Parquet or CSV files through DuckDB. This is the third supported usage path and had no support before
- A public API: `pytaq.__all__`, `__all__` on every subpackage, and `pytaq.__version__` from the installed metadata. All `__init__.py` files were previously empty
- Optional extras (`duckdb`, `polars`, `postgres`, `all`) so the backend you install matches how you use the package
- `pytaq.tables`, the daily table naming shared by the postgres and local paths
- Build backend and full package metadata. The project could not be built at all before
- `ruff`, `ty` and `pre-commit` configuration, run locally
- `py.typed`, so downstream type checkers actually use the annotations. The package advertised `Typing :: Typed` without shipping the marker
- `TO_VERIFY.md` for claims that need real TAQ data to confirm
- End-to-end tests covering a full local-files workflow, and first tests for `cleaning/nbbo.py`, `merge_trades_official_nbbo`, `sign_tick` and `sign_trades`

### Fixed

- **`merge_quotes_nbbo` returned about 3% of the rows it should**, and the wrong ones. `ibis.row_number()` is zero-based, so filtering on rank 1 kept the second-highest sequence number at each timestamp and dropped every timestamp holding a single quote. On one day of AAPL it returned 18,651 rows where 550,307 were correct. Only a self-union was ever tested, which masks the off-by-one exactly
- **`clean_nbbo` and `clean_quote_table` emitted different schemas**, so the documented NBBO reconstruction raised `RelationError`. `clean_nbbo` also omitted `qu_seqnum`, which the dedup ranks on

- **Cancelled-quote filters silently dropped every quote with a null `qu_cancel`.** `qu_cancel != "B"` is NULL in SQL for a null flag, not true. On a traced fixture `clean_nbbo` returned 0 rows from 4
- **`filter_changes_only` dropped the opening quote of every symbol.** Comparing against `lag()` with `!=` yields NULL on the first row of each group. Now uses null-safe comparison
- **`ibis.window(partition_by=)` does not exist**, so no trade sign classifier ran at all. The parameter is `group_by`
- **The tick-test forward fill latched to +1.** It was a cumulative max over `{-1, +1}`, which is not a forward fill
- **`asof_join` was called with `by=` and `suffixes=`**, neither of which exists, and without the required `on=`, so the trade-to-quote match raised `TypeError`
- `compute_quote_inforce` computed a difference against a bare column over a rows window rather than a lead, and ignored its `inforce_col` argument
- `sign_tick` built its expression against a re-sorted copy of the input, which Ibis rejects
- `pytaq.wrds` annotated a return type that does not exist in Ibis 12, and could not be imported

### Changed

- Ibis 9.5 to 12. Among other things this replaces `psycopg2`, which has no macOS wheels, with `psycopg` 3, so `uv sync` works on macOS
- `sign_tick` returns a table rather than a column, because the forward fill needs a materialised intermediate. It also now exposes the tick direction as an output column
- Documentation rewritten against the actual API. The previous version documented functions that never existed
- `requires-python` raised to `>=3.13`. Ibis 12's `pyarrow<18` constraint is gone, and targeting one modern version keeps the annotations simple

### Removed

- The legacy raw-SQL extraction path (`pytaq.extract`). It duplicated the Ibis pipeline, was broken by construction, and depended on the undeclared `wrds` package
- `jupyter` and other unused development dependencies
