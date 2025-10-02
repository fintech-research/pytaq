import ibis
import pandas as pd
import pytest

from .signs import sign_bjz, sign_clnv, sign_emo, sign_lr, sign_tick


@pytest.fixture
def con():
    """Create an in-memory DuckDB connection for testing."""
    return ibis.connect("duckdb://:memory:")


def test_sign_bjz_nasdaq_buy(con):
    """Test BJZ sign for off-exchange buy trades."""
    # Prices with sub-cent decimals .XX60-.XX99 should be classified as buys
    data = pd.DataFrame(
        {
            "price": [100.1260, 100.7568, 100.0187, 150.4299],
            "ex": ["D", "D", "D", "D"],  # Off-exchange
        }
    )
    table = con.create_table("test", data)

    result = table.mutate(bjz_sign=sign_bjz(table.price, table.ex)).execute()

    # All should be classified as buys (+1) - sub-cent values are 60, 68, 87, 99
    assert result["bjz_sign"].iloc[0] == 1
    assert result["bjz_sign"].iloc[1] == 1
    assert result["bjz_sign"].iloc[2] == 1
    assert result["bjz_sign"].iloc[3] == 1


def test_sign_bjz_nasdaq_sell(con):
    """Test BJZ sign for off-exchange sell trades."""
    # Prices with sub-cent decimals .XX01-.XX39 should be classified as sells
    data = pd.DataFrame(
        {
            "price": [100.1201, 100.7515, 100.0134, 150.4239],
            "ex": ["D", "D", "D", "D"],  # Off-exchange
        }
    )
    table = con.create_table("test", data)

    result = table.mutate(bjz_sign=sign_bjz(table.price, table.ex)).execute()

    # All should be classified as sells (-1) - sub-cent values are 01, 15, 34, 39
    assert result["bjz_sign"].iloc[0] == -1
    assert result["bjz_sign"].iloc[1] == -1
    assert result["bjz_sign"].iloc[2] == -1
    assert result["bjz_sign"].iloc[3] == -1


def test_sign_bjz_nasdaq_unclassified(con):
    """Test BJZ sign for unclassified off-exchange trades."""
    # Prices with sub-cent decimals .XX00, .XX40-.XX59 should be unclassified
    data = pd.DataFrame(
        {
            "price": [100.1200, 100.7540, 100.0150, 150.4259],
            "ex": ["D", "D", "D", "D"],  # Off-exchange
        }
    )
    table = con.create_table("test", data)

    result = table.mutate(bjz_sign=sign_bjz(table.price, table.ex)).execute()

    # All should be unclassified (null) - sub-cent values are 00, 40, 50, 59
    assert pd.isna(result["bjz_sign"].iloc[0])
    assert pd.isna(result["bjz_sign"].iloc[1])
    assert pd.isna(result["bjz_sign"].iloc[2])
    assert pd.isna(result["bjz_sign"].iloc[3])


def test_sign_bjz_non_nasdaq(con):
    """Test BJZ sign for on-exchange trades."""
    # On-exchange trades should always return null
    data = pd.DataFrame(
        {
            "price": [100.1260, 100.7568, 100.1201, 100.7515],
            "ex": ["N", "A", "P", "Q"],  # Various on-exchange venues
        }
    )
    table = con.create_table("test", data)

    result = table.mutate(bjz_sign=sign_bjz(table.price, table.ex)).execute()

    # All should be null for on-exchange trades
    assert pd.isna(result["bjz_sign"].iloc[0])
    assert pd.isna(result["bjz_sign"].iloc[1])
    assert pd.isna(result["bjz_sign"].iloc[2])
    assert pd.isna(result["bjz_sign"].iloc[3])


def test_sign_bjz_mixed_exchanges(con):
    """Test BJZ sign with mixed exchange venues."""
    data = pd.DataFrame(
        {
            "price": [100.1268, 100.1268, 100.1215, 100.1215],
            "ex": ["D", "N", "D", "A"],  # Off-exchange and on-exchange
        }
    )
    table = con.create_table("test", data)

    result = table.mutate(bjz_sign=sign_bjz(table.price, table.ex)).execute()

    # First should be buy (off-exchange + .XX68)
    assert result["bjz_sign"].iloc[0] == 1
    # Second should be null (NYSE)
    assert pd.isna(result["bjz_sign"].iloc[1])
    # Third should be sell (off-exchange + .XX15)
    assert result["bjz_sign"].iloc[2] == -1
    # Fourth should be null (AMEX)
    assert pd.isna(result["bjz_sign"].iloc[3])


def test_sign_bjz_edge_cases(con):
    """Test BJZ sign edge cases at thresholds."""
    data = pd.DataFrame(
        {
            # Testing boundary values (sub-cent decimals)
            "price": [
                100.120001,  # z ~= 0.01 - should be sell
                100.123900,  # z = 39.00 - should be sell
                100.124001,  # z ~= 40.01 - should be unclassified
                100.125900,  # z = 59.00 - should be unclassified
                100.126000,  # z = 60.00 - should be buy
                100.129900,  # z = 99.00 - should be buy
            ],
            "ex": ["D"] * 6,
        }
    )
    table = con.create_table("test", data)

    result = table.mutate(bjz_sign=sign_bjz(table.price, table.ex)).execute()

    assert result["bjz_sign"].iloc[0] == -1  # sell
    assert result["bjz_sign"].iloc[1] == -1  # sell
    assert pd.isna(result["bjz_sign"].iloc[2])  # unclassified
    assert pd.isna(result["bjz_sign"].iloc[3])  # unclassified
    assert result["bjz_sign"].iloc[4] == 1  # buy
    assert result["bjz_sign"].iloc[5] == 1  # buy


# TODO: Add test_sign_tick_basic once window API is fixed
