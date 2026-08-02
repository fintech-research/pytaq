"""Tests for the public API surface."""

import importlib
import importlib.metadata

import pytest

import pytaq


def test_version_matches_installed_metadata():
    assert pytaq.__version__ == importlib.metadata.version("pytaq")
    assert pytaq.__version__ != "0.0.0+unknown"


@pytest.mark.parametrize("name", pytaq.__all__)
def test_everything_in_all_is_importable(name):
    assert hasattr(pytaq, name), f"pytaq.__all__ advertises {name!r} but it is missing"


@pytest.mark.parametrize(
    "module",
    ["pytaq.cleaning", "pytaq.metrics", "pytaq.utils"],
)
def test_subpackage_all_entries_exist(module):
    mod = importlib.import_module(module)
    for name in mod.__all__:
        assert hasattr(mod, name), f"{module}.__all__ advertises missing {name!r}"


def test_key_entry_points_are_reachable_from_the_top_level():
    """The functions a user actually starts from."""
    for name in [
        "clean_trades",
        "clean_quote_table",
        "clean_nbbo",
        "clean_official_complete_nbbo",
        "merge_trades_official_nbbo",
        "sign_trades",
    ]:
        assert callable(getattr(pytaq, name))


def test_connectors_import_without_their_backends():
    """Importing must never require an optional extra.

    Only connecting does. This is what lets someone on the local-files path
    install pytaq[duckdb] and never see a postgres driver.
    """
    assert callable(pytaq.local.connect)
    assert callable(pytaq.wrds.connect)
