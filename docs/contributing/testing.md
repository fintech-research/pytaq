# Testing Guidelines

PyTAQ maintains a comprehensive test suite to ensure code quality and reliability. Currently at **75% code coverage** with **79 passing tests**.

## Running Tests

### Basic Test Execution

```bash
# Run all tests
pytest

# Run with verbose output
pytest -v

# Run specific test file
pytest pytaq/metrics/test_signs.py

# Run specific test
pytest pytaq/metrics/test_signs.py::test_sign_bjz_nasdaq_buy
```

### Coverage Reports

```bash
# Run with coverage
pytest --cov=pytaq

# With detailed missing lines report
pytest --cov=pytaq --cov-report=term-missing

# Generate HTML coverage report
pytest --cov=pytaq --cov-report=html

# Open HTML report
open htmlcov/index.html
```

### Test Filtering

```bash
# Run tests matching a pattern
pytest -k "bjz"

# Skip slow tests
pytest -m "not slow"

# Stop on first failure
pytest -x

# Show local variables on failure
pytest -l
```

## Writing Tests

### Test Structure

Tests should mirror the package structure:

```
pytaq/
├── metrics/
│   ├── signs.py
│   └── test_signs.py      # Tests for signs.py
├── cleaning/
│   ├── quotes.py
│   └── test_quotes.py     # Tests for quotes.py
```

### Basic Test Template

```python
import ibis
import pandas as pd
import pytest

from .module_name import function_to_test


@pytest.fixture
def con():
    """Create an in-memory DuckDB connection for testing."""
    return ibis.connect("duckdb://:memory:")


def test_function_basic(con):
    """Test basic functionality of function."""
    # Arrange - Set up test data
    data = pd.DataFrame({
        "column1": [1, 2, 3],
        "column2": [4, 5, 6],
    })
    table = con.create_table("test", data)

    # Act - Execute the function
    result = function_to_test(table).execute()

    # Assert - Verify results
    assert result["column1"].iloc[0] == 1
    assert len(result) == 3
```

### Test Data Best Practices

1. **Use pandas DataFrames** for DuckDB compatibility:

```python
# Good - explicit types
data = pd.DataFrame({
    "date": [datetime.date(2023, 1, 15)],
    "sym_suffix": pd.Series([None], dtype="string"),
    "price": [100.50],
})
```

2. **Convert date integers** to date objects:

```python
# Don't use integers
"DATE": [20230115]  # ❌

# Use datetime.date
"DATE": [datetime.date(2023, 1, 15)]  # ✓
```

3. **Use explicit dtype for nullable strings**:

```python
# For columns that can be None
"sym_suffix": pd.Series([None, None], dtype="string")
```

### Testing Ibis Expressions

```python
def test_ibis_expression(con):
    """Test Ibis column operations."""
    data = pd.DataFrame({
        "price": [100.0, 200.0],
        "quantity": [10, 20],
    })
    table = con.create_table("test", data)

    # Test expression
    result = table.mutate(
        total=table.price * table.quantity
    ).execute()

    assert result["total"].iloc[0] == 1000.0
    assert result["total"].iloc[1] == 4000.0
```

### Testing Edge Cases

Always test edge cases:

```python
def test_function_with_nulls(con):
    """Test function handles null values correctly."""
    data = pd.DataFrame({
        "value": [1.0, None, 3.0],
    })
    table = con.create_table("test", data)

    result = function_to_test(table).execute()

    # Verify null handling
    assert pd.isna(result["processed"].iloc[1])


def test_function_with_empty_data(con):
    """Test function handles empty data."""
    data = pd.DataFrame({"value": []})
    table = con.create_table("test", data)

    result = function_to_test(table).execute()

    assert len(result) == 0
```

### Testing Numerical Results

Use appropriate comparison for floating point:

