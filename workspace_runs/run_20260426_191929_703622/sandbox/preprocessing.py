def preprocess(data: dict) -> dict[str, pd.DataFrame]:
    """
    Preprocesses the input sales data to generate monthly sales summaries and supplier performance metrics.

    Args:
        data: A dictionary containing the loaded pandas DataFrames, expected to include
              'warehouse_and_retail_sales'.

    Returns:
        A dictionary containing the processed DataFrames:
        - 'monthly_sales_summary': Summary of sales aggregated by time, supplier, and item type.
        - 'supplier_item_summary': Performance metrics aggregated by supplier and item type.
    """
    import pandas as pd

    if 'warehouse_and_retail_sales' not in data:
        # Return empty structures if the main data is missing
        return {
            "monthly_sales_summary": pd.DataFrame(),
            "supplier_item_summary": pd.DataFrame()
        }

    df = data['warehouse_and_retail_sales'].copy()

    # 1. Calculate Monthly Sales Summary
    # Aggregate sales, transfers, and warehouse sales by Year, Month, Supplier, and Item Type.
    monthly_summary = df.groupby(
        ['YEAR', 'MONTH', 'SUPPLIER', 'ITEM TYPE']
    ).agg({
        'RETAIL SALES': 'sum',
        'RETAIL TRANSFERS': 'sum',
        'WAREHOUSE SALES': 'sum'
    }).reset_index()

    # 2. Calculate Supplier Item Summary
    # Aggregate total sales, transfers, and warehouse sales by Supplier and Item Type.
    supplier_item_summary = df.groupby(
        ['SUPPLIER', 'ITEM TYPE']
    ).agg({
        'RETAIL SALES': 'sum',
        'RETAIL TRANSFERS': 'sum',
        'WAREHOUSE SALES': 'sum'
    }).reset_index()

    return {
        "monthly_sales_summary": monthly_summary,
        "supplier_item_summary": supplier_item_summary
    }