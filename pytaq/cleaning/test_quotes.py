import datetime
from decimal import Decimal

import ibis
import pandas as pd
import pytest

from .quotes import (
    QUOTES_COLS_CLEAN,
    clean_quote_table,
    filter_quote_table,
    neutralize_withdrawn_quotes,
)


@pytest.fixture
def duckdb_con():
    """Create a DuckDB connection for tests."""
    return ibis.connect("duckdb://:memory:")


def test_neutralize_withdrawn_quotes_basic(duckdb_con):
    """Withdrawn sides are nulled; the row survives."""
    data = {
        "bid": [10.0, 0.0, None, 10.5, -1.0],
        "ask": [10.5, 10.5, 11.0, None, 11.0],
        "bidsiz": [100, 100, 100, 100, 100],
        "asksiz": [100, 100, 100, 0, 100],
    }
    table = duckdb_con.create_table("quotes", data)

    result = neutralize_withdrawn_quotes(table).execute()

    # Every row survives; only the withdrawn side is nulled. Deleting the row
    # would leave the venue's previous quote standing in the NBBO, which is the
    # error Holden and Jacobsen's Quote Filter 5 warns against.
    assert len(result) == 5
    # Row 0 is fully live.
    assert result["bid"].iloc[0] == 10.0
    assert result["ask"].iloc[0] == 10.5
    # Rows 1 and 4 have a non-positive bid; the ask survives.
    assert pd.isna(result["bid"].iloc[1])
    assert result["ask"].iloc[1] == 10.5
    assert pd.isna(result["bid"].iloc[4])
    assert result["ask"].iloc[4] == 11.0
    # Row 2 has a null bid; the ask survives.
    assert pd.isna(result["bid"].iloc[2])
    assert result["ask"].iloc[2] == 11.0
    # Row 3 has a null ask and a zero ask size; the bid survives.
    assert pd.isna(result["ask"].iloc[3])
    assert result["bid"].iloc[3] == 10.5


def test_neutralize_withdrawn_quotes_all_valid(duckdb_con):
    """Test that valid quotes are kept."""
    data = {
        "bid": [10.0, 11.0, 12.0],
        "ask": [10.5, 11.5, 12.5],
        "bidsiz": [100, 200, 300],
        "asksiz": [100, 200, 300],
    }
    table = duckdb_con.create_table("quotes_valid", data)

    result = neutralize_withdrawn_quotes(table).execute()

    assert len(result) == 3


def test_filter_quote_table_qu_cond(duckdb_con):
    """Test filtering by quote condition."""
    data = {
        "bid": [10.0, 10.0, 10.0],
        "ask": [10.5, 10.5, 10.5],
        "bidsiz": [100, 100, 100],
        "asksiz": [100, 100, 100],
        "qu_cond": ["A", "B", "Z"],  # Z is not in HJ_KEEP_QU_COND
        "qu_cancel": ["", "", ""],
        "natbbo_ind": ["1", "1", "1"],
        "qu_source": ["C", "C", "C"],
    }
    table = duckdb_con.create_table("quotes_cond", data)

    result = filter_quote_table(table, keep_qu_cond=["A", "B"]).execute()

    # All three rows survive; the abnormal-condition quote has both sides nulled.
    assert len(result) == 3
    abnormal = result[result["qu_cond"] == "Z"].iloc[0]
    assert pd.isna(abnormal["bid"])
    assert pd.isna(abnormal["ask"])
    normal = result[result["qu_cond"].isin(["A", "B"])]
    assert normal["bid"].notna().all()
    assert normal["ask"].notna().all()


