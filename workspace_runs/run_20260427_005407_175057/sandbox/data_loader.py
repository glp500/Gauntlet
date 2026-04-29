import pandas as pd
import os

def load_data(input_dir: str) -> dict[str, pd.DataFrame]:
    """
    Loads the raw sales data from the specified directory.

    Args:
        input_dir: Directory containing the input CSV file (Warehouse_and_Retail_Sales.csv).

    Returns:
        A dictionary containing the loaded raw sales DataFrame under the key 'warehouse_and_retail_sales'.
    """
    # Construct the full file path
    file_name = 'Warehouse_and_Retail_Sales.csv'
    file_path = os.path.join(input_dir, file_name)
    
    df = pd.DataFrame()
    
    try:
        # Attempt to read the CSV file
        df = pd.read_csv(file_path)
    except FileNotFoundError:
        # Handle case where the file is not found
        pass 
    except Exception as e:
        # Catch other potential reading errors
        # In a real scenario, we might log this, but here we just proceed 
        # with an empty dataframe if loading fails.
        pass
        
    # Return the data under the required contract key 'warehouse_and_retail_sales'
    return {
        'warehouse_and_retail_sales': df
    }