```python
# For exact equality (integers)
assert result["count"].iloc[0] == 42

# For floating point with tolerance
assert abs(result["average"].iloc[0] - 100.5) < 1e-6

# Using numpy testing
import numpy.testing as npt
npt.assert_almost_equal(result["value"].iloc[0], 100.5, decimal=6)
```

### Boolean Comparisons

Don't use `is` for boolean comparisons with pandas/numpy:

```python
# Wrong ❌
assert result["flag"].iloc[0] is True

# Correct ✓
assert result["flag"].iloc[0] == True

# Better - explicit boolean check
assert result["flag"].iloc[0]
```

## Test Organization

### Use Descriptive Names

```python
# Good ✓
def test_sign_bjz_nasdaq_buy():
    """Test BJZ sign classification for NASDAQ buy trades."""

# Less descriptive ❌
def test_bjz():
    """Test BJZ."""
```

### Group Related Tests

```python
class TestQuoteCleaning:
    """Tests for quote cleaning functions."""

    def test_filter_withdrawn_quotes(self, con):
        """Test filtering withdrawn quotes."""
        ...

    def test_filter_crossed_markets(self, con):
        """Test filtering crossed markets."""
        ...
```

### Use Fixtures for Common Setup

```python
@pytest.fixture
def sample_quotes(con):
    """Create sample quote data for testing."""
    data = pd.DataFrame({
        "symbol": ["AAPL", "MSFT"],
        "bid": [100.0, 200.0],
        "ask": [100.5, 200.5],
    })
    return con.create_table("quotes", data)


def test_with_fixture(sample_quotes):
    """Test using the fixture."""
    result = sample_quotes.execute()
    assert len(result) == 2
```

## Known Issues

### Skipped Tests

Some tests are skipped due to Ibis API compatibility:

```python
@pytest.mark.skip(reason="Window API issue - partition_by parameter")
def test_with_window_function(con):
    """This test is skipped until Ibis API is fixed."""
    ...
```

## Coverage Goals

- **Minimum**: 70% overall coverage
- **Target**: 80% overall coverage
- **Critical modules**: 90%+ coverage (cleaning, metrics)

Current coverage by module:

- ✅ `cleaning/quotes.py`: 100%
- ✅ `cleaning/trades.py`: 100%
- ✅ `metrics/locks_crosses.py`: 100%
- ⚠️ `metrics/signs.py`: 66%
- ⚠️ `metrics/quoted_spreads.py`: 57%
- ❌ `cleaning/nbbo.py`: 0%

## Continuous Integration

Tests run automatically on:

- Every push to GitHub
- Every pull request
- Before merging to main branch

## Best Practices

1. **Test one thing at a time** - Each test should verify one specific behavior
2. **Use meaningful assertions** - Make it clear what is being tested
3. **Keep tests independent** - Tests should not depend on each other
4. **Clean up resources** - Use fixtures for setup/teardown
5. **Test the interface, not implementation** - Focus on public API behavior
6. **Write tests first** - Consider TDD for new features

## Common Patterns

### Testing Data Transformations

```python
def test_merge_symbol(con):
    """Test symbol root and suffix merging."""
    data = pd.DataFrame({
        "sym_root": ["BRK", "AAPL"],
        "sym_suffix": ["A", None],
    })
    table = con.create_table("test", data)

    result = merge_symbol(table).execute()

    assert result["symbol"].iloc[0] == "BRK A"
    assert result["symbol"].iloc[1] == "AAPL"
```

### Testing Filters

```python
def test_filter_by_condition(con):
    """Test conditional filtering."""
    data = pd.DataFrame({
        "value": [1, 2, 3, 4, 5],
    })
    table = con.create_table("test", data)

    result = table.filter(table.value > 2).execute()

    assert len(result) == 3
    assert list(result["value"]) == [3, 4, 5]
```

## Resources

- [pytest documentation](https://docs.pytest.org/)
- [pytest-cov plugin](https://pytest-cov.readthedocs.io/)
- [Ibis testing examples](https://ibis-project.org/how-to/testing)
