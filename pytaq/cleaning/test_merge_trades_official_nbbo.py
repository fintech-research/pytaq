import datetime

import ibis
import pandas as pd
import pytest

from .merge_trades_official_nbbo import merge_trades_official_nbbo


@pytest.fixture
def duckdb_con():
    """Create a DuckDB connection for tests."""
    return ibis.connect("duckdb://:memory:")


@pytest.fixture
def quotes(duckdb_con):
    data = pd.DataFrame(
        {
            "symbol": pd.Series(["A", "A", "B"], dtype="string"),
            "timestamp": pd.to_datetime(
                [
                    "2020-01-02 09:30:00",
                    "2020-01-02 09:30:10",
                    "2020-01-02 09:30:00",
                ]
            ),
            "best_bid": [99.0, 100.0, 50.0],
            "best_ask": [101.0, 102.0, 52.0],
        }
    )
    return duckdb_con.create_table("off_nbbo", data)


@pytest.fixture
def trades(duckdb_con):
    data = pd.DataFrame(
        {
            "symbol": pd.Series(["A", "A", "A", "B"], dtype="string"),
            "timestamp": pd.to_datetime(
                [
                    "2020-01-02 09:29:59",  # before any quote
                    "2020-01-02 09:30:05",  # between the two A quotes
                    "2020-01-02 09:30:15",  # after the second A quote
                    "2020-01-02 09:30:01",  # after B's only quote
                ]
            ),
            "price": [100.0, 100.5, 101.5, 51.0],
        }
    )
    return duckdb_con.create_table("trades", data)


def test_merge_matches_last_prior_quote(trades, quotes):
    """Each trade takes the most recent quote at or before its timestamp."""
    result = (
        merge_trades_official_nbbo(trades, quotes)
        .execute()
        .sort_values(["symbol", "timestamp"])
        .reset_index(drop=True)
    )

    assert len(result) == 4

    # 09:30:05 sits between the two A quotes, so it takes the 09:30:00 one.
    assert result["best_bid"].iloc[1] == 99.0
    assert result["best_ask"].iloc[1] == 101.0

    # 09:30:15 is after the second A quote.
    assert result["best_bid"].iloc[2] == 100.0
    assert result["best_ask"].iloc[2] == 102.0


def test_merge_does_not_cross_symbols(trades, quotes):
    """B's trade must not pick up A's quote."""
    result = (
        merge_trades_official_nbbo(trades, quotes)
        .execute()
        .sort_values(["symbol", "timestamp"])
        .reset_index(drop=True)
    )

    b_row = result[result["symbol"] == "B"].iloc[0]
    assert b_row["best_bid"] == 50.0
    assert b_row["best_ask"] == 52.0


def test_merge_keeps_trade_with_no_prior_quote(trades, quotes):
    """A trade before any quote is kept, with null quote columns."""
    result = (
        merge_trades_official_nbbo(trades, quotes)
        .execute()
        .sort_values(["symbol", "timestamp"])
        .reset_index(drop=True)
    )

    first = result.iloc[0]
    assert first["price"] == 100.0
    assert pd.isna(first["best_bid"])
    assert pd.isna(first["best_ask"])


def test_merge_is_never_forward_looking(duckdb_con):
    """A quote that arrives after the trade must never be matched to it."""
    quote_data = pd.DataFrame(
        {
            "symbol": pd.Series(["A"], dtype="string"),
            "timestamp": pd.to_datetime(["2020-01-02 09:30:10"]),
            "best_bid": [99.0],
            "best_ask": [101.0],
        }
    )
    trade_data = pd.DataFrame(
        {
            "symbol": pd.Series(["A"], dtype="string"),
            "timestamp": pd.to_datetime(["2020-01-02 09:30:00"]),
            "price": [100.0],
        }
    )
    quotes_only_later = duckdb_con.create_table("later_quotes", quote_data)
    trade_first = duckdb_con.create_table("earlier_trade", trade_data)

    result = merge_trades_official_nbbo(trade_first, quotes_only_later).execute()

    assert len(result) == 1
    assert pd.isna(result["best_bid"].iloc[0])


# ---------------------------------------------------------------------------
# Trade-to-quote lag (#40)
# ---------------------------------------------------------------------------


