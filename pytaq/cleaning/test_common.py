import datetime

import ibis
import pandas as pd
import pytest

from .common import filter_by_time, merge_datetime, merge_symbol


@pytest.fixture
def duckdb_con():
    """Create a DuckDB connection for tests."""
    return ibis.connect("duckdb://:memory:")


def test_merge_datetime_basic(duckdb_con):
    """Test merging date and time_m columns into timestamp."""
    data = {
        "date": [
            datetime.date(2023, 1, 15),
            datetime.date(2023, 1, 16),
        ],
        "time_m": [
            34200.0,  # 09:30:00
            57600.5,  # 16:00:00.5
        ],
        "other": [1, 2],
    }
    table = duckdb_con.create_table("test_datetime", data)

    result = merge_datetime(table).execute()

    # Check that timestamp column was created
    assert "timestamp" in result.columns

    # Verify first row
    ts1 = result["timestamp"].iloc[0]
    assert ts1.year == 2023
    assert ts1.month == 1
    assert ts1.day == 15
    assert ts1.hour == 9
    assert ts1.minute == 30
    assert ts1.second == 0

    # Verify second row with fractional seconds
    ts2 = result["timestamp"].iloc[1]
    assert ts2.year == 2023
    assert ts2.month == 1
    assert ts2.day == 16
    assert ts2.hour == 16
    assert ts2.minute == 0
    assert ts2.second == 0
    assert ts2.microsecond == 500000  # 0.5 seconds


def test_merge_datetime_with_microseconds(duckdb_con):
    """Test merging with microsecond precision."""
    data = {
        "date": [datetime.date(2023, 1, 15)],
        "time_m": [34200.123456],  # 09:30:00.123456
    }
    table = duckdb_con.create_table("test_microseconds", data)

    result = merge_datetime(table).execute()

    ts = result["timestamp"].iloc[0]
    assert ts.hour == 9
    assert ts.minute == 30
    assert ts.second == 0
    # Check microseconds (should be ~123456)
    assert 123400 <= ts.microsecond <= 123500  # Allow some rounding


def test_merge_symbol_without_suffix(duckdb_con):
    """Test merging symbol when sym_suffix is null."""
    data = pd.DataFrame(
        {
            "sym_root": ["AAPL", "MSFT", "GOOG"],
            "sym_suffix": pd.Series([None, None, None], dtype="string"),
        }
    )
    table = duckdb_con.create_table("test_symbol_no_suffix", data)

    result = merge_symbol(table).execute()

    assert "symbol" in result.columns
    assert result["symbol"].iloc[0] == "AAPL"
    assert result["symbol"].iloc[1] == "MSFT"
    assert result["symbol"].iloc[2] == "GOOG"


def test_merge_symbol_with_suffix(duckdb_con):
    """Test merging symbol when sym_suffix exists."""
    data = pd.DataFrame(
        {
            "sym_root": ["BRK", "BRK", "AAPL"],
            "sym_suffix": pd.Series(["A", "B", None], dtype="string"),
        }
    )
    table = duckdb_con.create_table("test_symbol_with_suffix", data)

    result = merge_symbol(table).execute()

    assert result["symbol"].iloc[0] == "BRK A"
    assert result["symbol"].iloc[1] == "BRK B"
    assert result["symbol"].iloc[2] == "AAPL"


def test_merge_symbol_strips_whitespace(duckdb_con):
    """Test that merge_symbol strips extra whitespace."""
    data = pd.DataFrame(
        {
            "sym_root": ["AAPL  ", "  MSFT"],
            "sym_suffix": pd.Series([None, None], dtype="string"),
        }
    )
    table = duckdb_con.create_table("test_symbol_whitespace", data)

    result = merge_symbol(table).execute()

    # Should strip whitespace
    assert result["symbol"].iloc[0] == "AAPL"
    assert result["symbol"].iloc[1] == "MSFT"


def test_filter_by_time_both_bounds(duckdb_con):
    """Test filtering with both start and end time."""
    data = {
        "time_m": [
            32400.0,  # 09:00:00
            34200.0,  # 09:30:00
            46800.0,  # 13:00:00
            57600.0,  # 16:00:00
            61200.0,  # 17:00:00
        ],
        "value": [1, 2, 3, 4, 5],
    }
    table = duckdb_con.create_table("test_filter_time", data)

    start = datetime.time(9, 30, 0)
    end = datetime.time(16, 0, 0)

    result = filter_by_time(table, start_time=start, end_time=end).execute()

    # Should only include times between 09:30 and 16:00 inclusive
    assert len(result) == 3
    assert result["value"].tolist() == [2, 3, 4]


def test_filter_by_time_start_only(duckdb_con):
    """Test filtering with only start time."""
    data = {
        "time_m": [
            32400.0,  # 09:00:00
            34200.0,  # 09:30:00
            46800.0,  # 13:00:00
        ],
        "value": [1, 2, 3],
    }
    table = duckdb_con.create_table("test_filter_start", data)

    start = datetime.time(9, 30, 0)

    result = filter_by_time(table, start_time=start).execute()

    assert len(result) == 2
    assert result["value"].tolist() == [2, 3]


def test_filter_by_time_end_only(duckdb_con):
    """Test filtering with only end time."""
    data = {
        "time_m": [
            32400.0,  # 09:00:00
            34200.0,  # 09:30:00
            46800.0,  # 13:00:00
        ],
        "value": [1, 2, 3],
    }
    table = duckdb_con.create_table("test_filter_end", data)

    end = datetime.time(9, 30, 0)

    result = filter_by_time(table, end_time=end).execute()

    assert len(result) == 2
    assert result["value"].tolist() == [1, 2]


