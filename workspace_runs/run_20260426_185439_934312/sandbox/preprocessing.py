import pandas as pd
from typing import Dict

def preprocess(data: Dict[str, pd.DataFrame]) -> Dict[str, pd.DataFrame]:
    """
    Preprocesses the raw sales and inventory data by ensuring all required 
    columns are present and structured correctly for analysis.

    Args:
        data: A dictionary where keys correspond to column names (source DF names)
              and values are pandas DataFrames loaded from the input.

    Returns:
        A dictionary containing the processed DataFrames, keyed by the required
        column names: YEAR, MONTH, SUPPLIER, ITEM CODE, ITEM DESCRIPTION, 
        ITEM TYPE, RETAIL SALES, RETAIL TRANSFERS, WAREHOUSE SALES.
    """
    processed_data = {}

    required_columns = [
        'YEAR', 'MONTH', 'SUPPLIER', 'ITEM CODE', 'ITEM DESCRIPTION', 
        'ITEM TYPE', 'RETAIL SALES', 'RETAIL TRANSFERS', 'WAREHOUSE SALES'
    ]

    # Iterate through the input dictionary, where keys are the original column names
    for col_name, df in data.items():
        if not isinstance(df, pd.DataFrame):
            continue
            
        # Ensure the input DataFrame contains all necessary columns before subsetting
        if all(col in df.columns for col in required_columns):
            # Select only the required columns
            df_subset = df[required_columns].copy()
            
            # Store the subset under the corresponding required column name
            for col in required_columns:
                processed_data[col] = df_subset[col]

    return processed_data