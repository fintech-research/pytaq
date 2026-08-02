"""Shared fixtures.

Raw frames are shaped like the WRDS tables, with uppercase columns and
``date`` / ``time_m`` still separate, so tests exercise the same normalisation
real data goes through.
"""

import datetime

import ibis
import pandas as pd
import pytest

DATE = datetime.date(2020, 1, 2)

# 09:30:00, 09:31:00, 09:32:00, 09:33:00 as seconds since midnight
_OPEN = 34200.0


def seconds_at(minute: int, second: float = 0.0) -> float:
    """Seconds since midnight for a time offset from 09:30:00."""
    return _OPEN + minute * 60 + second


@pytest.fixture
def con():
    """In-memory DuckDB connection.

    DuckDB rather than polars: Ibis 12's polars backend implements no window
    functions, so it cannot run most of this package.
    """
    return ibis.connect("duckdb://:memory:")


@pytest.fixture
def raw_trades_frame():
    """Four trades for one symbol: up, flat, down."""
    n = 4
    return pd.DataFrame(
        {
            "DATE": [DATE] * n,
            "TIME_M": [seconds_at(0, 0.5), seconds_at(1), seconds_at(2), seconds_at(3)],
            "SYM_ROOT": pd.Series(["AAPL"] * n, dtype="string"),
            "SYM_SUFFIX": pd.Series([None] * n, dtype="string"),
            "EX": pd.Series(["N", "D", "N", "D"], dtype="string"),
            "SIZE": [100, 200, 300, 400],
            "PRICE": [10.0, 10.5, 10.5, 10.2],
            "TR_SEQNUM": [1, 2, 3, 4],
            "TR_SCOND": pd.Series(["@"] * n, dtype="string"),
            "TR_CORR": pd.Series(["00"] * n, dtype="string"),
        }
    )


@pytest.fixture
def raw_official_nbbo_frame():
    """Three official NBBO rows for one symbol."""
    n = 3
    return pd.DataFrame(
        {
            "DATE": [DATE] * n,
            "TIME_M": [seconds_at(0), seconds_at(1, 40), seconds_at(3, 20)],
            "SYM_ROOT": pd.Series(["AAPL"] * n, dtype="string"),
            "SYM_SUFFIX": pd.Series([None] * n, dtype="string"),
            "BEST_BID": [9.9, 10.1, 10.0],
            "BEST_BIDSIZESHARES": [100, 200, 300],
            "BEST_ASK": [10.6, 10.8, 10.7],
            "BEST_ASKSIZESHARES": [100, 200, 300],
        }
    )


@pytest.fixture
def raw_trades(con, raw_trades_frame):
    return con.create_table("raw_trades", raw_trades_frame)


@pytest.fixture
def raw_official_nbbo(con, raw_official_nbbo_frame):
    return con.create_table("raw_official_nbbo", raw_official_nbbo_frame)


@pytest.fixture
def cleaned_nbbo(raw_official_nbbo):
    """An NBBO table with symbol, timestamp and midpoint, ready for metrics."""
    from .cleaning.official_nbbo import clean_official_complete_nbbo

    t = clean_official_complete_nbbo(raw_official_nbbo)
    return t.mutate(midpoint=(t.best_bid + t.best_ask) / 2)


@pytest.fixture
def signed_trades(raw_trades, cleaned_nbbo):
    """Trades cleaned, matched to the NBBO and signed."""
    from .cleaning.merge_trades_official_nbbo import merge_trades_official_nbbo
    from .cleaning.trades import clean_trades
    from .metrics.signs import sign_trades

    trades = clean_trades(raw_trades)
    matched = merge_trades_official_nbbo(trades, cleaned_nbbo)
    return sign_trades(matched)