def test_filter_quote_table_canceled(duckdb_con):
    """Test filtering of canceled quotes."""
    data = {
        "bid": [10.0, 10.0, 10.0],
        "ask": [10.5, 10.5, 10.5],
        "bidsiz": [100, 100, 100],
        "asksiz": [100, 100, 100],
        "qu_cond": ["A", "A", "A"],
        "qu_cancel": ["", "B", "C"],  # B means canceled
        "natbbo_ind": ["1", "1", "1"],
        "qu_source": ["C", "C", "C"],
    }
    table = duckdb_con.create_table("quotes_cancel", data)

    result = filter_quote_table(
        table, exclude_canceled_quotes=True, keep_qu_cond=None
    ).execute()

    # All rows survive; the cancelled one has both sides nulled.
    assert len(result) == 3
    canceled = result[result["qu_cancel"] == "B"].iloc[0]
    assert pd.isna(canceled["bid"])
    assert pd.isna(canceled["ask"])
    assert result[result["qu_cancel"] != "B"]["bid"].notna().all()


def test_filter_quote_table_crossed_markets(duckdb_con):
    """Test filtering of crossed markets (bid > ask)."""
    data = {
        "bid": [10.0, 11.0, 10.0],
        "ask": [10.5, 10.5, 10.5],  # Second row is crossed
        "bidsiz": [100, 100, 100],
        "asksiz": [100, 100, 100],
        "qu_cond": ["A", "A", "A"],
        "qu_cancel": ["", "", ""],
        "natbbo_ind": ["1", "1", "1"],
        "qu_source": ["C", "C", "C"],
    }
    table = duckdb_con.create_table("quotes_crossed", data)

    result = filter_quote_table(
        table, exclude_crossed_markets=True, keep_qu_cond=None
    ).execute()

    # All rows survive; the crossed quote has both sides nulled, since a venue
    # quoting its own bid above its own ask is not trustworthy on either side.
    assert len(result) == 3
    crossed = result.iloc[1]
    assert pd.isna(crossed["bid"])
    assert pd.isna(crossed["ask"])
    live = result.drop(index=1)
    assert (live["bid"] <= live["ask"]).all()


def test_filter_quote_table_abnormal_spreads(duckdb_con):
    """Test filtering of abnormal spreads."""
    data = {
        "bid": [10.0, 10.0, 10.0],
        "ask": [10.5, 20.0, 11.0],  # Second row has spread of 10.0
        "bidsiz": [100, 100, 100],
        "asksiz": [100, 100, 100],
        "qu_cond": ["A", "A", "A"],
        "qu_cancel": ["", "", ""],
        "natbbo_ind": ["1", "1", "1"],
        "qu_source": ["C", "C", "C"],
    }
    table = duckdb_con.create_table("quotes_spread", data)

    result = filter_quote_table(
        table,
        exclude_abnormal_spreads=True,
        max_spread=Decimal("5.0"),
        keep_qu_cond=None,
    ).execute()

    # All rows survive; the wide-spread quote has both sides nulled.
    assert len(result) == 3
    wide = result.iloc[1]
    assert pd.isna(wide["bid"])
    assert pd.isna(wide["ask"])
    assert result.iloc[0]["ask"] == 10.5
    assert result.iloc[2]["ask"] == 11.0


def test_filter_quote_table_nbbo_only(duckdb_con):
    """Test filtering for NBBO quotes only."""
    data = {
        "bid": [10.0, 10.0, 10.0, 10.0],
        "ask": [10.5, 10.5, 10.5, 10.5],
        "bidsiz": [100, 100, 100, 100],
        "asksiz": [100, 100, 100, 100],
        "qu_cond": ["A", "A", "A", "A"],
        "qu_cancel": ["", "", "", ""],
        "qu_source": ["C", "C", "N", "X"],
        "natbbo_ind": ["1", "0", "4", "1"],
    }
    table = duckdb_con.create_table("quotes_nbbo", data)

    result = filter_quote_table(table, nbbo_only=True, keep_qu_cond=None).execute()

    # Should only keep rows where (qu_source='C' AND natbbo_ind='1') OR (qu_source='N' AND natbbo_ind='4')
    assert len(result) == 2
    assert result["qu_source"].iloc[0] == "C"
    assert result["qu_source"].iloc[1] == "N"


