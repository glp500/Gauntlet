import pandas as pd

def preprocess(data: dict) -> dict:
    """
    Performs necessary data preprocessing, cleaning, and feature engineering 
    on the input sales and warehouse data.

    Args:
        data: A dictionary containing the raw DataFrame(s) loaded from the input.
              Expected structure includes columns like YEAR, MONTH, 
              SUPPLIER, ITEM TYPE, ITEM CODE, RETAIL SALES, 
              RETAIL TRANSFERS, and WAREHOUSE SALES.

    Returns:
        A dictionary where keys are descriptive names and values are 
        processed Pandas DataFrames ready for analysis.
    """
    if not data:
        return {}

    # Assume the primary DataFrame is the first one loaded.
    if not data:
        return {}
        
    # Select the first DataFrame as the main source for processing
    df = list(data.values())[0]
    
    # Check for essential columns
    required_cols = ['YEAR', 'MONTH', 'SUPPLIER', 'ITEM TYPE', 'ITEM CODE', 
                     'RETAIL SALES', 'RETAIL TRANSFERS', 'WAREHOUSE SALES']
    
    if not all(col in df.columns for col in required_cols):
        # Return original data if critical columns are missing
        return data

    # 1. Type Conversion and Feature Engineering
    # Ensure temporal fields are treated as integers
    df['Year'] = df['YEAR'].astype(int)
    df['Month'] = df['MONTH'].astype(int)
    
    # Feature Engineering: Calculate Net Sales/Transfers
    df['NET_SALES'] = df['RETAIL SALES'] - df['RETAIL TRANSFERS']
    
    # 2. Aggregate Data by Time (Year and Month)
    monthly_summary = df.groupby(['Year', 'Month']).agg({
        'RETAIL SALES': 'sum',
        'RETAIL TRANSFERS': 'sum',
        'WAREHOUSE SALES': 'sum',
        'NET_SALES': 'sum'
    }).reset_index()
    
    # Rename columns for clarity
    monthly_summary.rename(columns={
        'RETAIL SALES': 'Total_Retail_Sales',
        'RETAIL TRANSFERS': 'Total_Retail_Transfers',
        'WAREHOUSE SALES': 'Total_Warehouse_Sales',
        'NET_SALES': 'Total_Net_Sales'
    }, inplace=True)

    # 3. Aggregate Data by Supplier and Item Type (Segmentation)
    supplier_item_summary = df.groupby(['SUPPLIER', 'ITEM TYPE']).agg({
        'RETAIL SALES': 'sum',
        'WAREHOUSE SALES': 'sum',
        'ITEM CODE': 'count'
    }).reset_index()
    
    # Rename columns for clarity
    supplier_item_summary.rename(columns={
        'RETAIL SALES': 'Total_Sales_By_Supplier_Type',
        'WAREHOUSE SALES': 'Total_Warehouse_Sales_By_Supplier_Type',
        'ITEM CODE': 'Item_Count'
    }, inplace=True)

    processed_data = {
        'monthly_summary': monthly_summary,
        'supplier_item_summary': supplier_item_summary
    }

    return processed_data