"""Tests for the process_day orchestration entry point."""

import datetime

import pandas as pd
import pytest

from .cleaning.merge_quotes_nbbo import merge_quotes_nbbo
from .conftest import DATE
from .pipeline import DayResult, process_day


def _raw_nbbo_frame(rows: list[tuple[float, float, float]]) -> pd.DataFrame:
    """Raw official NBBO rows from (seconds since midnight, bid, ask)."""
    n = len(rows)
    return pd.DataFrame(
        {
            "DATE": [DATE] * n,
            "TIME_M": [r[0] for r in rows],
            "SYM_ROOT": pd.Series(["AAPL"] * n, dtype="string"),
            "SYM_SUFFIX": pd.Series([None] * n, dtype="string"),
            "BEST_BID": [r[1] for r in rows],
            "BEST_BIDSIZESHARES": [100] * n,
            "BEST_ASK": [r[2] for r in rows],
            "BEST_ASKSIZESHARES": [100] * n,
        }
    )


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
# Quoted-spread statistics: the window and the locked-and-crossed exclusion
# ---------------------------------------------------------------------------


@pytest.fixture
def nbbo_with_preopen_and_locked(con):
    """Four quotes: one before the open, one locked, two ordinary.

    09:00  spread 1.00, before the trade window
    09:30  spread 0.10, stands 900s
    09:45  locked, stands 900s
    10:00  spread 0.20, stands until the close
    """
    frame = _raw_nbbo_frame(
        [
            (9 * 3600, 10.0, 11.0),  # 09:00, spread 1.00
            (9 * 3600 + 1800, 10.45, 10.55),  # 09:30, spread 0.10
            (9 * 3600 + 2700, 10.5, 10.5),  # 09:45, locked
            (10 * 3600, 10.4, 10.6),  # 10:00, spread 0.20
        ]
    )
    return con.create_table("nbbo_preopen_locked", frame)


def test_quoted_spread_drops_preopen_and_locked_quotes(
    raw_trades, nbbo_with_preopen_and_locked
):
    """Holden and Jacobsen delete both before time-weighting.

    Their code deletes quotes before 09:30 once the NBBO is built
    (`if time lt ("9:30:00"t) then delete`) and deletes locked and crossed
    quotes after timing them but before weighting
    (`if BestOfr=BestBid or BestOfr<BestBid then delete`). process_day used to do
    neither, so a spread quoted before anyone could trade against it, and a
    spread of zero from a locked market, both entered the day's average.
    """
    result = process_day(raw_trades, nbbo_with_preopen_and_locked, date=DATE).execute()

    # Only 09:30 (900s at 0.10) and 10:00 (21,600s at 0.20) survive.
    expected = (0.10 * 900 + 0.20 * 21_600) / (900 + 21_600)
    assert result["quoted_spread_dollar"].iloc[0] == pytest.approx(expected)


def test_quoted_spread_exclusions_are_optional(
    raw_trades, nbbo_with_preopen_and_locked
):
    """Both exclusions can be turned off, and then every quote counts."""
    result = process_day(
        raw_trades,
        nbbo_with_preopen_and_locked,
        date=DATE,
        quoted_spread_start_time=None,
        exclude_locked_crossed=False,
    ).execute()

    expected = (1.00 * 1800 + 0.10 * 900 + 0.0 * 900 + 0.20 * 21_600) / 25_200
    assert result["quoted_spread_dollar"].iloc[0] == pytest.approx(expected)


# ---------------------------------------------------------------------------
# Matching precision, end to end
# ---------------------------------------------------------------------------


def test_the_lag_is_applied_at_nanosecond_precision(con):
    """One nanosecond of lag has to be able to separate two quotes.

    The default lag is a single nanosecond, following H&J's 2018 DTAQ code, so
    the quote stamped in the same nanosecond as the trade must be excluded and
    the one a nanosecond earlier must win. That is only possible because the
    cleaned tables carry `timestamp_ns`: on the microsecond `timestamp` both
    quotes fall in the same microsecond as the trade, the lag floors to zero, and
    the later quote would win with a midpoint of 20.5 instead of 10.5.
    """
    # Trade at 09:30:00.002000000, so the lagged time is 09:30:00.001999999.
    trades = pd.DataFrame(
        {
            "DATE": [DATE],
            "TIME_M": [34200.002],
            "TIME_M_NANO": [0],
            "SYM_ROOT": pd.Series(["AAPL"], dtype="string"),
            "SYM_SUFFIX": pd.Series([None], dtype="string"),
            "EX": pd.Series(["N"], dtype="string"),
            "SIZE": [100],
            "PRICE": [10.5],
            "TR_SEQNUM": [1],
            "TR_SCOND": pd.Series(["@"], dtype="string"),
            "TR_CORR": pd.Series(["00"], dtype="string"),
        }
    )
    # One quote exactly on the lagged time, one in the trade's own nanosecond.
    nbbo = _raw_nbbo_frame([(34200.001999, 10.0, 11.0), (34200.002, 20.0, 21.0)])
    nbbo["TIME_M_NANO"] = [999, 0]

    day = process_day(
        con.create_table("ns_trades", trades),
        con.create_table("ns_nbbo", nbbo),
        date=DATE,
    )
    matched = day.matched.execute()

    assert len(matched) == 1
    assert matched["midpoint"].iloc[0] == pytest.approx(10.5)


def test_cleaned_trades_keep_the_nanosecond_key(raw_trades):
    """Dropping it silently demoted every downstream match to microseconds."""
    from .cleaning.trades import clean_trades

    assert "timestamp_ns" in clean_trades(raw_trades).columns


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


def test_dedup_separates_quotes_inside_one_microsecond(con):
    """Two quotes 500ns apart are two NBBO states, not one.

    H&J dedup the complete NBBO on `time_m`, which resolves to the nanosecond in
    DTAQ. Deduping on the microsecond `timestamp` instead throws away the second
    of any two quotes sharing a microsecond: on AAPL for 2020-01-02 that is 2,655
    NBBO rows, every one of them separable in nanoseconds.
    """
    import pandas as pd

    base = pd.Timestamp("2020-01-02 09:30:00")
    data = pd.DataFrame(
        {
            "symbol": pd.Series(["A"] * 3, dtype="string"),
            # The first two share a microsecond and differ by 500ns.
            "timestamp": [base, base, base + pd.Timedelta("1us")],
            "timestamp_ns": [base.value, base.value + 500, base.value + 1000],
            "qu_seqnum": [1, 2, 3],
            "best_bid": [99.0, 99.5, 99.7],
            "best_ask": [101.0, 101.5, 101.7],
            "best_bidsizeshares": [100, 200, 300],
            "best_asksizeshares": [100, 200, 300],
            "best_bidex": pd.Series(["N"] * 3, dtype="string"),
            "best_askex": pd.Series(["N"] * 3, dtype="string"),
        }
    )
    quotes = con.create_table("ns_dedup_quotes", data)
    empty = quotes.filter(quotes.qu_seqnum < 0)

    result = merge_quotes_nbbo(empty, quotes).execute()

    assert len(result) == 3, "quotes separated by nanoseconds must all survive"
    assert sorted(result["qu_seqnum"]) == [1, 2, 3]


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