def test_clean_quote_table_basic(duckdb_con):
    """Test complete quote cleaning pipeline."""
    data = pd.DataFrame(
        {
            "date": [datetime.date(2023, 1, 15), datetime.date(2023, 1, 15)],
            "time_m": [34200.0, 34201.0],
            "sym_root": ["AAPL", "MSFT"],
            "sym_suffix": pd.Series([None, None], dtype="string"),
            "bid": [150.0, 250.0],
            "ask": [150.5, 250.5],
            "bidsiz": [10, 20],  # In round lots
            "asksiz": [15, 25],
            "qu_cond": ["A", "A"],
            "qu_cancel": ["", ""],
            "natbbo_ind": ["1", "1"],
            "qu_source": ["C", "C"],
            "qu_seqnum": [1, 2],
            "ex": ["N", "N"],
        }
    )
    table = duckdb_con.create_table("quotes_clean", data)

    result = clean_quote_table(table, keep_qu_cond=["A"]).execute()

    # Check that output has correct columns
    assert set(QUOTES_COLS_CLEAN).issubset(set(result.columns))

    # Check conversion of size from round lots to shares
    assert result["best_bidsizeshares"].iloc[0] == 1000  # 10 * 100
    assert result["best_asksizeshares"].iloc[0] == 1500  # 15 * 100


def test_clean_quote_table_with_flags(duckdb_con):
    """Test quote cleaning with flag output."""
    data = pd.DataFrame(
        {
            "date": [datetime.date(2023, 1, 15)],
            "time_m": [34200.0],
            "sym_root": ["AAPL"],
            "sym_suffix": pd.Series([None], dtype="string"),
            "bid": [150.0],
            "ask": [150.5],
            "bidsiz": [10],
            "asksiz": [15],
            "qu_cond": ["A"],
            "qu_cancel": [""],
            "natbbo_ind": ["1"],
            "qu_source": ["C"],
            "qu_seqnum": [1],
            "ex": ["N"],
        }
    )
    table = duckdb_con.create_table("quotes_flags", data)

    result = clean_quote_table(table, output_flags=True, keep_qu_cond=["A"]).execute()

    # Check that flag columns are included
    assert "qu_cond" in result.columns
    assert "natbbo_ind" in result.columns
    assert "qu_source" in result.columns
    assert "qu_cancel" in result.columns


def test_clean_quote_table_with_suffix(duckdb_con):
    """Test quote cleaning with symbol suffix."""
    data = pd.DataFrame(
        {
            "date": [datetime.date(2023, 1, 15)],
            "time_m": [34200.0],
            "sym_root": ["BRK"],
            "sym_suffix": ["A"],
            "bid": [450000.0],
            "ask": [450100.0],
            "bidsiz": [1],
            "asksiz": [1],
            "qu_cond": ["A"],
            "qu_cancel": [""],
            "natbbo_ind": ["1"],
            "qu_source": ["C"],
            "qu_seqnum": [1],
            "ex": ["N"],
        }
    )
    table = duckdb_con.create_table("quotes_suffix", data)

    result = clean_quote_table(
        table, keep_qu_cond=["A"], max_spread=Decimal("200.0")
    ).execute()

    assert result["symbol"].iloc[0] == "BRK A"


def test_filter_quote_table_all_filters_disabled(duckdb_con):
    """Test that all filters can be disabled."""
    data = {
        "bid": [10.0, 11.0, 0.0],  # Last one would normally be filtered
        "ask": [10.5, 10.0, 10.5],  # Crossed market
        "bidsiz": [100, 100, 100],
        "asksiz": [100, 100, 100],
        "qu_cond": ["Z", "Z", "Z"],  # Not in default list
        "qu_cancel": ["B", "", ""],  # Canceled
        "natbbo_ind": ["0", "0", "0"],
        "qu_source": ["X", "X", "X"],
    }
    table = duckdb_con.create_table("quotes_no_filter", data)

    result = filter_quote_table(
        table,
        keep_qu_cond=None,
        exclude_canceled_quotes=False,
        exclude_crossed_markets=False,
        exclude_withdrawn_quotes=False,
        exclude_abnormal_spreads=False,
        nbbo_only=False,
    ).execute()

    # Should keep all rows
    assert len(result) == 3


