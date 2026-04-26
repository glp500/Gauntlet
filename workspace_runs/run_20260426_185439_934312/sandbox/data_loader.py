import pandas as pd
import os

def load_data(input_dir: str) -> dict[str, pd.DataFrame]:
    """
    Loads the sales and inventory data from the specified directory and returns 
    DataFrames keyed by their respective column names.

    Args:
        input_dir: The path to the directory containing the input CSV file.

    Returns:
        A dictionary where keys are the column names and values are the corresponding 
        pandas Series (treated as DataFrames here).
    """
    file_path = os.path.join(input_dir, "Warehouse_and_Retail_Sales.csv")
    
    if not os.path.exists(file_path):
        raise FileNotFoundError(f"Input file not found at: {file_path}")

    try:
        # Load the entire dataset
        df = pd.read_csv(file_path)
        
        # Select and return the required columns as separate DataFrames/Series
        data = {
            "YEAR": df['YEAR'],
            "MONTH": df['MONTH'],
            "SUPPLIER": df['SUPPLIER'],
            "ITEM CODE": df['ITEM CODE'],
            "ITEM DESCRIPTION": df['ITEM DESCRIPTION'],
            "ITEM TYPE": df['ITEM TYPE'],
            "RETAIL SALES": df['RETAIL SALES'],
            "RETAIL TRANSFERS": df['RETAIL TRANSFERS'],
            "WAREHOUSE SALES": df['WAREHOUSE SALES']
        }
        
        return data
        
    except Exception as e:
        # Handle file reading or parsing errors
        raise IOError(f"Error reading or processing CSV file: {e}")