import datetime
from decimal import Decimal

import ibis
import pandas as pd
import pytest

from .quotes import (
    QUOTES_COLS_CLEAN,
    clean_quote_table,
    filter_quote_table,
    filter_withdrawned_quotes,
)


@pytest.fixture
def duckdb_con():
    """Create a DuckDB connection for tests."""
    return ibis.connect("duckdb://:memory:")


def test_filter_withdrawned_quotes_basic(duckdb_con):
    """Test filtering of withdrawned quotes."""
    data = {
        "bid": [10.0, 0.0, None, 10.5, -1.0],
        "ask": [10.5, 10.5, 11.0, None, 11.0],
        "bidsiz": [100, 100, 100, 100, 100],
        "asksiz": [100, 100, 100, 0, 100],
    }
    table = duckdb_con.create_table("quotes", data)

    result = filter_withdrawned_quotes(table).execute()

    # Only first row should remain (all others have issues)
    assert len(result) == 1
    assert result["bid"].iloc[0] == 10.0


def test_filter_withdrawned_quotes_all_valid(duckdb_con):
    """Test that valid quotes are kept."""
    data = {
        "bid": [10.0, 11.0, 12.0],
        "ask": [10.5, 11.5, 12.5],
        "bidsiz": [100, 200, 300],
        "asksiz": [100, 200, 300],
    }
    table = duckdb_con.create_table("quotes_valid", data)

    result = filter_withdrawned_quotes(table).execute()

    assert len(result) == 3


def test_filter_quote_table_qu_cond(duckdb_con):
    """Test filtering by quote condition."""
    data = {
        "bid": [10.0, 10.0, 10.0],
        "ask": [10.5, 10.5, 10.5],
        "bidsiz": [100, 100, 100],
        "asksiz": [100, 100, 100],
        "qu_cond": ["A", "B", "Z"],  # Z is not in HJ_KEEP_QU_COND
        "qu_cancel": ["", "", ""],
        "natbbo_ind": ["1", "1", "1"],
        "qu_source": ["C", "C", "C"],
    }
    table = duckdb_con.create_table("quotes_cond", data)

    result = filter_quote_table(table, keep_qu_cond=["A", "B"]).execute()

    assert len(result) == 2
    assert all(result["qu_cond"].isin(["A", "B"]))


def test_filter_quote_table_canceled(duckdb_con):
    """Test filtering of canceled quotes."""
    data = {
        "bid": [10.0, 10.0, 10.0],
        "ask": [10.5, 10.5, 10.5],
        "bidsiz": [100, 100, 100],
        "asksiz": [100, 100, 100],
        "qu_cond": ["A", "A", "A"],
        "qu_cancel": ["", "B", "C"],  # B means canceled
        "natbbo_ind": ["1", "1", "1"],
        "qu_source": ["C", "C", "C"],
    }
    table = duckdb_con.create_table("quotes_cancel", data)

    result = filter_quote_table(
        table, delete_canceled_quotes=True, keep_qu_cond=None
    ).execute()

    # Should exclude the row with qu_cancel='B'
    assert len(result) == 2


def test_filter_quote_table_crossed_markets(duckdb_con):
    """Test filtering of crossed markets (bid > ask)."""
    data = {
        "bid": [10.0, 11.0, 10.0],
        "ask": [10.5, 10.5, 10.5],  # Second row is crossed
        "bidsiz": [100, 100, 100],
        "asksiz": [100, 100, 100],
        "qu_cond": ["A", "A", "A"],
        "qu_cancel": ["", "", ""],
        "natbbo_ind": ["1", "1", "1"],
        "qu_source": ["C", "C", "C"],
    }
    table = duckdb_con.create_table("quotes_crossed", data)

    result = filter_quote_table(
        table, delete_crossed_markets=True, keep_qu_cond=None
    ).execute()

    # Should exclude the crossed market row
    assert len(result) == 2
    assert all(result["bid"] <= result["ask"])


