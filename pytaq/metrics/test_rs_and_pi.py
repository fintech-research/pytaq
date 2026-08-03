from datetime import timedelta

import ibis
import pandas as pd
import pytest

from .rs_and_pi import (
    dollar_price_impact,
    dollar_realized_spread,
    merge_future_nbbo,
    percent_price_impact,
    percent_realized_spread,
)


@pytest.fixture
def con():
    """Create an in-memory DuckDB connection for testing."""
    return ibis.connect("duckdb://:memory:")


def test_dollar_realized_spread_basic(con):
    """Test dollar realized spread computation."""
    data = pd.DataFrame(
        {
            "sign": [1, -1, 1],
            "price": [100.5, 99.5, 100.0],
            "midpoint_next": [100.0, 100.0, 100.0],
        }
    )
    table = con.create_table("test", data)

    result = table.mutate(
        rs_dollar=dollar_realized_spread(table.sign, table.price, table.midpoint_next)
    ).execute()

    # RS = sign * (price - midpoint_next) * 2
    # First: 1 * (100.5 - 100.0) * 2 = 1.0
    assert result["rs_dollar"].iloc[0] == 1.0
    # Second: -1 * (99.5 - 100.0) * 2 = 1.0
    assert result["rs_dollar"].iloc[1] == 1.0
    # Third: 1 * (100.0 - 100.0) * 2 = 0, but corrected to null (price == midpoint)
    assert pd.isna(result["rs_dollar"].iloc[2])


def test_percent_realized_spread_basic(con):
    """Test percent realized spread computation."""
    data = pd.DataFrame(
        {
            "sign": [1, -1],
            "price": [101.0, 99.0],
            "midpoint_next": [100.0, 100.0],
        }
    )
    table = con.create_table("test", data)

    import math

    # Default is the Holden and Jacobsen ratio: the dollar measure over the
    # future midpoint, sign * (price - midpoint_next) * 2 / midpoint_next.
    ratio = table.mutate(
        rs_percent=percent_realized_spread(table.sign, table.price, table.midpoint_next)
    ).execute()
    assert ratio["rs_percent"].iloc[0] == pytest.approx((101.0 - 100.0) * 2 / 100.0)
    assert ratio["rs_percent"].iloc[1] == pytest.approx(-(99.0 - 100.0) * 2 / 100.0)

    # The log convention remains available.
    log = table.mutate(
        rs_percent=percent_realized_spread(
            table.sign, table.price, table.midpoint_next, percent_method="log"
        )
    ).execute()
    assert log["rs_percent"].iloc[0] == pytest.approx(
        (math.log(101.0) - math.log(100.0)) * 2
    )
    assert log["rs_percent"].iloc[1] == pytest.approx(
        -(math.log(99.0) - math.log(100.0)) * 2
    )


def test_dollar_price_impact_basic(con):
    """Test dollar price impact computation."""
    data = pd.DataFrame(
        {
            "sign": [1, -1, 1],
            "midpoint": [100.0, 100.0, 100.0],
            "midpoint_next": [100.5, 99.5, 100.0],
        }
    )
    table = con.create_table("test", data)

    result = table.mutate(
        pi_dollar=dollar_price_impact(table.sign, table.midpoint, table.midpoint_next)
    ).execute()

    # PI = sign * (midpoint_next - midpoint) * 2
    # First: 1 * (100.5 - 100.0) * 2 = 1.0
    assert result["pi_dollar"].iloc[0] == 1.0
    # Second: -1 * (99.5 - 100.0) * 2 = 1.0
    assert result["pi_dollar"].iloc[1] == 1.0
    # Third: 1 * (100.0 - 100.0) * 2 = 0, corrected to null
    assert pd.isna(result["pi_dollar"].iloc[2])


