import pandas as pd
import os

def load_data(input_dir: str) -> dict[str, pd.DataFrame]:
    """
    Loads the warehouse and retail sales data from a specified directory.

    Args:
        input_dir: The path to the directory containing the input CSV file.

    Returns:
        A dictionary containing the loaded data, keyed by DataFrame names.
    """
    file_path = os.path.join(input_dir, "Warehouse_and_Retail_Sales.csv")
    
    if not os.path.exists(file_path):
        # Handle error case if the file is not found, although in a sandbox context, 
        # we assume the input is provided correctly.
        raise FileNotFoundError(f"Input file not found at: {file_path}")

    try:
        df = pd.read_csv(file_path)
    except Exception as e:
        raise IOError(f"Error reading CSV file: {e}")

    # Return the data structured according to the bundle contract
    return {
        "warehouse_and_retail_sales": df
    }