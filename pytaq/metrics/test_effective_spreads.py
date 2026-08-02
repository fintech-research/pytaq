import math

import ibis
import pandas as pd
import pytest

from .effective_spreads import compute_effective_spreads


@pytest.fixture
def con():
    """Create an in-memory DuckDB connection for testing."""
    return ibis.connect("duckdb://:memory:")


def test_compute_effective_spreads_basic(con):
    """Test basic effective spread computation."""
    data = {
        "price": [100.0, 101.0, 102.0],
        "midpoint": [99.5, 100.5, 101.5],
        "best_bid": [99.0, 100.0, 101.0],
        "best_ask": [100.0, 101.0, 102.0],
    }
    table = con.create_table("test", data)

    result = compute_effective_spreads(table).execute()

    # Check that spread columns were added
    assert "DollarEffectiveSpread" in result.columns
    assert "PercentEffectiveSpread" in result.columns

    # Dollar effective spread = 2 * |price - midpoint|
    assert abs(result["DollarEffectiveSpread"].iloc[0] - 1.0) < 0.01
    assert abs(result["DollarEffectiveSpread"].iloc[1] - 1.0) < 0.01
    assert abs(result["DollarEffectiveSpread"].iloc[2] - 1.0) < 0.01


def test_compute_effective_spreads_filters_locks(con):
    """Test that locked quotes are filtered out."""
    data = {
        "id": [1, 2, 3, 4],
        "price": [100.0, 101.0, 102.0, 103.0],
        "midpoint": [99.5, 100.5, 101.5, 102.5],
        "best_bid": [99.0, 100.5, 101.0, 102.5],
        "best_ask": [100.0, 100.5, 102.0, 102.5],
    }
    table = con.create_table("test", data)

    result = compute_effective_spreads(table).execute()

    # Should filter out locked rows
    assert len(result) == 2
    assert 1 in result["id"].values
    assert 3 in result["id"].values


def test_compute_effective_spreads_filters_crosses(con):
    """Test that crossed quotes are filtered out."""
    data = {
        "id": [1, 2, 3, 4],
        "price": [100.0, 101.0, 102.0, 103.0],
        "midpoint": [99.5, 100.5, 101.5, 102.5],
        "best_bid": [99.0, 101.0, 101.0, 103.0],
        "best_ask": [100.0, 100.0, 102.0, 102.0],
    }
    table = con.create_table("test", data)

    result = compute_effective_spreads(table).execute()

    # Should filter out crossed rows
    assert len(result) == 2
    assert 1 in result["id"].values
    assert 3 in result["id"].values


def test_compute_effective_spreads_filters_both(con):
    """Test filtering of both locked and crossed quotes."""
    data = {
        "id": [1, 2, 3, 4, 5],
        "price": [100.0, 101.0, 102.0, 103.0, 104.0],
        "midpoint": [99.5, 100.5, 101.5, 102.5, 103.5],
        "best_bid": [99.0, 101.0, 101.5, 102.0, 104.0],
        "best_ask": [100.0, 100.0, 101.5, 103.0, 103.0],
    }
    table = con.create_table("test", data)

    result = compute_effective_spreads(table).execute()

    # Should keep only rows 1 and 4
    assert len(result) == 2
    assert 1 in result["id"].values
    assert 4 in result["id"].values


def test_compute_effective_spreads_dollar_calculation(con):
    """Test dollar effective spread calculation."""
    data = {
        "price": [100.0, 105.0, 98.0],
        "midpoint": [99.0, 100.0, 100.0],
        "best_bid": [98.5, 99.5, 99.5],
        "best_ask": [99.5, 100.5, 100.5],
    }
    table = con.create_table("test", data)

    result = compute_effective_spreads(table).execute()

    # Dollar spread = 2 * |price - midpoint|
    assert abs(result["DollarEffectiveSpread"].iloc[0] - 2.0) < 0.01  # 2*|100-99|
    assert abs(result["DollarEffectiveSpread"].iloc[1] - 10.0) < 0.01  # 2*|105-100|
    assert abs(result["DollarEffectiveSpread"].iloc[2] - 4.0) < 0.01  # 2*|98-100|


def test_compute_effective_spreads_percent_calculation(con):
    """Test percent effective spread calculation."""
    import math

    data = {
        "price": [100.0, 105.0],
        "midpoint": [99.0, 100.0],
        "best_bid": [98.5, 99.5],
        "best_ask": [99.5, 100.5],
    }
    table = con.create_table("test", data)

    result = compute_effective_spreads(table).execute()

    # Percent spread = 2 * |ln(price) - ln(midpoint)|
    expected1 = 2 * abs(math.log(100.0) - math.log(99.0))
    expected2 = 2 * abs(math.log(105.0) - math.log(100.0))

    assert abs(result["PercentEffectiveSpread"].iloc[0] - expected1) < 0.01
    assert abs(result["PercentEffectiveSpread"].iloc[1] - expected2) < 0.01


def test_compute_effective_spreads_preserves_columns(con):
    """Test that all original columns are preserved."""
    data = {
        "id": [1, 2],
        "symbol": ["AAPL", "MSFT"],
        "price": [100.0, 101.0],
        "midpoint": [99.5, 100.5],
        "best_bid": [99.0, 100.0],
        "best_ask": [100.0, 101.0],
        "volume": [1000, 2000],
    }
    table = con.create_table("test", data)

    result = compute_effective_spreads(table).execute()

    # Check all original columns are preserved
    assert "id" in result.columns
    assert "symbol" in result.columns
    assert "price" in result.columns
    assert "midpoint" in result.columns
    assert "volume" in result.columns


# ---------------------------------------------------------------------------
# Percent convention (#39)
# ---------------------------------------------------------------------------


@pytest.fixture
def one_trade(con):
    """A single trade 50 cents above a midpoint of 100."""
    data = pd.DataFrame(
        {
            "price": [100.5],
            "midpoint": [100.0],
            "best_bid": [99.5],
            "best_ask": [100.5],
        }
    )
    return con.create_table("one_trade", data)


def test_percent_effective_spread_defaults_to_the_hj_ratio(one_trade):
    """H&J define the percent measure as the dollar measure over the midpoint."""
    result = compute_effective_spreads(one_trade).execute()

    # 2*|100.5 - 100.0| = 1.0, and 1.0 / 100.0 = 0.01
    assert result["DollarEffectiveSpread"].iloc[0] == pytest.approx(1.0)
    assert result["PercentEffectiveSpread"].iloc[0] == pytest.approx(0.01)


def test_percent_effective_spread_log_convention_is_available(one_trade):
    result = compute_effective_spreads(one_trade, percent_method="log").execute()

    expected = abs(math.log(100.5) - math.log(100.0)) * 2
    assert result["PercentEffectiveSpread"].iloc[0] == pytest.approx(expected)
    # Close to the ratio form, but not equal to it.
    assert result["PercentEffectiveSpread"].iloc[0] != pytest.approx(0.01, abs=1e-12)


def test_dollar_effective_spread_does_not_depend_on_the_convention(one_trade):
    ratio = compute_effective_spreads(one_trade).execute()
    log = compute_effective_spreads(one_trade, percent_method="log").execute()

    assert (
        ratio["DollarEffectiveSpread"].iloc[0] == log["DollarEffectiveSpread"].iloc[0]
    )


def test_unknown_percent_method_is_rejected(one_trade):
    with pytest.raises(ValueError, match="percent_method must be one of"):
        compute_effective_spreads(one_trade, percent_method="geometric")
