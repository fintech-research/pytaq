import datetime

import pandas as pd
import pytest

from . import local
from .cleaning.merge_trades_official_nbbo import merge_trades_official_nbbo
from .cleaning.official_nbbo import clean_official_complete_nbbo
from .cleaning.trades import clean_trades

DATE = datetime.date(2020, 1, 2)


def _trades_frame():
    n = 4
    return pd.DataFrame(
        {
            "DATE": [DATE] * n,
            "TIME_M": [34200.5, 34260.0, 34320.25, 34380.0],
            "SYM_ROOT": pd.Series(["A"] * n, dtype="string"),
            "SYM_SUFFIX": pd.Series([None] * n, dtype="string"),
            "EX": pd.Series(["N", "D", "N", "D"], dtype="string"),
            "SIZE": [100, 200, 300, 400],
            "PRICE": [10.0, 10.5, 10.5, 10.2],
            "TR_SEQNUM": [1, 2, 3, 4],
            "TR_SCOND": pd.Series(["@"] * n, dtype="string"),
            "TR_CORR": pd.Series(["00"] * n, dtype="string"),
        }
    )


def _official_nbbo_frame():
    n = 3
    return pd.DataFrame(
        {
            "DATE": [DATE] * n,
            "TIME_M": [34200.0, 34300.0, 34400.0],
            "SYM_ROOT": pd.Series(["A"] * n, dtype="string"),
            "SYM_SUFFIX": pd.Series([None] * n, dtype="string"),
            "BEST_BID": [9.9, 10.1, 10.0],
            "BEST_BIDSIZESHARES": [100, 200, 300],
            "BEST_ASK": [10.6, 10.8, 10.7],
            "BEST_ASKSIZESHARES": [100, 200, 300],
        }
    )


@pytest.fixture
def data_dir(tmp_path):
    """A directory laid out the way pytaq.local expects."""
    _trades_frame().to_parquet(tmp_path / "ctm_20200102.parquet")
    _official_nbbo_frame().to_parquet(tmp_path / "complete_nbbo_20200102.parquet")
    return tmp_path


@pytest.fixture
def con():
    return local.connect()


def test_get_trades_reads_parquet(con, data_dir):
    result = local.get_trades(con, data_dir, DATE).execute()

    assert len(result) == 4
    assert "PRICE" in result.columns


def test_symbol_filter(con, data_dir):
    assert len(local.get_trades(con, data_dir, DATE, symbols=["A"]).execute()) == 4
    assert len(local.get_trades(con, data_dir, DATE, symbols=["ZZZZ"]).execute()) == 0


def test_missing_file_names_what_it_looked_for(con, data_dir):
    with pytest.raises(FileNotFoundError, match="cqm_20200102"):
        local.get_quotes(con, data_dir, DATE)


def test_reads_csv_as_well_as_parquet(con, tmp_path):
    _trades_frame().to_csv(tmp_path / "ctm_20200102.csv", index=False)

    result = local.get_trades(con, tmp_path, DATE).execute()

    assert len(result) == 4


def test_lowercase_columns_are_accepted(con, tmp_path):
    frame = _trades_frame()
    frame.columns = [c.lower() for c in frame.columns]
    frame.to_parquet(tmp_path / "ctm_20200102.parquet")

    result = local.get_trades(con, tmp_path, DATE, symbols=["A"]).execute()

    assert len(result) == 4


def test_end_to_end_from_local_files(con, data_dir):
    """The whole path 3 workflow: local files in, matched trades out.

    This is the test that would have caught the asof_join and null-handling
    bugs, since it exercises the stages together rather than one at a time.
    """
    raw_trades = local.get_trades(con, data_dir, DATE)
    raw_nbbo = local.get_official_complete_nbbo(con, data_dir, DATE)

    trades = clean_trades(raw_trades)
    nbbo = clean_official_complete_nbbo(raw_nbbo)
    merged = (
        merge_trades_official_nbbo(trades, nbbo)
        .execute()
        .sort_values("timestamp")
        .reset_index(drop=True)
    )

    assert len(merged) == 4

    # dollar volume is computed during cleaning
    assert merged["dollar"].tolist() == pytest.approx([1000.0, 2100.0, 3150.0, 4080.0])

    # Every trade here follows the 09:30:00 quote, so all should be matched.
    assert merged["best_bid"].notna().all()
    assert merged["best_ask"].notna().all()

    # The 09:31:00 trade (34260s) precedes the second quote (34300s), so it
    # still carries the opening quote.
    assert merged["best_bid"].tolist()[:2] == [9.9, 9.9]
    # The later trades pick up the quotes that superseded it.
    assert merged["best_bid"].tolist()[2:] == [10.1, 10.1]
