"""Integration tests against the live WRDS postgres server.

Skipped unless `WRDS_USERNAME` and `WRDS_PASSWORD` are set, so the suite still
runs offline. A `.env` file at the repository root is picked up automatically.

These exist because the rest of the suite runs entirely on DuckDB, and that
hid two real defects: `clean_nbbo` generated SQL postgres rejects (#33), and
no cleaning function could read a WRDS `time` column at all (#29). Neither was
visible without touching the server.

Queries are restricted to one symbol and one day, and assert on counts and
column shape rather than exact values, so they stay cheap and do not depend on
WRDS reissuing identical data.
"""

import datetime
import os

import pytest

from .cleaning.nbbo import clean_nbbo
from .cleaning.official_nbbo import clean_official_complete_nbbo
from .cleaning.quotes import clean_quote_table
from .cleaning.trades import clean_trades
from .tables import (
    get_nbbo_table_name,
    get_official_complete_nbbo_table_name,
    get_quotes_table_name,
    get_trades_table_name,
)

DATE = datetime.date(2020, 1, 2)
SYMBOL = "AAPL"
DATABASE = "taqmsec"


def _credentials():
    try:
        from dotenv import load_dotenv
    except ImportError:
        pass
    else:
        from pathlib import Path

        env = Path(__file__).resolve().parent.parent / ".env"
        if env.exists():
            load_dotenv(env)

    return os.environ.get("WRDS_USERNAME"), os.environ.get("WRDS_PASSWORD")


_USER, _PASSWORD = _credentials()

pytestmark = pytest.mark.skipif(
    not (_USER and _PASSWORD),
    reason="needs WRDS_USERNAME and WRDS_PASSWORD",
)


@pytest.fixture(scope="module")
def con():
    from .wrds import connect

    # Guaranteed by pytestmark; restated so the type checker sees it.
    assert _USER is not None
    assert _PASSWORD is not None
    return connect(_USER, _PASSWORD)


def _raw(con, table_name):
    t = con.table(table_name, database=DATABASE)
    return t.filter(t.sym_root == SYMBOL)


def test_connects(con):
    assert con.name == "postgres"


def test_time_m_is_a_time_column_on_the_server(con):
    """Pins the schema assumption the cleaning code dispatches on.

    If WRDS ever changes this, the dual-shape handling in cleaning.common
    should be revisited rather than silently taking the other branch.
    """
    schema = con.table(get_trades_table_name(DATE), database=DATABASE).schema()

    assert schema["time_m"].is_time()
    assert schema["price"].is_decimal()


def test_clean_trades(con):
    result = clean_trades(_raw(con, get_trades_table_name(DATE)))

    assert result.count().execute() > 0
    assert "timestamp" in result.columns
    assert "dollar" in result.columns


def test_clean_quote_table(con):
    result = clean_quote_table(_raw(con, get_quotes_table_name(DATE)))

    assert result.count().execute() > 0


def test_clean_official_complete_nbbo(con):
    result = clean_official_complete_nbbo(
        _raw(con, get_official_complete_nbbo_table_name(DATE))
    )

    assert result.count().execute() > 0


def test_clean_nbbo(con):
    """Regression test for #33.

    This raised `UndefinedTable: missing FROM-clause entry` on postgres,
    because `filter_changes_only` filtered directly on a window expression.
    DuckDB accepted the same expression, so nothing else caught it.
    """
    result = clean_nbbo(_raw(con, get_nbbo_table_name(DATE)))

    assert result.count().execute() > 0


def test_clean_nbbo_is_reproducible(con):
    """Regression test for the tie-breaking half of #33.

    Roughly 18,000 rows a day share a (symbol, timestamp) pair, so without a
    sequence tiebreaker the row count changed between runs of the same query.
    """
    result = clean_nbbo(_raw(con, get_nbbo_table_name(DATE)))

    assert result.count().execute() == result.count().execute()
