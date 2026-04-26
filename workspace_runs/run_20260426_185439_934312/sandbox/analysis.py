import pandas as pd

def run_analysis(data: dict) -> dict[str, pd.DataFrame]:
    """
    Analyzes the preprocessed sales and inventory data to derive key performance metrics.

    Args:
        data: A dictionary where keys correspond to the original column names
              and values are pandas DataFrames.

    Returns:
        A dictionary containing the calculated analysis results:
        - sales_trends_by_month: Time-series aggregation of sales and transfers by month.
        - sales_by_item_type: Aggregated sales performance grouped by item type.
    """
    
    # Define the required columns based on the contract assumptions
    required_cols = ['YEAR', 'MONTH', 'RETAIL SALES', 'WAREHOUSE SALES', 'ITEM TYPE']
    
    # Check if all necessary dataframes are present
    if not all(col in data for col in required_cols):
        return {"sales_trends_by_month": pd.DataFrame(), "sales_by_item_type": pd.DataFrame()}

    # --- 1. Calculate Sales Trends by Month (Time-Series) ---
    
    # Select the relevant time-series data
    monthly_trend = data[['YEAR', 'MONTH', 'RETAIL SALES', 'WAREHOUSE SALES']].copy()
    
    # Aggregate Retail Sales and Warehouse Sales by Year and Month
    sales_trends_by_month = monthly_trend.groupby(['YEAR', 'MONTH']).agg({
        'RETAIL SALES': 'sum',
        'WAREHOUSE SALES': 'sum'
    }).reset_index()
    
    # --- 2. Calculate Sales by Item Type ---
    
    # Aggregate Retail Sales by Item Type
    sales_by_item_type = data.groupby('ITEM TYPE').agg({
        'RETAIL SALES': 'sum',
        'RETAIL TRANSFERS': 'sum',
        'WAREHOUSE SALES': 'sum'
    }).reset_index()
    
    # Rename columns for clarity
    sales_by_item_type.rename(columns={
        'RETAIL SALES': 'Total Retail Sales',
        'RETAIL TRANSFERS': 'Total Retail Transfers',
        'WAREHOUSE SALES': 'Total Warehouse Sales'
    }, inplace=True)

    return {
        "sales_trends_by_month": sales_trends_by_month,
        "sales_by_item_type": sales_by_item_type
    }