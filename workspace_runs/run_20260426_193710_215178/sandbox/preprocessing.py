def preprocess(data: dict) -> dict[str, pd.DataFrame]:
    """
    Preprocesses the input sales and inventory data to generate summarized views
    for monthly sales trends and supplier/item summaries.

    Args:
        data: A dictionary containing the raw DataFrame, keyed typically by
              'warehouse_and_retail_sales'.

    Returns:
        A dictionary containing two processed DataFrames:
        - 'monthly_sales_summary': Aggregated sales data by month and year.
        - 'supplier_item_summary': Aggregated data based on supplier and item type.
    """
    if 'warehouse_and_retail_sales' not in data:
        raise ValueError("Input data dictionary must contain the key 'warehouse_and_retail_sales'.")

    df = data['warehouse_and_retail_sales'].copy()

    # 1. Create monthly_sales_summary
    # Aggregate sales metrics by year and month.
    monthly_summary = df.groupby(['YEAR', 'MONTH']).agg(
        Total_Retail_Sales=('RETAIL SALES', 'sum'),
        Total_Transfers=('RETAIL TRANSFERS', 'sum'),
        Total_Warehouse_Sales=('WAREHOUSE SALES', 'sum')
    ).reset_index()

    # 2. Create supplier_item_summary
    # Aggregate sales metrics by supplier and item type.
    supplier_item_summary = df.groupby(['SUPPLIER', 'ITEM TYPE']).agg(
        Average_Retail_Sales=('RETAIL SALES', 'mean'),
        Total_Warehouse_Sales=('WAREHOUSE SALES', 'sum'),
        Item_Count=('ITEM CODE', 'count')
    ).reset_index()

    return {
        'monthly_sales_summary': monthly_summary,
        'supplier_item_summary': supplier_item_summary
    }