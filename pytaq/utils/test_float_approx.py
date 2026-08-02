import ibis
import pandas as pd
import pytest

from .float_approx import (
    DEFAULT_ATOL,
    correct_float_approx,
    float_equal,
    float_zero,
)


@pytest.fixture
def con():
    """Create an in-memory DuckDB connection for testing."""
    return ibis.connect("duckdb://:memory:")


def test_float_equal_basic(con):
    """Test basic float equality comparison."""
    data = {
        "val1": [1.0, 2.0, 3.0000001, 4.5],
        "val2": [1.0, 2.0000001, 3.0, 4.5000001],
    }
    table = con.create_table("test", data)

    result = table.mutate(equal=float_equal(table.val1, table.val2)).execute()

    # First row: exactly equal
    assert result["equal"].iloc[0]
    # Second row: within tolerance
    assert result["equal"].iloc[1]
    # Third row: within tolerance
    assert result["equal"].iloc[2]
    # Fourth row: within tolerance
    assert result["equal"].iloc[3]


def test_float_equal_not_equal(con):
    """Test float equality when values are not equal."""
    data = {
        "val1": [1.0, 2.0, 3.0],
        "val2": [1.5, 2.1, 3.0001],
    }
    table = con.create_table("test", data)

    result = table.mutate(equal=float_equal(table.val1, table.val2)).execute()

    # All rows should be False (outside tolerance)
    assert not result["equal"].iloc[0]
    assert not result["equal"].iloc[1]
    assert not result["equal"].iloc[2]


def test_float_equal_custom_tolerance(con):
    """Test float equality with custom tolerance."""
    data = {
        "val1": [1.0, 2.0],
        "val2": [1.01, 2.01],
    }
    table = con.create_table("test", data)

    # With default tolerance (0.000001), should be False
    result_default = table.mutate(
        equal=float_equal(table.val1, table.val2, atol=DEFAULT_ATOL)
    ).execute()
    assert not result_default["equal"].iloc[0]

    # With larger tolerance (0.1), should be True
    result_custom = table.mutate(
        equal=float_equal(table.val1, table.val2, atol=0.1)
    ).execute()
    assert result_custom["equal"].iloc[0]


def test_float_zero_basic(con):
    """Test float zero comparison."""
    data = {
        "val": [0.0, 0.0000001, -0.0000001, 0.1, -0.1, 1.0],
    }
    table = con.create_table("test", data)

    result = table.mutate(is_zero=float_zero(table.val)).execute()

    # First three should be True (within tolerance of zero)
    assert result["is_zero"].iloc[0]
    assert result["is_zero"].iloc[1]
    assert result["is_zero"].iloc[2]
    # Last three should be False
    assert not result["is_zero"].iloc[3]
    assert not result["is_zero"].iloc[4]
    assert not result["is_zero"].iloc[5]


def test_float_zero_custom_tolerance(con):
    """Test float zero comparison with custom tolerance."""
    data = {
        "val": [0.05, -0.05, 0.0001],
    }
    table = con.create_table("test", data)

    # With default tolerance, should be False
    result_default = table.mutate(is_zero=float_zero(table.val)).execute()
    assert not result_default["is_zero"].iloc[0]

    # With larger tolerance, should be True
    result_custom = table.mutate(is_zero=float_zero(table.val, atol=0.1)).execute()
    assert result_custom["is_zero"].iloc[0]
    assert result_custom["is_zero"].iloc[1]


def test_correct_float_approx_basic(con):
    """Test correcting values when two columns are approximately equal."""
    data = {
        "series": [10.0, 20.0, 30.0, 40.0],
        "val1": [1.0, 2.0, 3.0, 4.0],
        "val2": [1.0, 2.1, 3.0000001, 4.5],
    }
    table = con.create_table("test", data)

    result = table.mutate(
        corrected=correct_float_approx(table.series, table.val1, table.val2)
    ).execute()

    # First row: val1 == val2, should be null
    assert pd.isna(result["corrected"].iloc[0])
    # Second row: val1 != val2, should keep original value
    assert result["corrected"].iloc[1] == 20.0
    # Third row: val1 ~= val2 (within tolerance), should be null
    assert pd.isna(result["corrected"].iloc[2])
    # Fourth row: val1 != val2, should keep original value
    assert result["corrected"].iloc[3] == 40.0


def test_correct_float_approx_custom_tolerance(con):
    """Test correcting with custom tolerance."""
    data = {
        "series": [10.0, 20.0],
        "val1": [1.0, 2.0],
        "val2": [1.01, 2.01],
    }
    table = con.create_table("test", data)

    # With default tolerance, should keep values
    result_default = table.mutate(
        corrected=correct_float_approx(table.series, table.val1, table.val2)
    ).execute()
    assert result_default["corrected"].iloc[0] == 10.0

    # With larger tolerance, should set to null
    result_custom = table.mutate(
        corrected=correct_float_approx(table.series, table.val1, table.val2, atol=0.1)
    ).execute()
    assert pd.isna(result_custom["corrected"].iloc[0])


def test_float_equal_with_nan(con):
    """Test float equality with NaN values."""
    data = {
        "val1": [float("nan"), 1.0, float("nan")],
        "val2": [float("nan"), 1.0, 2.0],
    }
    table = con.create_table("test", data)

    result = table.mutate(equal=float_equal(table.val1, table.val2)).execute()

    # NaN == NaN should be True (because equal_nan=True)
    assert result["equal"].iloc[0]
    # 1.0 == 1.0 should be True
    assert result["equal"].iloc[1]
    # NaN != 2.0 should be False (or null)
    # Test isna first: `not pd.NA` raises, so the order here matters.
    nan_vs_number = result["equal"].iloc[2]
    assert pd.isna(nan_vs_number) or not nan_vs_number
