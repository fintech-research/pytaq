# Changelog

All notable changes to PyTAQ will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added
- Comprehensive MkDocs documentation with Material theme
- BJZ retail trade classification algorithm implementation
- 20 new tests improving coverage to 75%
- Support for multiple trade sign classification algorithms (LR, EMO, CLNV, BJZ)
- Tests for realized spreads and price impact calculations
- Tests for quoted spreads and weighted averages

### Changed
- Refactoring from pandas to Ibis framework for cross-platform compatibility
- Improved test coverage from 68% to 75%
- Enhanced code documentation with Google-style docstrings

### Fixed
- filter_locks_crosses() now correctly filters both locks AND crosses
- sign_tick() forward fill logic using Ibis window functions
- filter_by_time() time-to-seconds conversion for numeric comparison
- merge_datetime() implementation replacing non-existent Ibis function
- Correct Ibis rename() syntax ({new_name: old_name} mapping)
- Test data setup using pandas DataFrames for DuckDB compatibility

## [Previous Versions]

For historical changes, see the [commit history](https://github.com/vincentgregoire/pytaq/commits/ibis).

## Migration Guide

### Pandas to Ibis

The current refactoring replaces pandas with Ibis. Key changes:

**Before (pandas)**:
```python
df = pd.read_csv("quotes.csv")
df["spread"] = df["ask"] - df["bid"]
result = df[df["spread"] < 5.0]
```

**After (Ibis)**:
```python
con = ibis.connect("duckdb://")
table = con.read_csv("quotes.csv")
result = table.mutate(spread=table.ask - table.bid).filter(table.spread < 5.0).execute()
```

### API Changes

- Functions now accept and return `ibis.Table` instead of `pandas.DataFrame`
- Use `.execute()` to materialize results
- Column operations use Ibis expressions instead of pandas syntax
