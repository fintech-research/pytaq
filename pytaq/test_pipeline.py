"""End-to-end tests, one per supported usage path, plus the gaps around them.

Everything below runs the stages together rather than one at a time. That is
the shape of test that catches the composition bugs: the trade-to-quote match
and the null handling both passed their unit tests while being wrong in the
pipeline.
"""

import datetime

import pandas as pd
import pytest

from .cleaning.merge_quotes_nbbo import merge_quotes_nbbo
from .cleaning.official_nbbo import clean_official_complete_nbbo
from .cleaning.trades import clean_trades
from .conftest import DATE, seconds_at
from .metrics.effective_spreads import compute_effective_spreads
from .metrics.quoted_spreads import (
    compute_quote_inforce,
    compute_spreads,
    compute_weighted_averages,
    compute_weighted_spreads,
)
from .metrics.timestamps import filter_timestamp

CLOSE = datetime.datetime(2020, 1, 2, 16, 0)


# --------------------------------------------------------------------------
# End-to-end, per usage path
# --------------------------------------------------------------------------


def test_end_to_end_trades_to_effective_spreads(signed_trades):
    """Raw trades and NBBO in, effective spreads out.

    This is the path 1 and 2 workflow. Only opening the tables differs there,
    and that needs a live postgres server.

    """
    result = compute_effective_spreads(signed_trades).execute()

    assert len(result) == 4
    for column in ["DollarEffectiveSpread", "PercentEffectiveSpread"]:
        assert column in result.columns

    # Effective spread is twice the absolute distance to the midpoint, so it is
    # non-negative wherever the trade matched a quote.
    matched = result[result["midpoint"].notna()]
    assert len(matched) > 0
    assert (matched["DollarEffectiveSpread"] >= 0).all()


def test_end_to_end_quoted_spreads_and_daily_average(cleaned_nbbo):
    """NBBO in, one time-weighted daily number per symbol out."""
    with_inforce = compute_quote_inforce(cleaned_nbbo, end_timestamp=CLOSE)
    with_spreads = compute_spreads(with_inforce)

    daily = compute_weighted_averages(
        with_spreads,
        measures=["quoted_spread_dollar", "quoted_spread_percent"],
        groupby_col="symbol",
    ).execute()

    assert len(daily) == 1
    assert daily["symbol"].iloc[0] == "AAPL"
    assert daily["quoted_spread_dollar"].iloc[0] > 0


def test_inforce_runs_to_the_close_for_the_last_quote(cleaned_nbbo):
    """The last quote of the day is in force until end_timestamp."""
    result = (
        compute_quote_inforce(cleaned_nbbo, end_timestamp=CLOSE)
        .execute()
        .sort_values("timestamp")
    )

    # The three quotes are 100s apart, so the first two are in force 100s each.
    assert result["inforce"].tolist()[:2] == [100.0, 100.0]

    last_quote = result["timestamp"].iloc[-1]
    expected = (CLOSE - last_quote.to_pydatetime()).total_seconds()
    assert result["inforce"].iloc[-1] == pytest.approx(expected)


# --------------------------------------------------------------------------
# Modules that had no coverage
# --------------------------------------------------------------------------


def test_merge_quotes_nbbo_dedups_to_the_last_quote_per_timestamp(con):
    """Two quotes at the same microsecond collapse to the higher seqnum."""
    frame = pd.DataFrame(
        {
            "symbol": pd.Series(["A"] * 3, dtype="string"),
            "timestamp": pd.to_datetime(
                [
                    "2020-01-02 09:30:00",
                    "2020-01-02 09:30:00",
                    "2020-01-02 09:30:01",
                ]
            ),
            "best_bid": [99.9, 99.95, 100.0],
            "best_bidsizeshares": [100, 150, 200],
            "best_ask": [100.1, 100.05, 100.2],
            "best_asksizeshares": [100, 150, 200],
            "qu_seqnum": [1, 2, 3],
        }
    )
    quotes = con.create_table("quotes_for_merge", frame)

    result = (
        merge_quotes_nbbo(quotes, quotes)
        .execute()
        .sort_values(["timestamp", "qu_seqnum"])
    )

    assert len(result) == 2
    assert result["qu_seqnum"].tolist() == [2, 3]
    assert result["best_bid"].iloc[0] == 99.95


