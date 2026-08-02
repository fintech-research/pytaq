# Code Style Guide

PyTAQ follows modern Python best practices and uses automated tools to maintain code quality.

## Pre-commit

There is no CI at the moment, so pre-commit is the gate. Install the hooks once after cloning:

```bash
uv sync
uv run pre-commit install
```

From then on the hooks run on every commit. To run them over the whole repository:

```bash
uv run pre-commit run --all-files
```

The hooks are Ruff (lint and format), `ty`, and a few whitespace and file checks. They are configured in `.pre-commit-config.yaml`.

## Ruff

PyTAQ uses [Ruff](https://github.com/astral-sh/ruff) for both linting and formatting.

```bash
# Format code
uv run ruff format

# Check for issues
uv run ruff check

# Auto-fix what can be fixed
uv run ruff check --fix
```

Ruff is configured under `[tool.ruff]` in `pyproject.toml`. The enabled rule families are pycodestyle, pyflakes, isort, pyupgrade, bugbear, simplify, comprehensions, pep8-naming, pytest-style and Ruff's own rules.

Note that `ruff format` also formats Python code blocks inside the Markdown files under `docs/`, so documentation examples stay consistent with the source.

## Type checking

PyTAQ uses [ty](https://github.com/astral-sh/ty):

```bash
uv run ty check
```

`ty` is configured under `[tool.ty]` in `pyproject.toml`. A few of its rules are deliberately switched off, and the reason is worth knowing before you turn them back on: nearly everything in this codebase is an Ibis expression, and Ibis builds its operators and column accessors dynamically. `ty` cannot follow that, so `invalid-argument-type`, `invalid-return-type` and `unsupported-operator` report noise rather than defects here.

What `ty` is good at on this codebase is call signatures and imports, and those rules are left on. They earn their keep: `ty` independently caught two real bugs that the test suite missed.

`pyproject.toml` also carries some narrowly scoped, temporary suppressions, each commented with the issue number that will remove it. They exist so the pre-commit hook stays usable while those bugs are still open. If you close one of those issues, delete its block.

## Python Style Guidelines

### General Principles

- Follow [PEP 8](https://peps.python.org/pep-0008/)
- Use meaningful variable names
- Keep functions focused and small
- Write self-documenting code with clear names
- Add comments for complex logic only

### Naming Conventions

```python
# Constants - UPPER_SNAKE_CASE
DEFAULT_CLNV_THRESHOLD = 0.3
HJ_MAX_SPREAD = 5.0


# Functions and variables - snake_case
def compute_effective_spreads(table, price_col):
    midpoint_value = (bid + ask) / 2
    return result


# Classes - PascalCase
class QuoteProcessor:
    pass


# Private/internal - prefix with underscore
def _internal_helper():
    pass


_private_constant = 10
```

### Imports

```python
# Standard library first
from datetime import date, datetime, time
from typing import TYPE_CHECKING, List, Union

# Third-party libraries
import ibis
import pandas as pd

# Local imports
from ..utils.float_approx import float_equal
from .locks_crosses import filter_locks_crosses

# Type checking imports
if TYPE_CHECKING:
    from ibis.expr.types import Column, Table
```

### Type Hints

Always use type hints for function signatures:

```python
def merge_symbol(
    table: "Table",
    sym_root_col: str = "sym_root",
    sym_suffix_col: str = "sym_suffix",
) -> "Table":
    """Merge symbol root and suffix columns.

    Args:
        table: Input table
        sym_root_col: Name of symbol root column
        sym_suffix_col: Name of symbol suffix column

    Returns:
        Table with merged 'symbol' column
    """
    ...
```

## Documentation

### Docstrings

Use Google-style docstrings:

```python
def compute_effective_spreads(
    table: "Table",
    timestamp_col: str = "timestamp",
    price_col: str = "price",
    filter_locks_crosses: bool = True,
) -> "Table":
    """Compute effective spreads from trade data.

    The effective spread measures the cost of immediate execution by
    comparing the trade price to the midpoint at the time of the trade.

    Args:
        table: Input table with trade data
        timestamp_col: Name of timestamp column
        price_col: Name of price column
        filter_locks_crosses: Whether to filter locked/crossed markets

    Returns:
        Table with effective spread measures added

    Examples:
        >>> spreads = compute_effective_spreads(trades)
        >>> result = spreads.execute()
        >>> print(result["eff_spread_dollar"].mean())

    Notes:
        - Dollar spread = 2 * sign * (price - midpoint)
        - Percent spread = 2 * sign * (log(price) - log(midpoint))
    """
    ...
```

### Module Docstrings

Every module should have a docstring:

```python
"""Trade sign classification algorithms.

This module implements various trade classification algorithms including:
- Lee-Ready (LR)
- EMO
- CLNV (Chakrabarty, Li, Nguyen, and Van Ness)
- BJZ (Boehmer, Jones, and Zhang) retail classification
"""
```

### Comments

```python
# Good comments explain WHY, not WHAT
# Calculate mid-price for quote comparison
midpoint = (bid + ask) / 2

# Bad comments restate the code
# Divide the sum of bid and ask by 2
midpoint = (bid + ask) / 2
```

## Code Organization

### File Structure

```python
"""Module docstring."""

# Imports
from typing import TYPE_CHECKING
import ibis

# Constants
DEFAULT_THRESHOLD = 0.5

# Type checking imports
if TYPE_CHECKING:
    from ibis.expr.types import Table


# Functions (in logical order)
def public_function():
    """Public API function."""
    ...


def _internal_function():
    """Internal helper function."""
    ...
```

### Function Length

- Keep functions under 50 lines when possible
- Extract complex logic into helper functions
- One function = one responsibility

```python
# Good - focused function
def filter_by_time(table, start_time, end_time):
    """Filter table by time range."""
    return table.filter(
        table.time_m.between(_time_to_seconds(start_time), _time_to_seconds(end_time))
    )


def _time_to_seconds(t):
    """Convert time to seconds since midnight."""
    return t.hour * 3600 + t.minute * 60 + t.second
```

## Ibis-Specific Guidelines

### Column Operations

```python
# Good - use Ibis expressions
result = table.mutate(
    spread=table.ask - table.bid, midpoint=(table.ask + table.bid) / 2
)

# Avoid - don't materialize unnecessarily
data = table.execute()  # Don't execute early
data["spread"] = data["ask"] - data["bid"]
```

### Lazy Evaluation

```python
# Good - chain operations, execute once
result = (
    table.filter(table.price > 0)
    .mutate(log_price=table.price.log())
    .group_by("symbol")
    .agg(avg_log_price=table.log_price.mean())
    .execute()
)

# Less efficient - multiple executions
filtered = table.filter(table.price > 0).execute()
with_log = filtered.mutate(log_price=filtered.price.log()).execute()
result = with_log.group_by("symbol").agg(...).execute()
```

### Null Handling

```python
# Explicit null handling
result = condition.ifelse(value, ibis.null().cast("int8"))

# Check for nulls
is_null = column.isnull()
not_null = column.notnull()
```

## Error Handling

### Validation

```python
def function_with_validation(table, column_name):
    """Function with input validation."""
    if column_name not in table.columns:
        raise ValueError(f"Column '{column_name}' not found in table")

    if not isinstance(table, ibis.expr.types.Table):
        raise TypeError("Expected Ibis table")

    return table
```

### Informative Errors

```python
# Good - helpful error message
raise ValueError(
    f"Invalid exchange code: {ex}. Expected one of: {', '.join(VALID_EXCHANGES)}"
)

# Bad - unclear error
raise ValueError("Invalid exchange")
```

## Testing Standards

### Test Naming

```python
# Good test names
def test_bjz_classifies_buy_correctly():
    """Test BJZ correctly identifies buy trades."""
    ...


def test_filter_handles_empty_table():
    """Test filter returns empty table for empty input."""
    ...
```

### Test Organization

```python
def test_function_name():
    """One-line description of what is tested."""
    # Arrange - set up test data
    data = create_test_data()

    # Act - execute function
    result = function_under_test(data)

    # Assert - verify results
    assert result == expected
```

## Pre-Commit Checklist

Before committing code:

- [ ] Run `ruff format` to format code
- [ ] Run `ruff check --fix` to fix linting issues
- [ ] Run `pytest` to ensure all tests pass
- [ ] Add tests for new functionality
- [ ] Update docstrings and documentation
- [ ] Verify type hints are present
- [ ] Check that changes follow this style guide

## Tools

- **Ruff**: Linting and formatting
- **pytest**: Testing
- **mkdocs**: Documentation
- **mypy**: Type checking (optional)

## Resources

- [PEP 8 - Style Guide for Python Code](https://peps.python.org/pep-0008/)
- [PEP 257 - Docstring Conventions](https://peps.python.org/pep-0257/)
- [Google Python Style Guide](https://google.github.io/styleguide/pyguide.html)
- [Ruff Documentation](https://docs.astral.sh/ruff/)
- [Ibis Documentation](https://ibis-project.org/)