def test_neutralize_withdrawn_quotes_edge_cases(duckdb_con):
    """A zero size withdraws only its own side."""
    data = {
        "bid": [10.0, 10.0, 10.0],
        "ask": [10.5, 10.5, 10.5],
        "bidsiz": [0, 100, 100],  # Zero size
        "asksiz": [100, 0, 100],  # Zero size
    }
    table = duckdb_con.create_table("quotes_edge", data)

    result = neutralize_withdrawn_quotes(table).execute()

    # A zero size withdraws only its own side.
    assert len(result) == 3
    assert pd.isna(result["bid"].iloc[0])
    assert result["ask"].iloc[0] == 10.5
    assert result["bid"].iloc[1] == 10.0
    assert pd.isna(result["ask"].iloc[1])
    assert result["bid"].iloc[2] == 10.0
    assert result["ask"].iloc[2] == 10.5


def test_filter_quote_table_keeps_null_qu_cancel(duckdb_con):
    """A null cancel flag means "not canceled" and must not drop the quote.

    Regression test: `qu_cancel != "B"` alone evaluates to NULL for null
    cancel flags, which silently discarded every such quote.
    """
    data = pd.DataFrame(
        {
            "qu_cond": pd.Series(["R", "R", "R"], dtype="string"),
            "qu_cancel": pd.Series([None, "", "B"], dtype="string"),
            "bid": [10.0, 10.0, 10.0],
            "ask": [10.5, 10.5, 10.5],
            "bidsiz": [100, 100, 100],
            "asksiz": [100, 100, 100],
            "qu_source": pd.Series(["C", "C", "C"], dtype="string"),
            "natbbo_ind": pd.Series(["1", "1", "1"], dtype="string"),
        }
    )
    table = duckdb_con.create_table("quotes_null_cancel", data)

    result = filter_quote_table(table).execute()

    # Every row survives. The null and empty-string rows keep their quotes;
    # only the explicit "B" is neutralised.
    assert len(result) == 3
    canceled = result[result["qu_cancel"] == "B"].iloc[0]
    assert pd.isna(canceled["bid"])
    assert pd.isna(canceled["ask"])
    not_canceled = result[result["qu_cancel"] != "B"]
    assert not_canceled["bid"].notna().all()
    assert not_canceled["ask"].notna().all()


def test_a_withdrawn_quote_does_not_leave_the_venue_stale(duckdb_con):
    """The reason Holden and Jacobsen neutralise instead of deleting.

    A venue quotes, then withdraws. If the withdrawal row is deleted, the
    venue's earlier quote is the most recent thing on file and goes on setting
    the NBBO with a stale price. Keeping the row with a null side records that
    the venue has stepped away.
    """
    data = pd.DataFrame(
        {
            "qu_seqnum": [1, 2],
            "qu_cond": pd.Series(["R", "R"], dtype="string"),
            "qu_cancel": pd.Series([None, None], dtype="string"),
            "qu_source": pd.Series(["C", "C"], dtype="string"),
            "natbbo_ind": pd.Series(["1", "1"], dtype="string"),
            # The venue quotes 10.00/10.50, then withdraws both sides.
            "bid": [10.0, 0.0],
            "bidsiz": [100, 0],
            "ask": [10.5, 0.0],
            "asksiz": [100, 0],
        }
    )
    table = duckdb_con.create_table("withdrawal_sequence", data)

    result = filter_quote_table(table).execute().sort_values("qu_seqnum")

    # Both rows are present, so the withdrawal is visible downstream.
    assert len(result) == 2
    assert result["bid"].iloc[0] == 10.0
    assert pd.isna(result["bid"].iloc[1])
    assert pd.isna(result["ask"].iloc[1])


