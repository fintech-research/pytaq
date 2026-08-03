import datetime

import ibis
import pandas as pd
import pytest

from .nbbo import NBBO_COLS_CLEAN, clean_nbbo, filter_changes_only


@pytest.fixture
def duckdb_con():
    """Create a DuckDB connection for tests."""
    return ibis.connect("duckdb://:memory:")


def _raw_nbbo(n_rows=4, qu_cancel=None):
    """Build a raw NBBO frame shaped like the WRDS table (uppercase columns)."""
    return pd.DataFrame(
        {
            "DATE": [datetime.date(2020, 1, 2)] * n_rows,
            "TIME_M": [34200.0 + i for i in range(n_rows)],
            "SYM_ROOT": pd.Series(["A"] * n_rows, dtype="string"),
            "SYM_SUFFIX": pd.Series([None] * n_rows, dtype="string"),
            "BEST_BID": [99.0, 99.0, 100.0, 100.0][:n_rows],
            "BEST_BIDSIZ": [1.0, 1.0, 2.0, 2.0][:n_rows],
            "BEST_ASK": [101.0, 101.0, 102.0, 102.0][:n_rows],
            "BEST_ASKSIZ": [1.0, 1.0, 2.0, 2.0][:n_rows],
            "QU_COND": pd.Series(["R"] * n_rows, dtype="string"),
            "QU_CANCEL": pd.Series(
                qu_cancel if qu_cancel is not None else [None] * n_rows,
                dtype="string",
            ),
            "BEST_BIDEX": pd.Series(["N"] * n_rows, dtype="string"),
            "BEST_ASKEX": pd.Series(["N"] * n_rows, dtype="string"),
            "QU_SEQNUM": list(range(1, n_rows + 1)),
        }
    )


def test_clean_nbbo_keeps_null_qu_cancel(duckdb_con):
    """Null cancel flags must not wipe out the whole table.

    Regression test: `qu_cancel != "B"` is NULL for a null cancel flag, so
    every quote was discarded. On a 4-row input this returned 0 rows.
    """
    table = duckdb_con.create_table("nbbo_null_cancel", _raw_nbbo())

    result = clean_nbbo(table).execute()

    assert len(result) > 0
    assert list(result.columns) == NBBO_COLS_CLEAN


def test_clean_nbbo_still_drops_canceled(duckdb_con):
    """Explicitly canceled quotes are still removed."""
    raw = _raw_nbbo(qu_cancel=["B", "B", "B", "B"])
    table = duckdb_con.create_table("nbbo_canceled", raw)

    result = clean_nbbo(table).execute()

    assert len(result) == 0


def test_filter_changes_only_keeps_first_row_per_symbol(duckdb_con):
    """The opening quote of each symbol must survive.

    Regression test: comparing against `lag()` with `!=` yields NULL on the
    first row of every group, so the opening quote of each symbol was dropped.
    """
    data = pd.DataFrame(
        {
            "symbol": pd.Series(["A", "A", "A", "B", "B"], dtype="string"),
            "timestamp": pd.to_datetime(
                [
                    "2020-01-02 09:30:00",
                    "2020-01-02 09:30:01",
                    "2020-01-02 09:30:02",
                    "2020-01-02 09:30:00",
                    "2020-01-02 09:30:01",
                ]
            ),
            "best_bid": [99.0, 99.0, 100.0, 50.0, 51.0],
            "best_ask": [101.0, 101.0, 102.0, 52.0, 53.0],
            "best_bidsizeshares": [100, 100, 200, 300, 300],
            "best_asksizeshares": [100, 100, 200, 300, 300],
        }
    )
    table = duckdb_con.create_table("nbbo_changes", data)

    result = filter_changes_only(table).execute().sort_values(["symbol", "timestamp"])

    # A: opening quote plus the 09:30:02 change. The 09:30:01 repeat goes.
    # B: opening quote plus the 09:30:01 change.
    assert len(result) == 4
    assert list(result["symbol"]) == ["A", "A", "B", "B"]
    assert list(result["best_bid"]) == [99.0, 100.0, 50.0, 51.0]