def test_merge_quotes_nbbo_can_keep_every_row(con):
    """keep_changes_only=False unions without deduplicating."""
    frame = pd.DataFrame(
        {
            "symbol": pd.Series(["A", "A"], dtype="string"),
            "timestamp": pd.to_datetime(["2020-01-02 09:30:00", "2020-01-02 09:30:00"]),
            "best_bid": [99.9, 99.95],
            "best_bidsizeshares": [100, 150],
            "best_ask": [100.1, 100.05],
            "best_asksizeshares": [100, 150],
            "qu_seqnum": [1, 2],
        }
    )
    quotes = con.create_table("quotes_no_dedup", frame)

    result = merge_quotes_nbbo(quotes, quotes, keep_changes_only=False).execute()

    # union() is UNION ALL here, so the table unioned with itself doubles.
    assert len(result) == 4


def test_filter_timestamp_bounds(cleaned_nbbo):
    """filter_timestamp accepts a column name or a column expression."""
    all_rows = cleaned_nbbo.execute()

    by_name = filter_timestamp(
        cleaned_nbbo,
        timestamp="timestamp",
        start_time=datetime.time(9, 31),
    ).execute()
    assert len(by_name) < len(all_rows)

    by_expression = filter_timestamp(
        cleaned_nbbo,
        timestamp=cleaned_nbbo.timestamp,
        start_time=datetime.time(9, 31),
    ).execute()
    assert len(by_expression) == len(by_name)


def test_filter_timestamp_with_no_bounds_is_a_no_op(cleaned_nbbo):
    result = filter_timestamp(cleaned_nbbo, timestamp="timestamp").execute()

    assert len(result) == len(cleaned_nbbo.execute())


def test_filter_timestamp_rejects_a_bad_argument(cleaned_nbbo):
    with pytest.raises(ValueError, match="Ibis Column or a column name"):
        filter_timestamp(cleaned_nbbo, timestamp=42)


def test_compute_weighted_spreads_daily(cleaned_nbbo):
    result = compute_weighted_spreads(
        date=DATE,
        off_nbbo_table=cleaned_nbbo,
        start_time=datetime.time(9, 0),
        end_time=datetime.time(16, 0),
    )

    assert result is not None
    frame = result.execute()
    assert len(frame) == 1
    assert frame["symbol"].iloc[0] == "AAPL"


def test_compute_weighted_spreads_returns_none_when_empty(cleaned_nbbo):
    """No quotes in the window means no daily number, not a crash."""
    result = compute_weighted_spreads(
        date=DATE,
        off_nbbo_table=cleaned_nbbo,
        start_time=datetime.time(15, 0),
        end_time=datetime.time(16, 0),
    )

    assert result is None


# --------------------------------------------------------------------------
# Cross-stage invariants
# --------------------------------------------------------------------------


def test_cleaning_preserves_trade_count_through_the_match(
    raw_trades, cleaned_nbbo, signed_trades
):
    """Matching to quotes must not silently drop or duplicate trades."""
    cleaned = clean_trades(raw_trades).execute()
    matched = signed_trades.execute()

    assert len(matched) == len(cleaned)


def test_symbol_and_timestamp_survive_every_stage(signed_trades):
    result = signed_trades.execute()

    assert result["symbol"].notna().all()
    assert result["timestamp"].notna().all()
    assert result["symbol"].unique().tolist() == ["AAPL"]


def test_time_windows_are_respected(raw_trades):
    """A trade outside the window is dropped, one inside is kept."""
    narrow = clean_trades(
        raw_trades,
        start_time=datetime.time(9, 31, 30),
        end_time=datetime.time(16, 0),
    ).execute()

    assert len(narrow) == 2
    assert (narrow["timestamp"].dt.time >= datetime.time(9, 31, 30)).all()


