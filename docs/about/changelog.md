# Changelog

All notable changes to PyTAQ are documented here.

The format follows [Keep a Changelog](https://keepachangelog.com/en/1.0.0/), and the project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

Completion of the pandas-to-Ibis refactor and everything needed to publish.

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
