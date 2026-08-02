import datetime

import ibis
import pandas as pd
import pytest

from .trades import TRADES_COLS_CLEAN, clean_trades


@pytest.fixture
def duckdb_con():
    """Create a DuckDB connection for tests."""
    return ibis.connect("duckdb://:memory:")


def test_clean_trades_basic(duckdb_con):
    """Test basic trade cleaning."""
    data = pd.DataFrame(
        {
            "DATE": [datetime.date(2023, 1, 15), datetime.date(2023, 1, 15)],
            "TIME_M": [34200.0, 34201.0],
            "SYM_ROOT": ["AAPL", "MSFT"],
            "SYM_SUFFIX": pd.Series([None, None], dtype="string"),
            "PRICE": [150.0, 250.0],
            "SIZE": [100, 200],
            "TR_CORR": ["00", "00"],
            "TR_SEQNUM": [1, 2],
            "TR_SCOND": ["", ""],
            "EX": ["N", "N"],
        }
    )
    table = duckdb_con.create_table("trades", data)

    result = clean_trades(table).execute()

    # Check output has correct columns
    assert set(TRADES_COLS_CLEAN).issubset(set(result.columns))

    # Check dollar calculation
    assert result["dollar"].iloc[0] == 15000.0  # 150.0 * 100
    assert result["dollar"].iloc[1] == 50000.0  # 250.0 * 200


def test_clean_trades_with_corrections(duckdb_con):
    """Test filtering of trade corrections."""
    data = pd.DataFrame(
        {
            "DATE": [datetime.date(2023, 1, 15)] * 3,
            "TIME_M": [34200.0, 34201.0, 34202.0],
            "SYM_ROOT": ["AAPL", "AAPL", "AAPL"],
            "SYM_SUFFIX": pd.Series([None, None, None], dtype="string"),
            "PRICE": [150.0, 150.0, 150.0],
            "SIZE": [100, 100, 100],
            "TR_CORR": ["00", "01", "02"],  # Regular, correction, cancellation
            "TR_SEQNUM": [1, 2, 3],
            "TR_SCOND": ["", "", ""],
            "EX": ["N", "N", "N"],
        }
    )
    table = duckdb_con.create_table("trades_corr", data)

    result = clean_trades(table, exclude_corrections=True).execute()

    # Should only keep the regular trade (tr_corr='00')
    assert len(result) == 1
    assert result["tr_seqnum"].iloc[0] == 1


def test_clean_trades_keep_corrections(duckdb_con):
    """Test keeping trade corrections."""
    data = pd.DataFrame(
        {
            "DATE": [datetime.date(2023, 1, 15)] * 2,
            "TIME_M": [34200.0, 34201.0],
            "SYM_ROOT": ["AAPL", "AAPL"],
            "SYM_SUFFIX": pd.Series([None, None], dtype="string"),
            "PRICE": [150.0, 150.0],
            "SIZE": [100, 100],
            "TR_CORR": ["00", "01"],
            "TR_SEQNUM": [1, 2],
            "TR_SCOND": ["", ""],
            "EX": ["N", "N"],
        }
    )
    table = duckdb_con.create_table("trades_keep_corr", data)

    result = clean_trades(table, exclude_corrections=False).execute()

    # Should keep both trades
    assert len(result) == 2


def test_clean_trades_price_filter(duckdb_con):
    """Test filtering by positive price."""
    data = pd.DataFrame(
        {
            "DATE": [datetime.date(2023, 1, 15)] * 3,
            "TIME_M": [34200.0, 34201.0, 34202.0],
            "SYM_ROOT": ["AAPL", "AAPL", "AAPL"],
            "SYM_SUFFIX": pd.Series([None, None, None], dtype="string"),
            "PRICE": [150.0, 0.0, -1.0],
            "SIZE": [100, 100, 100],
            "TR_CORR": ["00", "00", "00"],
            "TR_SEQNUM": [1, 2, 3],
            "TR_SCOND": ["", "", ""],
            "EX": ["N", "N", "N"],
        }
    )
    table = duckdb_con.create_table("trades_price", data)

    result = clean_trades(table, price_positive_only=True).execute()

    # Should only keep the trade with positive price
    assert len(result) == 1
    assert result["price"].iloc[0] == 150.0


def test_clean_trades_keep_non_positive_price(duckdb_con):
    """Test keeping non-positive prices."""
    data = pd.DataFrame(
        {
            "DATE": [datetime.date(2023, 1, 15)] * 2,
            "TIME_M": [34200.0, 34201.0],
            "SYM_ROOT": ["AAPL", "AAPL"],
            "SYM_SUFFIX": pd.Series([None, None], dtype="string"),
            "PRICE": [150.0, 0.0],
            "SIZE": [100, 100],
            "TR_CORR": ["00", "00"],
            "TR_SEQNUM": [1, 2],
            "TR_SCOND": ["", ""],
            "EX": ["N", "N"],
        }
    )
    table = duckdb_con.create_table("trades_keep_zero", data)

    result = clean_trades(table, price_positive_only=False).execute()

    # Should keep both trades
    assert len(result) == 2