def test_percent_price_impact_basic(con):
    """Test percent price impact computation."""
    data = pd.DataFrame(
        {
            "sign": [1, -1],
            "midpoint": [100.0, 100.0],
            "midpoint_next": [101.0, 99.0],
        }
    )
    table = con.create_table("test", data)

    import math

    # Default is the H&J ratio, divided by the future midpoint.
    ratio = table.mutate(
        pi_percent=percent_price_impact(table.sign, table.midpoint, table.midpoint_next)
    ).execute()
    assert ratio["pi_percent"].iloc[0] == pytest.approx((101.0 - 100.0) * 2 / 101.0)
    assert ratio["pi_percent"].iloc[1] == pytest.approx(-(99.0 - 100.0) * 2 / 99.0)

    log = table.mutate(
        pi_percent=percent_price_impact(
            table.sign, table.midpoint, table.midpoint_next, percent_method="log"
        )
    ).execute()
    assert log["pi_percent"].iloc[0] == pytest.approx(
        (math.log(101.0) - math.log(100.0)) * 2
    )
    assert log["pi_percent"].iloc[1] == pytest.approx(
        -(math.log(99.0) - math.log(100.0)) * 2
    )


def test_realized_spread_zero_sign(con):
    """Test realized spread with zero sign."""
    data = pd.DataFrame(
        {
            "sign": [0, 0],
            "price": [100.5, 99.5],
            "midpoint_next": [100.0, 100.0],
        }
    )
    table = con.create_table("test", data)

    result = table.mutate(
        rs_dollar=dollar_realized_spread(table.sign, table.price, table.midpoint_next)
    ).execute()

    # Zero sign should give zero realized spread
    assert result["rs_dollar"].iloc[0] == 0.0
    assert result["rs_dollar"].iloc[1] == 0.0


def test_price_impact_same_midpoints(con):
    """Test price impact when midpoints are equal."""
    data = pd.DataFrame(
        {
            "sign": [1, -1],
            "midpoint": [100.0, 100.0],
            "midpoint_next": [100.0, 100.0],
        }
    )
    table = con.create_table("test", data)

    result = table.mutate(
        pi_dollar=dollar_price_impact(table.sign, table.midpoint, table.midpoint_next)
    ).execute()

    # When midpoints are equal, should be corrected to null
    assert pd.isna(result["pi_dollar"].iloc[0])
    assert pd.isna(result["pi_dollar"].iloc[1])


def test_merge_future_nbbo_applies_the_horizon_in_nanoseconds(con):
    """The horizon is read at nanosecond precision when both sides carry the key.

    `timestamp` is only microsecond-resolution, so a quote 500 nanoseconds past
    the horizon shares a microsecond with it and is indistinguishable from a
    quote sitting exactly on it. Matching on `timestamp` takes that quote;
    matching on `timestamp_ns` must not.
    """
    base = pd.Timestamp("2020-01-02 09:30:00")
    delay = timedelta(minutes=5)
    horizon_ns = base.value + int(delay.total_seconds()) * 1_000_000_000

    # Trades arrive already matched to the quote in force, as `compute_rs_and_pi`
    # passes them, so the NBBO columns collide and the future ones take `_next`.
    trades = pd.DataFrame(
        {
            "symbol": ["AAPL"],
            "timestamp": [base],
            "timestamp_ns": [base.value],
            "price": [100.0],
            "best_bid": [99.5],
            "best_ask": [100.5],
            "midpoint": [100.0],
        }
    )
    # The second quote is 500 nanoseconds past the horizon, inside the same
    # microsecond, so its `timestamp` lands exactly on the horizon.
    quote_times = [base + timedelta(minutes=4), base + delay]
    nbbo = pd.DataFrame(
        {
            "symbol": ["AAPL", "AAPL"],
            "timestamp": quote_times,
            "timestamp_ns": [quote_times[0].value, horizon_ns + 500],
            "best_bid": [10.0, 20.0],
            "best_ask": [11.0, 21.0],
        }
    )

    result = merge_future_nbbo(
        con.create_table("trades_ns", trades),
        con.create_table("nbbo_ns", nbbo),
        delay=delay,
    ).execute()

    # That quote is after the horizon, so the earlier one stands: (10 + 11) / 2.
    assert result["midpoint_next"].iloc[0] == pytest.approx(10.5)

    # Without the nanosecond key the join falls back to `timestamp`, where the
    # same quote sits on the horizon and is taken instead: (20 + 21) / 2.
    fallback = merge_future_nbbo(
        con.create_table("trades_us", trades.drop(columns="timestamp_ns")),
        con.create_table("nbbo_us", nbbo.drop(columns="timestamp_ns")),
        delay=delay,
    ).execute()

    assert fallback["midpoint_next"].iloc[0] == pytest.approx(20.5)
