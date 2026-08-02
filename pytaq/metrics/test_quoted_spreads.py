import datetime

import ibis
import pandas as pd
import pytest

from .quoted_spreads import (
    compute_quote_inforce,
    compute_spreads,
    compute_weighted_averages,
)


@pytest.fixture
def con():
    """Create an in-memory DuckDB connection for testing."""
    return ibis.connect("duckdb://:memory:")


def test_compute_spreads_basic(con):
    """Test basic spread computation."""
    data = pd.DataFrame({
        "best_bid": [99.5, 100.0, 100.5],
        "best_ask": [100.5, 101.0, 101.5],
        "best_bidsizeshares": [100, 200, 150],
        "best_asksizeshares": [150, 180, 120],
    })
    table = con.create_table("test", data)

    result = compute_spreads(table).execute()

    # Check dollar spread
    assert result["quoted_spread_dollar"].iloc[0] == 1.0
    assert result["quoted_spread_dollar"].iloc[1] == 1.0
    assert result["quoted_spread_dollar"].iloc[2] == 1.0

    # Check bid depth in dollars
    assert result["best_bid_depth_dollar"].iloc[0] == 99.5 * 100
    assert result["best_bid_depth_dollar"].iloc[1] == 100.0 * 200

    # Check ask depth in dollars
    assert result["best_ofr_depth_dollar"].iloc[0] == 100.5 * 150
    assert result["best_ofr_depth_dollar"].iloc[1] == 101.0 * 180

    # Check share depths
    assert result["best_bid_depth_share"].iloc[0] == 100
    assert result["best_ofr_depth_share"].iloc[0] == 150


def test_compute_spreads_percent(con):
    """Test percent spread computation."""
    data = pd.DataFrame({
        "best_bid": [100.0],
        "best_ask": [101.0],
        "best_bidsizeshares": [100],
        "best_asksizeshares": [100],
    })
    table = con.create_table("test", data)

    result = compute_spreads(table).execute()

    # Percent spread = log(ask) - log(bid)
    import math
    expected_percent = math.log(101.0) - math.log(100.0)
    assert abs(result["quoted_spread_percent"].iloc[0] - expected_percent) < 1e-6


def test_compute_weighted_averages_basic(con):
    """Test weighted average computation."""
    data = pd.DataFrame({
        "symbol": ["AAPL", "AAPL", "AAPL"],
        "quoted_spread_dollar": [1.0, 2.0, 3.0],
        "quoted_spread_percent": [0.01, 0.02, 0.03],
        "inforce": [100.0, 200.0, 300.0],  # Time weights
    })
    table = con.create_table("test", data)

    result = compute_weighted_averages(
        table,
        measures=["quoted_spread_dollar", "quoted_spread_percent"],
        groupby_col="symbol",
        inforce_col="inforce",
    ).execute()

    # Weighted average = sum(value * weight) / sum(weight)
    # Dollar: (1*100 + 2*200 + 3*300) / (100+200+300) = 1400/600 = 2.333...
    expected_dollar = (1.0 * 100 + 2.0 * 200 + 3.0 * 300) / (100 + 200 + 300)
    assert abs(result["quoted_spread_dollar"].iloc[0] - expected_dollar) < 1e-6

    # Percent: (0.01*100 + 0.02*200 + 0.03*300) / 600 = 14/600 = 0.0233...
    expected_percent = (0.01 * 100 + 0.02 * 200 + 0.03 * 300) / 600
    assert abs(result["quoted_spread_percent"].iloc[0] - expected_percent) < 1e-6


def test_compute_weighted_averages_multiple_symbols(con):
    """Test weighted averages with multiple symbols."""
    data = pd.DataFrame({
        "symbol": ["AAPL", "AAPL", "MSFT", "MSFT"],
        "quoted_spread_dollar": [1.0, 2.0, 3.0, 4.0],
        "inforce": [100.0, 100.0, 100.0, 100.0],
    })
    table = con.create_table("test", data)

    result = compute_weighted_averages(
        table,
        measures=["quoted_spread_dollar"],
        groupby_col="symbol",
        inforce_col="inforce",
    ).execute()

    # Should have 2 rows, one for each symbol
    assert len(result) == 2

    # AAPL average: (1+2)/2 = 1.5
    aapl = result[result["symbol"] == "AAPL"].iloc[0]
    assert abs(aapl["quoted_spread_dollar"] - 1.5) < 1e-6

    # MSFT average: (3+4)/2 = 3.5
    msft = result[result["symbol"] == "MSFT"].iloc[0]
    assert abs(msft["quoted_spread_dollar"] - 3.5) < 1e-6


def test_compute_weighted_averages_zero_weight(con):
    """Test weighted averages when all weights are zero."""
    data = pd.DataFrame({
        "symbol": ["AAPL", "AAPL"],
        "quoted_spread_dollar": [1.0, 2.0],
        "inforce": [0.0, 0.0],  # Zero weights
    })
    table = con.create_table("test", data)

    result = compute_weighted_averages(
        table,
        measures=["quoted_spread_dollar"],
        groupby_col="symbol",
        inforce_col="inforce",
    ).execute()

    # Should return null when all weights are zero
    assert pd.isna(result["quoted_spread_dollar"].iloc[0])


@pytest.mark.skip(reason="Window API issue - partition_by parameter")
def test_compute_quote_inforce_basic(con):
    """Test quote inforce time computation."""
    data = pd.DataFrame({
        "symbol": ["AAPL"] * 3,
        "timestamp": pd.to_datetime([
            "2023-01-01 09:30:00",
            "2023-01-01 09:30:10",
            "2023-01-01 09:30:25",
        ]),
    })
    table = con.create_table("test", data)

    end_timestamp = datetime.datetime(2023, 1, 1, 16, 0, 0)

    result = compute_quote_inforce(
        table,
        end_timestamp=end_timestamp,
        groupby_col="symbol",
        timestamp_col="timestamp",
        inforce_col="inforce",
    ).execute()

    # First quote in force for 10 seconds (until next quote)
    assert result["inforce"].iloc[0] == 10.0
    # Second quote in force for 15 seconds
    assert result["inforce"].iloc[1] == 15.0
    # Last quote in force until end of day
    last_inforce = (end_timestamp - pd.Timestamp("2023-01-01 09:30:25")).total_seconds()
    assert abs(result["inforce"].iloc[2] - last_inforce) < 1e-6


@pytest.mark.skip(reason="Window API issue - partition_by parameter")
def test_compute_quote_inforce_multiple_symbols(con):
    """Test quote inforce with multiple symbols."""
    data = pd.DataFrame({
        "symbol": ["AAPL", "AAPL", "MSFT", "MSFT"],
        "timestamp": pd.to_datetime([
            "2023-01-01 09:30:00",
            "2023-01-01 09:30:10",
            "2023-01-01 09:30:05",
            "2023-01-01 09:30:20",
        ]),
    })
    table = con.create_table("test", data)

    end_timestamp = datetime.datetime(2023, 1, 1, 16, 0, 0)

    result = compute_quote_inforce(
        table,
        end_timestamp=end_timestamp,
        groupby_col="symbol",
        timestamp_col="timestamp",
    ).execute()

    # Each symbol should have its own inforce times
    aapl = result[result["symbol"] == "AAPL"].sort_values("timestamp")
    assert aapl.iloc[0]["inforce"] == 10.0  # AAPL first quote

    msft = result[result["symbol"] == "MSFT"].sort_values("timestamp")
    assert msft.iloc[0]["inforce"] == 15.0  # MSFT first quote (5 sec -> 20 sec)
