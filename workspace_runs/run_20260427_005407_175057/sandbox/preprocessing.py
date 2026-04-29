import pandas as pd
from typing import Dict

def preprocess(data: Dict[str, pd.DataFrame]) -> Dict[str, pd.DataFrame]:
    """
    Cleans, aggregates, and engineers the raw sales transaction data.
    The raw transaction data is summarized by Year, Month, Item Type, and Supplier,
    creating a detailed monthly summary suitable for time-series analysis.

    Args:
        data: A dictionary containing raw DataFrames. Expects the key 
              'warehouse_and_retail_sales'.

    Returns:
        A dictionary containing the aggregated DataFrame under the key 'time_series_sales'.
    """
    # Check for the required input data key as per the shared bundle contract
    RAW_DATA_KEY = 'warehouse_and_retail_sales'
    if RAW_DATA_KEY not in data:
        raise ValueError(f"Input data dictionary must contain '{RAW_DATA_KEY}'.")

    df = data[RAW_DATA_KEY].copy()

    # Define dimensions (grouping keys) and metric columns (values to sum)
    aggregation_keys = ['YEAR', 'MONTH', 'ITEM TYPE', 'SUPPLIER']
    metric_columns = ['RETAIL SALES', 'RETAIL TRANSFERS', 'WAREHOUSE SALES']

    # 1. Aggregate the data: Sum all sales metrics by the defined dimensions.
    # This aggregates transactions into unique Year/Month/Item Type/Supplier combinations.
    try:
        aggregated_df = df.groupby(aggregation_keys)[metric_columns].sum().reset_index()
    except KeyError as e:
        raise ValueError(f"One or more required columns are missing for aggregation: {e}")


    # 2. Feature Engineering: Calculate the total sales volume.
    aggregated_df['TOTAL SALES'] = (
        aggregated_df['RETAIL SALES'] + 
        aggregated_df['RETAIL TRANSFERS'] + 
        aggregated_df['WAREHOUSE SALES']
    )

    # 3. Select and refine the final column structure.
    # Define the desired final structure to ensure consistency.
    final_columns_list = [
        'YEAR', 
        'MONTH', 
        'TOTAL SALES', 
        'RETAIL SALES', 
        'RETAIL TRANSFERS', 
        'WAREHOUSE SALES', 
        'ITEM TYPE', 
        'SUPPLIER'
    ]
    
    # Filter the DataFrame to include only the necessary and calculated columns that exist.
    processed_df = aggregated_df[[col for col in final_columns_list if col in aggregated_df.columns]].copy()

    # Return the data under the key specified by the shared bundle contract.
    return {
        'time_series_sales': processed_df
    }