import ibis

from .averages import compute_averages_ave_sw_dw


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
    assert abs(result_df["price_Ave"].iloc[0] - expected_price_ave[0]) < 0.01
    assert abs(result_df["price_Ave"].iloc[1] - expected_price_ave[1]) < 0.01

    # Check dollar-weighted averages
    assert abs(result_df["price_DW"].iloc[0] - expected_price_dw[0]) < 0.01
    assert abs(result_df["price_DW"].iloc[1] - expected_price_dw[1]) < 0.01

    # Check share-weighted averages
    assert abs(result_df["price_SW"].iloc[0] - expected_price_sw[0]) < 0.01
    assert abs(result_df["price_SW"].iloc[1] - expected_price_sw[1]) < 0.01
