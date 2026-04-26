import pandas as pd

def run_analysis(data: dict) -> dict[str, pd.DataFrame]:
    """
    Analyzes the preprocessed sales and inventory data to derive key performance metrics.

    Args:
        data: A dictionary containing preprocessed pandas DataFrames. Expected keys are
              'monthly_sales_summary' and 'supplier_item_summary'.

    Returns:
        A dictionary containing the calculated analysis results as DataFrames.
    """
    monthly_summary = data.get('monthly_sales_summary')
    supplier_item_summary = data.get('supplier_item_summary')

    if monthly_summary is None or supplier_item_summary is None:
        # Return empty results if required inputs are missing
        return {
            "monthly_sales_summary": pd.DataFrame(),
            "supplier_performance": pd.DataFrame()
        }

    # --- 1. Monthly Sales Summary Calculation ---
    # Aggregate total sales, transfers, and warehouse sales by month for trend analysis.
    if not monthly_summary.empty:
        monthly_sales_summary_result = monthly_summary.groupby(['YEAR', 'MONTH']).agg(
            Total_Retail_Sales=('RETAIL SALES', 'sum'),
            Total_Transfers=('RETAIL TRANSFERS', 'sum'),
            Total_Warehouse_Sales=('WAREHOUSE SALES', 'sum')
        ).reset_index()
    else:
        monthly_sales_summary_result = pd.DataFrame()


    # --- 2. Supplier/Item Performance Calculation ---
    # Aggregate performance metrics by supplier and item type.
    if not supplier_item_summary.empty:
        supplier_performance_result = supplier_item_summary.groupby(
            ['SUPPLIER', 'ITEM TYPE']
        ).agg(
            Avg_Retail_Sales=('RETAIL SALES', 'mean'),
            Total_Warehouse_Sales=('WAREHOUSE SALES', 'sum'),
            Total_Transfers=('RETAIL TRANSFERS', 'sum')
        ).reset_index()
    else:
        supplier_performance_result = pd.DataFrame()


    return {
        "monthly_sales_summary": monthly_sales_summary_result,
        "supplier_performance": supplier_performance_result
    }