def test_filter_quote_table_abnormal_spreads(duckdb_con):
    """Test filtering of abnormal spreads."""
    data = {
        "bid": [10.0, 10.0, 10.0],
        "ask": [10.5, 20.0, 11.0],  # Second row has spread of 10.0
        "bidsiz": [100, 100, 100],
        "asksiz": [100, 100, 100],
        "qu_cond": ["A", "A", "A"],
        "qu_cancel": ["", "", ""],
        "natbbo_ind": ["1", "1", "1"],
        "qu_source": ["C", "C", "C"],
    }
    table = duckdb_con.create_table("quotes_spread", data)

    result = filter_quote_table(
        table,
        delete_abnormal_spreads=True,
        max_spread=Decimal("5.0"),
        keep_qu_cond=None,
    ).execute()

    # Should exclude the row with spread > 5.0
    assert len(result) == 2


def test_filter_quote_table_nbbo_only(duckdb_con):
    """Test filtering for NBBO quotes only."""
    data = {
        "bid": [10.0, 10.0, 10.0, 10.0],
        "ask": [10.5, 10.5, 10.5, 10.5],
        "bidsiz": [100, 100, 100, 100],
        "asksiz": [100, 100, 100, 100],
        "qu_cond": ["A", "A", "A", "A"],
        "qu_cancel": ["", "", "", ""],
        "qu_source": ["C", "C", "N", "X"],
        "natbbo_ind": ["1", "0", "4", "1"],
    }
    table = duckdb_con.create_table("quotes_nbbo", data)

    result = filter_quote_table(table, nbbo_only=True, keep_qu_cond=None).execute()

    # Should only keep rows where (qu_source='C' AND natbbo_ind='1') OR (qu_source='N' AND natbbo_ind='4')
    assert len(result) == 2
    assert result["qu_source"].iloc[0] == "C"
    assert result["qu_source"].iloc[1] == "N"


def test_clean_quote_table_basic(duckdb_con):
    """Test complete quote cleaning pipeline."""
    data = pd.DataFrame(
        {
            "date": [datetime.date(2023, 1, 15), datetime.date(2023, 1, 15)],
            "time_m": [34200.0, 34201.0],
            "sym_root": ["AAPL", "MSFT"],
            "sym_suffix": pd.Series([None, None], dtype="string"),
            "bid": [150.0, 250.0],
            "ask": [150.5, 250.5],
            "bidsiz": [10, 20],  # In round lots
            "asksiz": [15, 25],
            "qu_cond": ["A", "A"],
            "qu_cancel": ["", ""],
            "natbbo_ind": ["1", "1"],
            "qu_source": ["C", "C"],
            "qu_seqnum": [1, 2],
            "ex": ["N", "N"],
        }
    )
    table = duckdb_con.create_table("quotes_clean", data)

    result = clean_quote_table(table, keep_qu_cond=["A"]).execute()

    # Check that output has correct columns
    assert set(QUOTES_COLS_CLEAN).issubset(set(result.columns))

    # Check conversion of size from round lots to shares
    assert result["best_bidsizeshares"].iloc[0] == 1000  # 10 * 100
    assert result["best_asksizeshares"].iloc[0] == 1500  # 15 * 100


def test_clean_quote_table_with_flags(duckdb_con):
    """Test quote cleaning with flag output."""
    data = pd.DataFrame(
        {
            "date": [datetime.date(2023, 1, 15)],
            "time_m": [34200.0],
            "sym_root": ["AAPL"],
            "sym_suffix": pd.Series([None], dtype="string"),
            "bid": [150.0],
            "ask": [150.5],
            "bidsiz": [10],
            "asksiz": [15],
            "qu_cond": ["A"],
            "qu_cancel": [""],
            "natbbo_ind": ["1"],
            "qu_source": ["C"],
            "qu_seqnum": [1],
            "ex": ["N"],
        }
    )
    table = duckdb_con.create_table("quotes_flags", data)

    result = clean_quote_table(table, output_flags=True, keep_qu_cond=["A"]).execute()

    # Check that flag columns are included
    assert "qu_cond" in result.columns
    assert "natbbo_ind" in result.columns
    assert "qu_source" in result.columns
    assert "qu_cancel" in result.columns


