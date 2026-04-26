import pandas as pd

def run_analysis(data: dict) -> dict:
    """
    Analyzes the preprocessed sales and warehouse data to generate key findings
    and calculated metrics.

    Args:
        data: A dictionary containing preprocessed pandas DataFrames.
              Expected keys include 'sales_data'.

    Returns:
        A dictionary containing calculated analysis results as pandas DataFrames.
    """
    analysis_results = {}

    # Ensure 'sales_data' exists before proceeding
    if 'sales_data' not in data:
        return analysis_results

    sales_df = data['sales_data']

    # --- 1. Aggregate Overall Metrics ---
    
    total_retail_sales = sales_df['RETAIL SALES'].sum()
    total_retail_transfers = sales_df['RETAIL TRANSFERS'].sum()
    total_warehouse_sales = sales_df['WAREHOUSE SALES'].sum()
    
    # Store overall summary, although this is often derived in the text summary
    analysis_results['overall_summary'] = {
        "Total Retail Sales": total_retail_sales,
        "Total Retail Transfers": total_retail_transfers,
        "Total Warehouse Sales": total_warehouse_sales
    }

    # --- 2. Segment Analysis by Supplier ---
    
    # Aggregate sales metrics by supplier
    supplier_summary = sales_df.groupby('SUPPLIER').agg(
        Total_Sales=('RETAIL SALES', 'sum'),
        Total_Transfers=('RETAIL TRANSFERS', 'sum'),
        Total_Warehouse_Sales=('WAREHOUSE SALES', 'sum'),
        Transaction_Count=('ITEM CODE', 'count')
    ).reset_index()
    
    # Calculate average metrics for supplier insight
    supplier_summary['Avg_Retail_Sales'] = supplier_summary['Total_Sales'] / supplier_summary['Transaction_Count']
    supplier_summary['Avg_Warehouse_Sales'] = supplier_summary['Total_Warehouse_Sales'] / supplier_summary['Transaction_Count']

    analysis_results['supplier_performance'] = supplier_summary
    
    # --- 3. Segment Analysis by Item Type ---
    
    # Aggregate sales metrics by item type
    item_type_summary = sales_df.groupby('ITEM TYPE').agg(
        Total_Sales=('RETAIL SALES', 'sum'),
        Total_Warehouse_Sales=('WAREHOUSE SALES'),
        Total_Transfers=('RETAIL TRANSFERS', 'sum')
    ).reset_index()
    
    # Calculate average transfer rate: (Total Transfers / Total Retail Sales) for each item type group
    item_type_summary['Avg_Transfer_Rate'] = 0.0
    
    # Only calculate rate where Total_Sales is non-zero
    mask = item_type_summary['Total_Sales'] > 0
    item_type_summary.loc[mask, 'Avg_Transfer_Rate'] = (
        item_type_summary.loc[mask, 'Total_Transfers'] / item_type_summary.loc[mask, 'Total_Sales']
    )

    analysis_results['item_type_performance'] = item_type_summary

    # --- 4. Identify Key Relationships (Correlation Example) ---
    
    if 'RETAIL SALES' in sales_df.columns and 'WAREHOUSE SALES' in sales_df.columns:
        # Calculate correlation between retail sales and warehouse sales across all transactions
        if pd.api.types.is_numeric_dtype(sales_df['RETAIL SALES']) and pd.api.types.is_numeric_dtype(sales_df['WAREHOUSE SALES']):
            correlation = sales_df['RETAIL SALES'].corr(sales_df['WAREHOUSE SALES'])
            analysis_results['sales_warehouse_correlation'] = pd.DataFrame({
                "Correlation (Retail vs Warehouse Sales)": [correlation]
            })
        else:
             analysis_results['sales_warehouse_correlation'] = pd.DataFrame({
                "Correlation (Retail vs Warehouse Sales)": [None]
            })
        
    # Note: Textual summary generation is omitted as the function contract requires returning
    # only the analysis results as DataFrames.

    return analysis_results