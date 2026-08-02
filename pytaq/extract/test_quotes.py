import ibis
import pytest

from .quotes import filter_withdrawned_quotes

# Sample data for testing
sample_data = {
    "bid": [1.0, 2.0, None, 4.0, 5.0, 0.0],
    "ask": [2.0, None, 3.5, 6.0, 5.5, 1.0],
    "bidsiz": [100, 200, 300, None, 0, 50],
    "asksiz": [100, None, 0, 400, 500, 50],
}

# Expected result
expected_result = {
    "bid": [1.0],
    "ask": [2.0],
    "bidsiz": [100.0],
    "asksiz": [100.0],
}


@pytest.mark.parametrize(
    "quotes, expected",
    [(sample_data, expected_result)],
)
def test_filter_withdrawned_quotes(quotes, expected):
    # Create Ibis table from sample data
    con = ibis.connect("duckdb://:memory:")
    quotes_table = con.create_table("quotes", quotes)

    # Apply the filter function
    result = filter_withdrawned_quotes(quotes_table)

    # Execute and convert to pandas for comparison
    result_df = result.execute()
    expected_table = con.create_table("expected", expected)
    expected_df = expected_table.execute()

    # Compare the results
    assert len(result_df) == len(expected_df)
    for col in expected_df.columns:
        assert result_df[col].iloc[0] == expected_df[col].iloc[0]