@pytest.fixture
def same_instant(duckdb_con):
    """A quote in the same millisecond as the trade, and one 5ms earlier."""
    quotes = pd.DataFrame(
        {
            "symbol": pd.Series(["A", "A"], dtype="string"),
            "timestamp": pd.to_datetime(
                ["2020-01-02 09:30:00.000", "2020-01-02 09:30:00.005"]
            ),
            "best_bid": [99.0, 98.0],
            "best_ask": [101.0, 102.0],
        }
    )
    trades = pd.DataFrame(
        {
            "symbol": pd.Series(["A"], dtype="string"),
            "timestamp": pd.to_datetime(["2020-01-02 09:30:00.005"]),
            "price": [100.0],
        }
    )
    return (
        duckdb_con.create_table("lag_trades", trades),
        duckdb_con.create_table("lag_quotes", quotes),
    )


def test_default_lag_excludes_the_same_instant_quote(same_instant):
    """H&J specify a one-millisecond lag for DTAQ.

    A quote stamped in the same instant as the trade may be a consequence of
    it, so it is not the state the trader faced.
    """
    trades, quotes = same_instant

    result = merge_trades_official_nbbo(trades, quotes).execute()

    assert result["best_bid"].iloc[0] == 99.0
    assert result["best_ask"].iloc[0] == 101.0


def test_zero_lag_matches_contemporaneous_quotes(same_instant):
    """Passing timedelta(0) recovers the previous behaviour."""
    trades, quotes = same_instant

    result = merge_trades_official_nbbo(
        trades, quotes, lag=datetime.timedelta(0)
    ).execute()

    assert result["best_bid"].iloc[0] == 98.0
    assert result["best_ask"].iloc[0] == 102.0


def test_a_longer_lag_reaches_further_back(duckdb_con):
    """The lag is honoured as a duration, not just as a tiebreak."""
    quotes = pd.DataFrame(
        {
            "symbol": pd.Series(["A", "A"], dtype="string"),
            "timestamp": pd.to_datetime(
                ["2020-01-02 09:30:00.000", "2020-01-02 09:30:00.500"]
            ),
            "best_bid": [99.0, 98.0],
            "best_ask": [101.0, 102.0],
        }
    )
    trades = pd.DataFrame(
        {
            "symbol": pd.Series(["A"], dtype="string"),
            "timestamp": pd.to_datetime(["2020-01-02 09:30:00.600"]),
            "price": [100.0],
        }
    )
    t = duckdb_con.create_table("long_lag_trades", trades)
    q = duckdb_con.create_table("long_lag_quotes", quotes)

    # 1ms back from 09:30:00.600 is still after the 09:30:00.500 quote.
    near = merge_trades_official_nbbo(t, q).execute()
    assert near["best_bid"].iloc[0] == 98.0

    # 200ms back lands before it, so the earlier quote applies.
    far = merge_trades_official_nbbo(
        t, q, lag=datetime.timedelta(milliseconds=200)
    ).execute()
    assert far["best_bid"].iloc[0] == 99.0


def test_lag_does_not_drop_trades(same_instant):
    """Changing the lag must not change the trade count."""
    trades, quotes = same_instant

    for lag in [datetime.timedelta(0), datetime.timedelta(milliseconds=1)]:
        result = merge_trades_official_nbbo(trades, quotes, lag=lag).execute()
        assert len(result) == 1


def test_lag_is_applied_at_nanosecond_precision(duckdb_con):
    """Two quotes inside one microsecond are distinguishable (#52).

    Matching on `timestamp` alone treats everything within a microsecond as
    simultaneous, which is exactly the resolution at which the ordering of a
    trade and a quote is decided.
    """
    quotes = pd.DataFrame(
        {
            "symbol": pd.Series(["A", "A"], dtype="string"),
            "date": [datetime.date(2020, 1, 2)] * 2,
            "time_m": [datetime.time(9, 30, 0, 100)] * 2,
            "time_m_nano": [100, 900],
            "best_bid": [99.0, 98.0],
            "best_ask": [101.0, 102.0],
        }
    )
    trades = pd.DataFrame(
        {
            "symbol": pd.Series(["A"], dtype="string"),
            "date": [datetime.date(2020, 1, 2)],
            "time_m": [datetime.time(9, 30, 0, 100)],
            "time_m_nano": [500],
            "price": [100.0],
        }
    )
    from .common import merge_datetime

    q = merge_datetime(duckdb_con.create_table("ns_quotes", quotes))
    t = merge_datetime(duckdb_con.create_table("ns_trades", trades))

    # Zero lag, so the only thing separating them is the nanosecond remainder.
    result = merge_trades_official_nbbo(t, q, lag=datetime.timedelta(0)).execute()

    # The trade is at +500ns, so it sees the +100ns quote, not the +900ns one.
    assert result["best_bid"].iloc[0] == 99.0
    assert result["best_ask"].iloc[0] == 101.0
