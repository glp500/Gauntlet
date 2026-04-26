import pandas as pd
import os

def load_data(input_dir: str) -> dict[str, pd.DataFrame]:
    """
    Loads sales and warehouse data from the specified input directory.

    Args:
        input_dir: The path to the directory containing the data files.

    Returns:
        A dictionary where the key is 'sales_data' and the value is the 
        Pandas DataFrame loaded from Warehouse_and_Retail_Sales.csv.
    """
    dataframes = {}
    
    # Assuming the primary file is Warehouse_and_Retail_Sales.csv based on the task description
    file_name = "Warehouse_and_Retail_Sales.csv"
    file_path = os.path.join(input_dir, file_name)
    
    if not os.path.exists(file_path):
        # Return empty dictionary if the file is not found
        return dataframes

    try:
        df = pd.read_csv(file_path)
        
        # Store the loaded DataFrame
        dataframes['sales_data'] = df
        
    except Exception:
        # Handle potential errors during file reading
        pass
        
    return dataframes