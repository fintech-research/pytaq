"""Naming of the daily TAQ tables.

WRDS names each daily TAQ table after its date, e.g. ``ctm_20200102``. Local
copies are expected to keep the same names, so these helpers serve both the
postgres path and the local-files path.
"""

import datetime

DEFAULT_DATABASE = "taqmsec"


def get_trades_table_name(date: datetime.date | datetime.datetime) -> str:
    """Name of the consolidated trades table for a date."""
    return "ctm_" + date.strftime("%Y%m%d")


def get_nbbo_table_name(date: datetime.date | datetime.datetime) -> str:
    """Name of the NBBO table for a date."""
    return "nbbom_" + date.strftime("%Y%m%d")


def get_official_complete_nbbo_table_name(
    date: datetime.date | datetime.datetime,
) -> str:
    """Name of the official complete NBBO table for a date."""
    return "complete_nbbo_" + date.strftime("%Y%m%d")


def get_quotes_table_name(date: datetime.date | datetime.datetime) -> str:
    """Name of the consolidated quotes table for a date."""
    return "cqm_" + date.strftime("%Y%m%d")
