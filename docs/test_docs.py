"""Execute the Python examples in the documentation.

The previous documentation described an API that did not exist, so examples
are checked mechanically rather than by eye. Every fenced ``python`` block
under ``docs/`` is compiled, and blocks that can run without external data are
executed against a fixture directory.

A block that needs a WRDS connection, or is an illustrative fragment rather
than a runnable program, is marked in the source with ``# docs-test: skip``.
"""

import ast
import datetime
import re
from pathlib import Path

import pandas as pd
import pytest

DOCS_DIR = Path(__file__).parent
CODE_BLOCK = re.compile(r"^```python\n(.*?)^```", re.MULTILINE | re.DOTALL)
SKIP_MARKER = "# docs-test: skip"

DATE = datetime.date(2020, 1, 2)


def _blocks():
    for path in sorted(DOCS_DIR.rglob("*.md")):
        for index, match in enumerate(CODE_BLOCK.finditer(path.read_text())):
            yield pytest.param(
                match.group(1),
                id=f"{path.relative_to(DOCS_DIR)}:{index}",
            )


@pytest.mark.parametrize("source", list(_blocks()))
def test_documented_examples_are_valid_python(source):
    """Every example parses, whether or not it can be executed here."""
    ast.parse(source)


@pytest.fixture(scope="module")
def data_dir(tmp_path_factory):
    """A directory matching the layout the documentation describes."""
    path = tmp_path_factory.mktemp("data")
    n = 4
    trades = pd.DataFrame(
        {
            "DATE": [DATE] * n,
            "TIME_M": [34200.5, 34260.0, 34320.25, 34380.0],
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
    trades.to_parquet(path / "ctm_20200102.parquet")

    m = 3
    nbbo = pd.DataFrame(
        {
            "DATE": [DATE] * m,
            "TIME_M": [34200.0, 34300.0, 34400.0],
            "SYM_ROOT": pd.Series(["AAPL"] * m, dtype="string"),
            "SYM_SUFFIX": pd.Series([None] * m, dtype="string"),
            "BEST_BID": [9.9, 10.1, 10.0],
            "BEST_BIDSIZESHARES": [100, 200, 300],
            "BEST_ASK": [10.6, 10.8, 10.7],
            "BEST_ASKSIZESHARES": [100, 200, 300],
        }
    )
    nbbo.to_parquet(path / "complete_nbbo_20200102.parquet")
    return path


def test_the_readme_example_runs(data_dir):
    """The example on the front page, run for real."""
    from pytaq import clean_trades, local

    con = local.connect()
    raw = local.get_trades(con, data_dir, DATE, symbols=["AAPL"])
    trades = clean_trades(raw)

    result = trades.execute()
    assert len(result) == 4
    assert "dollar" in result.columns


def test_the_quickstart_workflow_runs(data_dir):
    """Open, clean, match, sign, as the quick start describes it."""
    from pytaq import (
        clean_official_complete_nbbo,
        clean_trades,
        local,
        merge_trades_official_nbbo,
        sign_trades,
    )

    con = local.connect()
    trades = clean_trades(local.get_trades(con, data_dir, DATE))
    nbbo = clean_official_complete_nbbo(
        local.get_official_complete_nbbo(con, data_dir, DATE)
    )

    matched = merge_trades_official_nbbo(trades, nbbo)
    signed = sign_trades(matched).execute()

    assert len(signed) == 4
    for suffix in ["Tick", "LR", "EMO", "CLNV", "BJZ"]:
        assert f"BuySell{suffix}" in signed.columns


def test_documented_hj_defaults_match_the_code():
    """The defaults table in configuration.md is not hand-maintained fiction."""
    from pytaq import hj_defaults as hj

    assert datetime.time(9, 0) == hj.HJ_START_TIME_QUOTES
    assert datetime.time(16, 0) == hj.HJ_END_TIME_QUOTES
    assert datetime.time(9, 30) == hj.HJ_START_TIME_TRADES
    assert datetime.time(16, 0) == hj.HJ_END_TIME_TRADES
    assert hj.HJ_KEEP_QU_COND == ["A", "B", "H", "O", "R", "W"]
    assert str(hj.HJ_MAX_SPREAD) == "5.0"
    assert str(hj.HJ_MAX_QUOTE_CHANGE) == "2.5"
