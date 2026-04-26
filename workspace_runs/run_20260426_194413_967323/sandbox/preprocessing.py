import pandas as pd

def preprocess(data: dict) -> dict[str, pd.DataFrame]:
    """
    Analyzes the input sales data and generates summarized views for
    yearly trends and monthly pivots.

    Args:
        data: A dictionary containing the loaded DataFrame, expected to have
              the key 'warehouse_and_retail_sales'.

    Returns:
        A dictionary containing two processed DataFrames:
        - 'yearly_sales_summary': Summary statistics grouped by year.
        - 'monthly_sales_pivot': Monthly breakdown of sales metrics pivoted by item code.
    """
    if 'warehouse_and_retail_sales' not in data:
        # Return empty results if the expected data is missing
        return {
            'yearly_sales_summary': pd.DataFrame(),
            'monthly_sales_pivot': pd.DataFrame()
        }

    df = data['warehouse_and_retail_sales'].copy()

    # 1. Create yearly_sales_summary
    # Calculate aggregate metrics grouped by year
    yearly_summary = df.groupby('YEAR').agg(
        total_retail_sales=('RETAIL SALES', 'sum'),
        total_retail_transfers=('RETAIL TRANSFERS', 'sum'),
        total_warehouse_sales=('WAREHOUSE SALES', 'sum'),
        avg_retail_sales=('RETAIL SALES', 'mean')
    ).reset_index()

    # 2. Create monthly_sales_pivot
    # Pivot the data to see monthly trends across item codes and sales metrics
    monthly_pivot = df.pivot_table(
        index=['YEAR', 'MONTH'],
        columns='ITEM CODE',
        values=['RETAIL SALES', 'WAREHOUSE SALES', 'RETAIL TRANSFERS'],
        aggfunc='sum'
    ).reset_index()

    return {
        'yearly_sales_summary': yearly_summary,
        'monthly_sales_pivot': monthly_pivot
    }