def test_filter_by_time_no_filter(duckdb_con):
    """Test filter_by_time with no filters returns original table."""
    data = {
        "time_m": [32400.0, 34200.0, 46800.0],
        "value": [1, 2, 3],
    }
    table = duckdb_con.create_table("test_no_filter", data)

    result = filter_by_time(table).execute()

    assert len(result) == 3
    assert result["value"].tolist() == [1, 2, 3]


def test_merge_datetime_preserves_other_columns(duckdb_con):
    """Test that merge_datetime preserves all other columns."""
    data = {
        "date": [datetime.date(2023, 1, 15)],
        "time_m": [34200.0],
        "col1": ["test"],
        "col2": [42],
    }
    table = duckdb_con.create_table("test_preserve", data)

    result = merge_datetime(table).execute()

    assert "timestamp" in result.columns
    assert "date" in result.columns
    assert "time_m" in result.columns
    assert "col1" in result.columns
    assert "col2" in result.columns
    assert result["col1"].iloc[0] == "test"
    assert result["col2"].iloc[0] == 42


def test_merge_symbol_preserves_other_columns(duckdb_con):
    """Test that merge_symbol preserves all other columns."""
    data = pd.DataFrame(
        {
            "sym_root": ["AAPL"],
            "sym_suffix": pd.Series([None], dtype="string"),
            "price": [150.0],
            "volume": [1000],
        }
    )
    table = duckdb_con.create_table("test_preserve_symbol", data)

    result = merge_symbol(table).execute()

    assert "symbol" in result.columns
    assert "price" in result.columns
    assert "volume" in result.columns
    assert result["price"].iloc[0] == 150.0
    assert result["volume"].iloc[0] == 1000


# ---------------------------------------------------------------------------
# time_m arrives in two shapes, and both are real (#29)
#
# The WRDS postgres server types time_m as a SQL time; local exports commonly
# carry it as a double of seconds since midnight. The tests above cover the
# numeric shape, which was the only one the code originally handled.
# ---------------------------------------------------------------------------

# The same three observations, expressed both ways.
_TIMES = [
    datetime.time(9, 30, 0, 0),
    datetime.time(9, 30, 0, 436516),
    datetime.time(15, 59, 59, 999999),
]
_SECONDS = [34200.0, 34200.436516, 57599.999999]


@pytest.fixture
def time_typed(duckdb_con):
    """A table whose time_m is a SQL time, as WRDS postgres returns."""
    frame = pd.DataFrame(
        {"date": [datetime.date(2020, 1, 2)] * 3, "time_m": _TIMES, "row": [0, 1, 2]}
    )
    table = duckdb_con.create_table("time_typed", frame)
    assert table.time_m.type().is_time(), "fixture must carry a real time column"
    return table


@pytest.fixture
def numeric_typed(duckdb_con):
    """A table whose time_m is seconds since midnight, as local exports carry."""
    frame = pd.DataFrame(
        {"date": [datetime.date(2020, 1, 2)] * 3, "time_m": _SECONDS, "row": [0, 1, 2]}
    )
    table = duckdb_con.create_table("numeric_typed", frame)
    assert table.time_m.type().is_numeric()
    return table


def test_merge_datetime_accepts_a_time_column(time_typed):
    """Regression test: this raised AttributeError on real WRDS data.

    `TimeColumn` has no `.floor()`, so the numeric implementation could not
    touch a postgres table at all.
    """
    result = merge_datetime(time_typed).execute().sort_values("row")

    assert [ts.time() for ts in result["timestamp"]] == _TIMES


def test_both_time_m_shapes_give_the_same_timestamp(time_typed, numeric_typed):
    """The two schemas describe the same instants and must agree."""
    from_time = merge_datetime(time_typed).execute().sort_values("row")
    from_numeric = merge_datetime(numeric_typed).execute().sort_values("row")

    assert list(from_time["timestamp"]) == list(from_numeric["timestamp"])


def test_filter_by_time_accepts_a_time_column(time_typed):
    """Regression test: comparing a time column against a float raised."""
    result = filter_by_time(
        time_typed, datetime.time(9, 30, 0, 1), datetime.time(16, 0)
    ).execute()

    # Drops the 09:30:00.000000 row, keeps the other two.
    assert sorted(result["row"]) == [1, 2]


def test_both_time_m_shapes_filter_identically(time_typed, numeric_typed):
    start, end = datetime.time(9, 30, 0, 1), datetime.time(16, 0)

    from_time = filter_by_time(time_typed, start, end).execute()
    from_numeric = filter_by_time(numeric_typed, start, end).execute()

    assert sorted(from_time["row"]) == sorted(from_numeric["row"])


def test_merge_datetime_rejects_an_unusable_time_m(duckdb_con):
    """A string time_m is a schema mistake and should say so, not guess."""
    frame = pd.DataFrame(
        {
            "date": [datetime.date(2020, 1, 2)],
            "time_m": pd.Series(["09:30:00"], dtype="string"),
        }
    )
    table = duckdb_con.create_table("string_time", frame)

    with pytest.raises(TypeError, match="time or a numeric"):
        merge_datetime(table)


def test_filter_by_time_rejects_an_unusable_time_m(duckdb_con):
    frame = pd.DataFrame(
        {
            "date": [datetime.date(2020, 1, 2)],
            "time_m": pd.Series(["09:30:00"], dtype="string"),
        }
    )
    table = duckdb_con.create_table("string_time_filter", frame)

    with pytest.raises(TypeError, match="time or a numeric"):
        filter_by_time(table, datetime.time(9, 30), datetime.time(16, 0))
