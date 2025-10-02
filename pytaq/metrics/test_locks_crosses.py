import ibis
import pytest

from .locks_crosses import (
    crossed_rows,
    filter_locks_crosses,
    locked_crossed_rows,
    locked_rows,
)


@pytest.fixture
def con():
    """Create an in-memory DuckDB connection for testing."""
    return ibis.connect("duckdb://:memory:")


def test_locked_rows_basic(con):
    """Test identification of locked markets (bid == ask)."""
    data = {
        "bid": [10.0, 11.0, 12.0, 13.0],
        "ask": [10.0, 11.5, 12.0000001, 14.0],  # 1st and 3rd are locked
    }
    table = con.create_table("test", data)

    result = table.mutate(is_locked=locked_rows(table.ask, table.bid)).execute()

    # First row: exact match
    assert result["is_locked"].iloc[0] == True
    # Second row: different
    assert result["is_locked"].iloc[1] == False
    # Third row: within tolerance
    assert result["is_locked"].iloc[2] == True
    # Fourth row: different
    assert result["is_locked"].iloc[3] == False


def test_crossed_rows_basic(con):
    """Test identification of crossed markets (ask < bid)."""
    data = {
        "bid": [10.0, 11.0, 12.0, 13.0],
        "ask": [9.0, 11.5, 12.5, 12.5],  # 1st and 4th are crossed
    }
    table = con.create_table("test", data)

    result = table.mutate(is_crossed=crossed_rows(table.ask, table.bid)).execute()

    # First row: ask < bid (crossed)
    assert result["is_crossed"].iloc[0] == True
    # Second row: normal
    assert result["is_crossed"].iloc[1] == False
    # Third row: normal
    assert result["is_crossed"].iloc[2] == False
    # Fourth row: ask < bid (crossed)
    assert result["is_crossed"].iloc[3] == True


def test_locked_crossed_rows_basic(con):
    """Test identification of locked or crossed markets."""
    data = {
        "bid": [10.0, 11.0, 12.0, 13.0, 14.0],
        "ask": [9.0, 11.0, 12.5, 12.5, 15.0],
    }
    table = con.create_table("test", data)

    result = table.mutate(
        is_lock_or_cross=locked_crossed_rows(table.ask, table.bid)
    ).execute()

    # First: crossed (ask < bid)
    assert result["is_lock_or_cross"].iloc[0] == True
    # Second: locked (ask == bid)
    assert result["is_lock_or_cross"].iloc[1] == True
    # Third: normal
    assert result["is_lock_or_cross"].iloc[2] == False
    # Fourth: crossed (ask < bid)
    assert result["is_lock_or_cross"].iloc[3] == True
    # Fifth: normal
    assert result["is_lock_or_cross"].iloc[4] == False


def test_filter_locks_crosses(con):
    """Test filtering of locked/crossed rows."""
    data = {
        "id": [1, 2, 3, 4, 5],
        "bid": [10.0, 11.0, 12.0, 13.0, 14.0],
        "ask": [9.0, 11.0, 12.5, 12.5, 15.0],
    }
    table = con.create_table("test", data)

    # Filter out locked/crossed rows
    result = filter_locks_crosses(table, table.ask, table.bid).execute()

    # Should keep rows where ask > bid (not locked/crossed)
    # Rows 3 and 5 should remain
    assert len(result) == 2
    assert 3 in result["id"].values
    assert 5 in result["id"].values


def test_locked_rows_with_floats(con):
    """Test locked rows detection with floating point numbers."""
    data = {
        "bid": [10.123456, 11.999999, 12.5],
        "ask": [10.123456, 12.000000, 12.5000001],
    }
    table = con.create_table("test", data)

    result = table.mutate(is_locked=locked_rows(table.ask, table.bid)).execute()

    # First: exact match
    assert result["is_locked"].iloc[0] == True
    # Second: within float tolerance
    assert result["is_locked"].iloc[1] == True
    # Third: within float tolerance
    assert result["is_locked"].iloc[2] == True


def test_crossed_rows_edge_cases(con):
    """Test crossed rows with edge cases."""
    data = {
        "bid": [10.0, 0.0, 100.0],
        "ask": [5.0, 0.0, 99.99999],
    }
    table = con.create_table("test", data)

    result = table.mutate(is_crossed=crossed_rows(table.ask, table.bid)).execute()

    # First: clearly crossed
    assert result["is_crossed"].iloc[0] == True
    # Second: not crossed (equal, but not less than)
    assert result["is_crossed"].iloc[1] == False
    # Third: crossed
    assert result["is_crossed"].iloc[2] == True


def test_filter_locks_crosses_preserves_columns(con):
    """Test that filtering preserves all table columns."""
    data = {
        "id": [1, 2, 3],
        "symbol": ["AAPL", "MSFT", "GOOGL"],
        "bid": [10.0, 11.0, 12.0],
        "ask": [10.0, 11.5, 12.5],
        "volume": [1000, 2000, 3000],
    }
    table = con.create_table("test", data)

    result = filter_locks_crosses(table, table.ask, table.bid).execute()

    # Check all columns are preserved
    assert "id" in result.columns
    assert "symbol" in result.columns
    assert "bid" in result.columns
    assert "ask" in result.columns
    assert "volume" in result.columns
