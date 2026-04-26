import pandas as pd
import os

def load_data(input_dir: str) -> dict[str, pd.DataFrame]:
    """
    Loads the sales and inventory data from the specified CSV file.

    Args:
        input_dir: The directory where the input CSV file is located.

    Returns:
        A dictionary containing the loaded DataFrame.
        The primary key is 'warehouse_and_retail_sales'.
    """
    file_path = os.path.join(input_dir, "Warehouse_and_Retail_Sales.csv")

    if not os.path.exists(file_path):
        raise FileNotFoundError(f"Input file not found at: {file_path}")

    try:
        # Load the data
        df = pd.read_csv(file_path)
    except Exception as e:
        # Handle potential reading errors
        raise IOError(f"Error reading CSV file: {e}")

    # Per the bundle contract, the main loaded data is keyed as 'warehouse_and_retail_sales'.
    data_dict = {
        "warehouse_and_retail_sales": df
    }

    return data_dict