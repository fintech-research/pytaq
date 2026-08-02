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
