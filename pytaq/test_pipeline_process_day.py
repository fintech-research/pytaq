"""Tests for the process_day orchestration entry point."""

import datetime

import pytest

from .cleaning.merge_quotes_nbbo import merge_quotes_nbbo
from .conftest import DATE
from .pipeline import DayResult, process_day


@pytest.fixture
def day(raw_trades, raw_official_nbbo):
    return process_day(raw_trades, raw_official_nbbo, date=DATE)


def test_returns_every_stage(day):
    assert isinstance(day, DayResult)
    for stage in [
        "trades",
        "nbbo",
        "matched",
        "signed",
        "effective_spreads",
        "quoted_spreads",
        "realized_spreads",
        "daily",
    ]:
        assert getattr(day, stage) is not None, stage


def test_daily_has_one_row_per_symbol(day):
    result = day.execute()

    assert len(result) == 1
    assert result["symbol"].iloc[0] == "AAPL"


def test_daily_carries_the_standard_measures(day):
    result = day.execute()

    for measure in ["effective_spread_dollar", "effective_spread_percent"]:
        for weight in ["", "_share_weighted", "_dollar_weighted"]:
            assert f"{measure}{weight}" in result.columns
    for measure in ["quoted_spread_dollar", "quoted_spread_percent"]:
        assert measure in result.columns
    for sign in ["lr", "emo", "clnv"]:
        assert f"realized_spread_dollar_{sign}_5min" in result.columns
        assert f"price_impact_dollar_{sign}_5min" in result.columns


def test_effective_spread_decomposes_into_realized_and_impact(day):
    """H&J define price impact as effective spread minus realized spread.

    The identity is not exact here because the two exclude locked and crossed
    markets at different instants: effective spread at the trade, realized
    spread and price impact at the horizon.
    """
    r = day.execute().iloc[0]

    es = r["effective_spread_dollar"]
    rs = r["realized_spread_dollar_lr_5min"]
    pi = r["price_impact_dollar_lr_5min"]

    assert rs + pi == pytest.approx(es, abs=0.05)


def test_horizon_can_be_skipped(raw_trades, raw_official_nbbo):
    day = process_day(raw_trades, raw_official_nbbo, date=DATE, horizon=None)

    assert day.realized_spreads is None
    result = day.execute()
    assert not [c for c in result.columns if "RealizedSpread" in c]


def test_horizon_suffix_names_the_columns(raw_trades, raw_official_nbbo):
    day = process_day(
        raw_trades,
        raw_official_nbbo,
        date=DATE,
        horizon=datetime.timedelta(minutes=1),
        horizon_suffix="1min",
    )

    assert "realized_spread_dollar_lr_1min" in day.execute().columns


def test_percent_method_is_threaded_through(raw_trades, raw_official_nbbo):
    ratio = process_day(raw_trades, raw_official_nbbo, date=DATE).execute()
    log = process_day(
        raw_trades, raw_official_nbbo, date=DATE, percent_method="log"
    ).execute()

    # Dollar measures are the same either way; percent ones need not be.
    assert ratio["effective_spread_dollar"].iloc[0] == pytest.approx(
        log["effective_spread_dollar"].iloc[0]
    )


def test_unknown_percent_method_is_rejected(raw_trades, raw_official_nbbo):
    with pytest.raises(ValueError, match="percent_method must be one of"):
        # Deliberately invalid: this is the test.
        process_day(raw_trades, raw_official_nbbo, date=DATE, percent_method="nope")  # ty: ignore[invalid-argument-type]


def test_everything_stays_lazy(day):
    """Building the pipeline must not execute anything."""
    import ibis

    for stage in [day.trades, day.nbbo, day.matched, day.signed, day.daily]:
        assert isinstance(stage, ibis.Table)


def test_retail_variants_are_opt_in(raw_trades, raw_official_nbbo):
    plain = process_day(raw_trades, raw_official_nbbo, date=DATE).execute()
    retail = process_day(
        raw_trades, raw_official_nbbo, date=DATE, track_retail=True
    ).execute()

    assert "realized_spread_dollar_bjz_5min" not in plain.columns
    assert "realized_spread_dollar_bjz_5min" in retail.columns


# ---------------------------------------------------------------------------
# merge_quotes_nbbo, on genuine cleaner output rather than a self-union (#50)
# ---------------------------------------------------------------------------


def test_cleaners_produce_union_compatible_schemas(raw_official_nbbo, con):
    """merge_quotes_nbbo unions the two, so their schemas must agree.

    Regression test: clean_nbbo omitted best_bidex, best_askex and qu_seqnum,
    so the documented reconstruction raised RelationError. qu_seqnum matters
    twice over, since the dedup ranks on it.
    """
    from .cleaning.nbbo import NBBO_COLS_CLEAN
    from .cleaning.quotes import QUOTES_COLS_CLEAN

    assert set(NBBO_COLS_CLEAN) == set(QUOTES_COLS_CLEAN)


def test_dedup_keeps_the_highest_sequence_number(con):
    """Regression test: ibis.row_number() is zero-based.

    Filtering on rank 1 kept the second-highest sequence number and dropped
    every timestamp holding a single quote. On one real day that returned
    18,651 rows where 550,307 were correct.
    """
    import pandas as pd

    data = pd.DataFrame(
        {
            "symbol": pd.Series(["A"] * 4, dtype="string"),
            "timestamp": pd.to_datetime(
                [
                    "2020-01-02 09:30:00",
                    "2020-01-02 09:30:00",
                    "2020-01-02 09:30:00",
                    "2020-01-02 09:30:01",  # a lone quote at its timestamp
                ]
            ),
            "qu_seqnum": [7, 9, 8, 3],
            "best_bid": [99.0, 99.5, 99.2, 100.0],
            "best_ask": [101.0, 101.5, 101.2, 102.0],
            "best_bidsizeshares": [100, 200, 300, 400],
            "best_asksizeshares": [100, 200, 300, 400],
            "best_bidex": pd.Series(["N"] * 4, dtype="string"),
            "best_askex": pd.Series(["N"] * 4, dtype="string"),
        }
    )
    empty = con.create_table("dedup_empty", data).filter(lambda t: t.qu_seqnum < 0)
    quotes = con.create_table("dedup_quotes", data)

    result = merge_quotes_nbbo(empty, quotes).execute()

    # One row per timestamp, and the lone quote is not dropped.
    assert len(result) == 2
    assert sorted(result["qu_seqnum"]) == [3, 9]