def test_clean_trades_time_filter(duckdb_con):
    """Test filtering by time range."""
    data = pd.DataFrame(
        {
            "DATE": [datetime.date(2023, 1, 15)] * 4,
            "TIME_M": [
                32400.0,  # 09:00:00 - before start
                34200.0,  # 09:30:00 - at start
                46800.0,  # 13:00:00 - middle
                57600.0,  # 16:00:00 - at end
            ],
            "SYM_ROOT": ["AAPL", "AAPL", "AAPL", "AAPL"],
            "SYM_SUFFIX": pd.Series([None, None, None, None], dtype="string"),
            "PRICE": [150.0, 150.0, 150.0, 150.0],
            "SIZE": [100, 100, 100, 100],
            "TR_CORR": ["00", "00", "00", "00"],
            "TR_SEQNUM": [1, 2, 3, 4],
            "TR_SCOND": ["", "", "", ""],
            "EX": ["N", "N", "N", "N"],
        }
    )
    table = duckdb_con.create_table("trades_time", data)

    start_time = datetime.time(9, 30, 0)
    end_time = datetime.time(16, 0, 0)

    result = clean_trades(table, start_time=start_time, end_time=end_time).execute()

    # Should keep trades from 09:30 to 16:00 inclusive
    assert len(result) == 3
    assert result["tr_seqnum"].tolist() == [2, 3, 4]


def test_clean_trades_no_time_filter(duckdb_con):
    """Test with no time filtering."""
    data = pd.DataFrame(
        {
            "DATE": [datetime.date(2023, 1, 15)] * 2,
            "TIME_M": [32400.0, 61200.0],  # 09:00 and 17:00
            "SYM_ROOT": ["AAPL", "AAPL"],
            "SYM_SUFFIX": pd.Series([None, None], dtype="string"),
            "PRICE": [150.0, 150.0],
            "SIZE": [100, 100],
            "TR_CORR": ["00", "00"],
            "TR_SEQNUM": [1, 2],
            "TR_SCOND": ["", ""],
            "EX": ["N", "N"],
        }
    )
    table = duckdb_con.create_table("trades_no_time", data)

    result = clean_trades(table, start_time=None, end_time=None).execute()

    # Should keep all trades
    assert len(result) == 2


def test_clean_trades_with_suffix(duckdb_con):
    """Test trade cleaning with symbol suffix."""
    data = pd.DataFrame(
        {
            "DATE": [datetime.date(2023, 1, 15)],
            "TIME_M": [34200.0],
            "SYM_ROOT": ["BRK"],
            "SYM_SUFFIX": ["A"],
            "PRICE": [450000.0],
            "SIZE": [1],
            "TR_CORR": ["00"],
            "TR_SEQNUM": [1],
            "TR_SCOND": [""],
            "EX": ["N"],
        }
    )
    table = duckdb_con.create_table("trades_suffix", data)

    result = clean_trades(table).execute()

    assert result["symbol"].iloc[0] == "BRK A"


def test_clean_trades_preserves_tr_scond(duckdb_con):
    """Test that trade condition codes are preserved."""
    data = pd.DataFrame(
        {
            "DATE": [datetime.date(2023, 1, 15)] * 2,
            "TIME_M": [34200.0, 34201.0],
            "SYM_ROOT": ["AAPL", "AAPL"],
            "SYM_SUFFIX": pd.Series([None, None], dtype="string"),
            "PRICE": [150.0, 150.0],
            "SIZE": [100, 100],
            "TR_CORR": ["00", "00"],
            "TR_SEQNUM": [1, 2],
            "TR_SCOND": ["@", "T"],
            "EX": ["N", "N"],
        }
    )
    table = duckdb_con.create_table("trades_scond", data)

    result = clean_trades(table).execute()

    assert result["tr_scond"].iloc[0] == "@"
    assert result["tr_scond"].iloc[1] == "T"


def test_clean_trades_column_case_insensitive(duckdb_con):
    """Test that column names are case-insensitive."""
    data = pd.DataFrame(
        {
            "date": [datetime.date(2023, 1, 15)],  # lowercase
            "time_m": [34200.0],
            "sym_root": ["AAPL"],
            "sym_suffix": pd.Series([None], dtype="string"),
            "price": [150.0],
            "size": [100],
            "tr_corr": ["00"],
            "tr_seqnum": [1],
            "tr_scond": [""],
            "ex": ["N"],
        }
    )
    table = duckdb_con.create_table("trades_lower", data)

    result = clean_trades(table).execute()

    # Should work with lowercase column names
    assert len(result) == 1
    assert result["price"].iloc[0] == 150.0


def test_clean_trades_combined_filters(duckdb_con):
    """Test combining multiple filters."""
    data = pd.DataFrame(
        {
            "DATE": [datetime.date(2023, 1, 15)] * 4,
            "TIME_M": [
                32400.0,  # Before start time
                34200.0,  # Valid
                34201.0,  # Valid but has correction
                34202.0,  # Valid but zero price
            ],
            "SYM_ROOT": ["AAPL", "AAPL", "AAPL", "AAPL"],
            "SYM_SUFFIX": pd.Series([None, None, None, None], dtype="string"),
            "PRICE": [150.0, 150.0, 150.0, 0.0],
            "SIZE": [100, 100, 100, 100],
            "TR_CORR": ["00", "00", "01", "00"],
            "TR_SEQNUM": [1, 2, 3, 4],
            "TR_SCOND": ["", "", "", ""],
            "EX": ["N", "N", "N", "N"],
        }
    )
    table = duckdb_con.create_table("trades_combined", data)

    result = clean_trades(
        table,
        exclude_corrections=True,
        price_positive_only=True,
        start_time=datetime.time(9, 30, 0),
        end_time=datetime.time(16, 0, 0),
    ).execute()

    # Should only keep the second row (valid time, no correction, positive price)
    assert len(result) == 1
    assert result["tr_seqnum"].iloc[0] == 2