def test_one_sided_quotes_keep_their_live_side(duckdb_con):
    """Quote Filter 3: a one-sided quote still contributes to its own side."""
    data = pd.DataFrame(
        {
            "qu_cond": pd.Series(["R", "R"], dtype="string"),
            "qu_cancel": pd.Series([None, None], dtype="string"),
            "qu_source": pd.Series(["C", "C"], dtype="string"),
            "natbbo_ind": pd.Series(["1", "1"], dtype="string"),
            "bid": [10.0, 0.0],
            "bidsiz": [100, 0],
            "ask": [0.0, 10.5],
            "asksiz": [0, 100],
        }
    )
    table = duckdb_con.create_table("one_sided", data)

    result = filter_quote_table(table).execute()

    assert len(result) == 2
    # Bid-only quote keeps its bid.
    assert result["bid"].iloc[0] == 10.0
    assert pd.isna(result["ask"].iloc[0])
    # Ask-only quote keeps its ask.
    assert pd.isna(result["bid"].iloc[1])
    assert result["ask"].iloc[1] == 10.5


# ---------------------------------------------------------------------------
# natbbo_ind encodings (#30)
#
# CTA renumbered the National BBO Indicator from digits to letters on
# 30 October 2017 (Daily TAQ Client Specification 3.0b):
#   A = formerly '0'   G = formerly '1'   O = formerly '2'
#   T = formerly '6'   U = formerly '4'
# UTP never changed. Only '1'/'G' and UTP '4' mean "this quote is itself the
# NBBO"; the appendage codes mean the NBBO arrives in the NBBO file instead.
# ---------------------------------------------------------------------------


def _quotes_with_codes(duckdb_con, name, pairs):
    """A quote table with one row per (qu_source, natbbo_ind) pair."""
    n = len(pairs)
    data = pd.DataFrame(
        {
            "qu_source": pd.Series([s for s, _ in pairs], dtype="string"),
            "natbbo_ind": pd.Series([i for _, i in pairs], dtype="string"),
            "qu_cond": pd.Series(["R"] * n, dtype="string"),
            "qu_cancel": pd.Series([None] * n, dtype="string"),
            "bid": [10.0] * n,
            "bidsiz": [100] * n,
            "ask": [10.5] * n,
            "asksiz": [100] * n,
        }
    )
    return duckdb_con.create_table(name, data)


def test_nbbo_only_accepts_the_pre_2017_cta_encoding(duckdb_con):
    table = _quotes_with_codes(
        duckdb_con, "cta_numeric", [("C", "0"), ("C", "1"), ("C", "2"), ("C", "4")]
    )

    result = filter_quote_table(table).execute()

    assert list(result["natbbo_ind"]) == ["1"]


def test_nbbo_only_accepts_the_post_2017_cta_encoding(duckdb_con):
    """Regression test: this returned zero rows, dropping every NYSE-listed
    quote on data from 30 October 2017 onward."""
    table = _quotes_with_codes(
        duckdb_con, "cta_alpha", [("C", "A"), ("C", "G"), ("C", "O"), ("C", "U")]
    )

    result = filter_quote_table(table).execute()

    assert list(result["natbbo_ind"]) == ["G"]


def test_nbbo_only_keeps_utp_code_four(duckdb_con):
    """UTP never renumbered."""
    table = _quotes_with_codes(duckdb_con, "utp", [("N", "0"), ("N", "2"), ("N", "4")])

    result = filter_quote_table(table).execute()

    assert list(result["natbbo_ind"]) == ["4"]


def test_nbbo_only_handles_a_sample_spanning_the_encoding_change(duckdb_con):
    """Both spellings at once, since the codes cannot collide."""
    table = _quotes_with_codes(
        duckdb_con,
        "mixed_eras",
        [("C", "1"), ("C", "G"), ("C", "A"), ("N", "4"), ("N", "0")],
    )

    result = filter_quote_table(table).execute()

    assert sorted(result["natbbo_ind"]) == ["1", "4", "G"]


def test_nbbo_codes_are_overridable(duckdb_con):
    """A user with a different sample period can supply their own codes."""
    table = _quotes_with_codes(duckdb_con, "override", [("C", "G"), ("C", "U")])

    result = filter_quote_table(table, cta_nbbo_codes=("U",)).execute()

    assert list(result["natbbo_ind"]) == ["U"]