def test_clean_quote_table_with_suffix(duckdb_con):
    """Test quote cleaning with symbol suffix."""
    data = pd.DataFrame(
        {
            "date": [datetime.date(2023, 1, 15)],
            "time_m": [34200.0],
            "sym_root": ["BRK"],
            "sym_suffix": ["A"],
            "bid": [450000.0],
            "ask": [450100.0],
            "bidsiz": [1],
            "asksiz": [1],
            "qu_cond": ["A"],
            "qu_cancel": [""],
            "natbbo_ind": ["1"],
            "qu_source": ["C"],
            "qu_seqnum": [1],
            "ex": ["N"],
        }
    )
    table = duckdb_con.create_table("quotes_suffix", data)

    result = clean_quote_table(
        table, keep_qu_cond=["A"], max_spread=Decimal("200.0")
    ).execute()

    assert result["symbol"].iloc[0] == "BRK A"


def test_filter_quote_table_all_filters_disabled(duckdb_con):
    """Test that all filters can be disabled."""
    data = {
        "bid": [10.0, 11.0, 0.0],  # Last one would normally be filtered
        "ask": [10.5, 10.0, 10.5],  # Crossed market
        "bidsiz": [100, 100, 100],
        "asksiz": [100, 100, 100],
        "qu_cond": ["Z", "Z", "Z"],  # Not in default list
        "qu_cancel": ["B", "", ""],  # Canceled
        "natbbo_ind": ["0", "0", "0"],
        "qu_source": ["X", "X", "X"],
    }
    table = duckdb_con.create_table("quotes_no_filter", data)

    result = filter_quote_table(
        table,
        keep_qu_cond=None,
        delete_canceled_quotes=False,
        delete_crossed_markets=False,
        delete_withdrawned_quotes=False,
        delete_abnormal_spreads=False,
        nbbo_only=False,
    ).execute()

    # Should keep all rows
    assert len(result) == 3


def test_filter_withdrawned_quotes_edge_cases(duckdb_con):
    """Test edge cases for withdrawned quotes filtering."""
    data = {
        "bid": [10.0, 10.0, 10.0],
        "ask": [10.5, 10.5, 10.5],
        "bidsiz": [0, 100, 100],  # Zero size
        "asksiz": [100, 0, 100],  # Zero size
    }
    table = duckdb_con.create_table("quotes_edge", data)

    result = filter_withdrawned_quotes(table).execute()

    # Should only keep the last row
    assert len(result) == 1
    assert result["bidsiz"].iloc[0] == 100
    assert result["asksiz"].iloc[0] == 100


def test_filter_quote_table_keeps_null_qu_cancel(duckdb_con):
    """A null cancel flag means "not canceled" and must not drop the quote.

    Regression test: `qu_cancel != "B"` alone evaluates to NULL for null
    cancel flags, which silently discarded every such quote.
    """
    data = pd.DataFrame(
        {
            "qu_cond": pd.Series(["R", "R", "R"], dtype="string"),
            "qu_cancel": pd.Series([None, "", "B"], dtype="string"),
            "bid": [10.0, 10.0, 10.0],
            "ask": [10.5, 10.5, 10.5],
            "bidsiz": [100, 100, 100],
            "asksiz": [100, 100, 100],
            "qu_source": pd.Series(["C", "C", "C"], dtype="string"),
            "natbbo_ind": pd.Series(["1", "1", "1"], dtype="string"),
        }
    )
    table = duckdb_con.create_table("quotes_null_cancel", data)

    result = filter_quote_table(table).execute()

    # The null and the empty-string rows survive; only the explicit "B" goes.
    assert len(result) == 2
    assert "B" not in set(result["qu_cancel"].dropna())
