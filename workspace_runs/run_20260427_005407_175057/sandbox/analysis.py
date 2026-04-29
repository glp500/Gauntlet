import pandas as pd

def run_analysis(data: dict) -> dict:
    """
    Analyzes sales performance from the preprocessed time-series data 
    to determine total sales contributions by item type and year. 
    This data supports the generation of the summary and the comparative visualization.

    Args:
        data: A dictionary containing preprocessed DataFrame(s). 
              Expected key: 'time_series_sales'.

    Returns:
        A dictionary containing result DataFrames, specifically 
        'total_sales_by_item_type', summarizing total sales across 
        all items by year and item type.
    """
    # Retrieve the preprocessed DataFrame, expected under 'time_series_sales'.
    df_summary = data.get('time_series_sales')

    if df_summary is None:
        # Return empty dictionary if the expected key is missing
        return {}

    # 1. Calculate Total Sales for each transaction record.
    # Total sales = RETAIL SALES + WAREHOUSE SALES + RETAIL TRANSFERS
    # Ensure that the calculation uses the correct column names from the source data.
    df_summary['TOTAL_SALES'] = (
        df_summary['RETAIL SALES'].fillna(0) + 
        df_summary['WAREHOUSE SALES'].fillna(0) + 
        df_summary['RETAIL TRANSFERS'].fillna(0)
    )

    # 2. Aggregate total sales. We group by Year and Item Type to identify 
    # major contributors over time, which is key for both the text summary 
    # (identifying trends/top segments) and the visualization focus (Item Type comparison).
    sales_aggregation = df_summary.groupby(['YEAR', 'ITEM TYPE'])['TOTAL_SALES'].sum().reset_index()
    
    # Rename the aggregated column to reflect total sales contribution.
    sales_aggregation.rename(columns={'TOTAL_SALES': 'TOTAL_ITEM_SALES'}, inplace=True)

    # The required output DataFrame for downstream analysis and visualization.
    results = {
        'total_sales_by_item_type': sales_aggregation
    }
    
    return results