def test_official_nbbo_cleaning_is_idempotent_in_shape(raw_official_nbbo):
    """Cleaning twice is not meaningful, but the output shape is stable."""
    once = clean_official_complete_nbbo(raw_official_nbbo).execute()

    assert list(once.columns) == [
        "timestamp",
        "symbol",
        "best_bid",
        "best_bidsizeshares",
        "best_ask",
        "best_asksizeshares",
    ]
    assert len(once) == 3


def test_seconds_helper_matches_the_fixture_times(raw_trades_frame):
    """Guard the fixture helper itself, since every time assertion rests on it."""
    assert seconds_at(0) == 34200.0
    assert seconds_at(1) == 34260.0
    assert raw_trades_frame["TIME_M"].iloc[1] == seconds_at(1)


# --------------------------------------------------------------------------
# Realized spreads and price impacts
# --------------------------------------------------------------------------


def test_rs_and_pi_adds_a_column_set_per_sign(signed_trades):
    """Every sign algorithm gets its own four measures."""
    from .metrics.rs_and_pi import rs_and_pi

    # A five-minute-later midpoint, supplied directly rather than merged, so
    # this exercises the measure arithmetic on its own.
    prepared = signed_trades.mutate(midpoint_next=signed_trades.midpoint * 1.01)

    result = rs_and_pi(prepared, signs=["LR", "EMO"], suffix="5min").execute()

    for sign in ["LR", "EMO"]:
        for prefix in [
            "DollarRealizedSpread_",
            "PercentRealizedSpread_",
            "DollarPriceImpact_",
            "PercentPriceImpact_",
        ]:
            assert f"{prefix}{sign}5min" in result.columns

    # A buy whose midpoint rose has a positive price impact by construction.
    buys = result[result["BuySellLR"] == 1]
    if len(buys):
        assert (buys["DollarPriceImpact_LR5min"] > 0).all()


def test_compute_rs_and_pi_runs_end_to_end(signed_trades, cleaned_nbbo):
    """The full realized-spread path, including the future-NBBO merge.

    Regression test for #26: merge_future_nbbo ignored its suffix argument, so
    the join emitted best_ask_right while the caller read best_ask_next.
    """
    from .metrics.rs_and_pi import compute_rs_and_pi

    result = compute_rs_and_pi(
        signed_trades,
        off_nbbo_table=cleaned_nbbo,
        delay=datetime.timedelta(minutes=1),
        suffix="1min",
    ).execute()

    for prefix in [
        "DollarRealizedSpread_",
        "PercentRealizedSpread_",
        "DollarPriceImpact_",
        "PercentPriceImpact_",
    ]:
        assert f"{prefix}LR1min" in result.columns


def test_merge_future_nbbo_attaches_a_later_midpoint(signed_trades, cleaned_nbbo):
    """The merge brings in a midpoint from `delay` after the trade."""
    from .metrics.rs_and_pi import merge_future_nbbo

    result = merge_future_nbbo(
        signed_trades, cleaned_nbbo, delay=datetime.timedelta(minutes=1)
    ).execute()

    assert "midpoint_next" in result.columns
    assert "best_ask_next" in result.columns


def test_merge_future_nbbo_does_not_fan_out(signed_trades, cleaned_nbbo):
    """One row per trade.

    The previous implementation was an inequality left join, which matches
    every quote from the horizon onward rather than the nearest one, turning
    each trade into as many rows as there are later quotes.
    """
    from .metrics.rs_and_pi import merge_future_nbbo

    trades_in = signed_trades.count().execute()

    rows_out = (
        merge_future_nbbo(
            signed_trades, cleaned_nbbo, delay=datetime.timedelta(minutes=1)
        )
        .count()
        .execute()
    )

    assert rows_out == trades_in


def test_effective_spreads_need_no_hand_built_indicators(signed_trades):
    """Regression test for #27.

    compute_effective_spreads used to filter on `lock` and `cross` columns
    that nothing in the package produced, so it could not be called on
    pipeline output at all. It now derives them from the prevailing quote.
    """
    from .metrics.effective_spreads import compute_effective_spreads

    result = compute_effective_spreads(signed_trades).execute()

    assert "DollarEffectiveSpread" in result.columns
    assert "PercentEffectiveSpread" in result.columns
    assert (result["DollarEffectiveSpread"].dropna() >= 0).all()