def test_filter_changes_only_treats_null_to_null_as_unchanged(duckdb_con):
    """Consecutive all-null quotes collapse, but a null-to-value move counts."""
    data = pd.DataFrame(
        {
            "symbol": pd.Series(["A"] * 4, dtype="string"),
            "timestamp": pd.to_datetime(
                [
                    "2020-01-02 09:30:00",
                    "2020-01-02 09:30:01",
                    "2020-01-02 09:30:02",
                    "2020-01-02 09:30:03",
                ]
            ),
            "best_bid": [99.0, None, None, 99.0],
            "best_ask": [101.0, None, None, 101.0],
            "best_bidsizeshares": [100.0, None, None, 100.0],
            "best_asksizeshares": [100.0, None, None, 100.0],
        }
    )
    table = duckdb_con.create_table("nbbo_nulls", data)

    result = filter_changes_only(table).execute().sort_values("timestamp")

    # Row 0 kept (first), row 1 kept (value -> null is a change), row 2 dropped
    # (null -> null is not), row 3 kept (null -> value is a change).
    assert len(result) == 3
    assert [str(ts.time()) for ts in result["timestamp"]] == [
        "09:30:00",
        "09:30:01",
        "09:30:03",
    ]


def test_filter_changes_only_is_deterministic_with_tied_timestamps(duckdb_con):
    """Quotes sharing a timestamp must not make the output vary between runs.

    Regression test for #33. Ordering on (symbol, timestamp) alone leaves
    lag() free to pick any of the tied rows. On one real day of AAPL NBBO
    data about 18,000 rows share a timestamp with another, and three runs of
    the same query returned three different row counts.
    """
    n = 60
    data = pd.DataFrame(
        {
            "symbol": pd.Series(["A"] * n, dtype="string"),
            # Only three distinct timestamps across 60 rows: heavy ties.
            "timestamp": pd.to_datetime(
                ["2020-01-02 09:30:00", "2020-01-02 09:30:01", "2020-01-02 09:30:02"]
                * (n // 3)
            ),
            "qu_seqnum": list(range(n)),
            "best_bid": [99.0 + (i % 7) for i in range(n)],
            "best_ask": [101.0 + (i % 5) for i in range(n)],
            "best_bidsizeshares": [100 * (i % 3 + 1) for i in range(n)],
            "best_asksizeshares": [100 * (i % 4 + 1) for i in range(n)],
        }
    )
    table = duckdb_con.create_table("tied_timestamps", data)

    counts = {len(filter_changes_only(table).execute()) for _ in range(5)}

    assert len(counts) == 1, f"non-deterministic row count across runs: {counts}"


def test_filter_changes_only_drops_the_helper_column(duckdb_con):
    """The materialised comparison column must not leak into the output."""
    data = pd.DataFrame(
        {
            "symbol": pd.Series(["A", "A"], dtype="string"),
            "timestamp": pd.to_datetime(["2020-01-02 09:30:00", "2020-01-02 09:30:01"]),
            "qu_seqnum": [1, 2],
            "best_bid": [99.0, 100.0],
            "best_ask": [101.0, 102.0],
            "best_bidsizeshares": [100, 200],
            "best_asksizeshares": [100, 200],
        }
    )
    table = duckdb_con.create_table("helper_column", data)

    result = filter_changes_only(table).execute()

    assert "_changed" not in result.columns
    assert set(result.columns) == set(data.columns)


def test_filter_changes_only_without_a_sequence_column(duckdb_con):
    """Falls back to timestamp ordering when there is no tiebreaker."""
    data = pd.DataFrame(
        {
            "symbol": pd.Series(["A", "A", "A"], dtype="string"),
            "timestamp": pd.to_datetime(
                [
                    "2020-01-02 09:30:00",
                    "2020-01-02 09:30:01",
                    "2020-01-02 09:30:02",
                ]
            ),
            "best_bid": [99.0, 99.0, 100.0],
            "best_ask": [101.0, 101.0, 102.0],
            "best_bidsizeshares": [100, 100, 200],
            "best_asksizeshares": [100, 100, 200],
        }
    )
    table = duckdb_con.create_table("no_seqnum", data)

    result = filter_changes_only(table, sequence_col=None).execute()

    # Timestamps are unique here, so the result is well defined regardless.
    assert len(result) == 2
