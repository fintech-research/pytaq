import ibis
import pandas as pd
import pytest

from .averages import compute_averages, compute_averages_ave_sw_dw


@pytest.fixture
def con():
    """In-memory DuckDB connection."""
    return ibis.connect("duckdb://:memory:")


def test_compute_averages_ave_sw_dw():
    """Write test for compute average pytest style
    Tests weighted and simple averages computation with Ibis backend."""

    # Create sample data
    sample_data = {
        "symbol": ["A", "A", "A", "B", "B", "B"],
        "dollar": [1.0, 2.0, 2.0, 1.0, 1.0, 3.0],
        "size": [5.0, 2.0, 3.0, 1.0, 1.0, 3.0],
        "price": [1.0, 2.0, 3.0, 7.0, 2.0, 3.0],
    }

    # Create Ibis table
    con = ibis.connect("duckdb://:memory:")
    table = con.create_table("test_data", sample_data)

    measures = ["price"]
    simple = True
    dollar_weighted = True
    share_weighted = True

    result = compute_averages_ave_sw_dw(
        table, measures, simple, dollar_weighted, share_weighted
    )

    # Execute the result
    result_df = result.execute()

    # Expected results
    expected_price_ave = [2.0, 4.0]
    expected_price_dw = [2.2, 3.6]
    expected_price_sw = [1.8, 3.6]

    # Verify results
    assert len(result_df) == 2
    assert result_df["symbol"].iloc[0] == "A"
    assert result_df["symbol"].iloc[1] == "B"

    # Check averages (with some tolerance for floating point)
    assert abs(result_df["price_average"].iloc[0] - expected_price_ave[0]) < 0.01
    assert abs(result_df["price_average"].iloc[1] - expected_price_ave[1]) < 0.01

    # Check dollar-weighted averages
    assert abs(result_df["price_dollar_weighted"].iloc[0] - expected_price_dw[0]) < 0.01
    assert abs(result_df["price_dollar_weighted"].iloc[1] - expected_price_dw[1]) < 0.01

    # Check share-weighted averages
    assert abs(result_df["price_share_weighted"].iloc[0] - expected_price_sw[0]) < 0.01
    assert abs(result_df["price_share_weighted"].iloc[1] - expected_price_sw[1]) < 0.01


def test_weighted_average_ignores_the_weight_of_missing_observations(con):
    """Regression test for the weighted-average null bias.

    Both sums must run over the same rows. Summing the full weight column
    while the numerator skips nulls biases the result toward zero in
    proportion to the weight the missing rows carry. Here the missing
    observation holds 98% of the weight, and the old code returned 0.03
    against a correct 1.5.
    """
    data = pd.DataFrame(
        {
            "symbol": pd.Series(["A"] * 3, dtype="string"),
            "spread": [1.0, None, 2.0],
            "size": [10, 980, 10],
        }
    )
    table = con.create_table("weighted_nulls", data)

    result = compute_averages(
        table, cols=["spread"], group="symbol", weights=[("size", "_share_weighted")]
    ).execute()

    # (1.0*10 + 2.0*10) / (10 + 10)
    assert result["spread_share_weighted"].iloc[0] == pytest.approx(1.5)


def test_weighted_average_unchanged_without_nulls(con):
    """The fix must not move results on complete data."""
    data = pd.DataFrame(
        {
            "symbol": pd.Series(["A"] * 3, dtype="string"),
            "spread": [1.0, 3.0, 2.0],
            "size": [10, 80, 10],
        }
    )
    table = con.create_table("weighted_complete", data)

    result = compute_averages(
        table, cols=["spread"], group="symbol", weights=[("size", "_share_weighted")]
    ).execute()

    assert result["spread_share_weighted"].iloc[0] == pytest.approx(
        (1 * 10 + 3 * 80 + 2 * 10) / 100
    )


def test_weighted_average_of_an_entirely_missing_measure_is_null(con):
    """No observed weight means nothing to average, not zero."""
    data = pd.DataFrame(
        {
            "symbol": pd.Series(["A"] * 2, dtype="string"),
            "spread": pd.Series([None, None], dtype="float64"),
            "size": [10, 10],
        }
    )
    table = con.create_table("weighted_all_null", data)

    result = compute_averages(
        table, cols=["spread"], group="symbol", weights=[("size", "_share_weighted")]
    ).execute()

    assert pd.isna(result["spread_share_weighted"].iloc[0])


def test_a_null_weight_excludes_its_observation(con):
    """An observation with no weight cannot contribute to a weighted average."""
    data = pd.DataFrame(
        {
            "symbol": pd.Series(["A"] * 3, dtype="string"),
            "spread": [1.0, 99.0, 2.0],
            "size": pd.Series([10, None, 10], dtype="Float64"),
        }
    )
    table = con.create_table("weighted_null_weight", data)

    result = compute_averages(
        table, cols=["spread"], group="symbol", weights=[("size", "_share_weighted")]
    ).execute()

    # The 99.0 observation has no weight, so it is excluded entirely.
    assert result["spread_share_weighted"].iloc[0] == pytest.approx(1.5)
