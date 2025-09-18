# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

PyTAQ is a Python module for processing NYSE TAQ (Trade and Quote) data using Ibis framework for cross-platform data manipulation. The project is currently undergoing a refactoring from pandas to Ibis (branch: ibis).

## Common Commands

### Development Setup
```bash
# Install dependencies using uv
uv sync

# Install development dependencies
uv sync --group dev
```

### Testing
```bash
# Run all tests
pytest

# Run specific test file
pytest pytaq/extract/test_quotes.py
pytest pytaq/metrics/test_averages.py
pytest pytaq/utils/test_time_to_sql.py
```

### Code Quality
```bash
# Format code
ruff format

# Lint code
ruff check

# Fix linting issues
ruff check --fix
```

### Documentation
```bash
# Build documentation (MkDocs)
mkdocs build

# Serve documentation locally
mkdocs serve
```

## Architecture Overview

The codebase is organized into four main modules:

### 1. Extract (`pytaq/extract/`)
- **Purpose**: Extract and load raw TAQ data from various sources
- **Key files**:
  - `common.py`: Core utilities for datetime merging, symbol handling, and table operations using Ibis
  - `quotes.py`, `trades.py`, `nbbo.py`, `official_nbbo.py`: Data type-specific extraction logic
  - `postgresql.py`: Database connection and data loading utilities

### 2. Cleaning (`pytaq/cleaning/`)
- **Purpose**: Clean and standardize extracted TAQ data
- **Structure**: Mirrors extract module with corresponding cleaning functions for each data type
- **Key pattern**: Uses Ibis expressions for data transformations

### 3. Metrics (`pytaq/metrics/`)
- **Purpose**: Calculate financial metrics from cleaned TAQ data
- **Key modules**:
  - `averages.py`: Weighted and simple averages computation
  - `effective_spreads.py`, `quoted_spreads.py`: Spread calculations
  - `locks_crosses.py`: Market quality metrics
  - `rs_and_pi.py`: Realized spread and price impact metrics
  - `signs.py`: Trade classification

### 4. Utils (`pytaq/utils/`)
- **Purpose**: Common utilities and helper functions
- **Key files**:
  - `time_to_sql.py`: Time conversion utilities for database operations
  - `float_approx.py`: Floating-point approximation utilities

## Technical Notes

### Ibis Framework Integration
- All data operations use Ibis expressions for cross-platform compatibility
- Common pattern: functions accept and return `ibis.Table` objects
- Type hints use `TYPE_CHECKING` pattern for Ibis table types

### Code Conventions
- Uses f-strings for string formatting
- Type hints throughout codebase
- Comprehensive docstrings following Google style
- Error handling with descriptive context
- Ruff for code formatting and linting (configured in pyproject.toml)

### Dependencies
- **Core**: `ibis-framework` with DuckDB, Polars, and PostgreSQL backends
- **Dev**: `pytest`, `jupyter`, `polars`, `pyarrow`, `python-dotenv`
- **Package management**: Uses `uv` for dependency resolution and virtual environments

### Current State
The project is in active refactoring (ibis branch) transitioning from pandas-based operations to Ibis framework for improved performance and cross-platform data processing capabilities.