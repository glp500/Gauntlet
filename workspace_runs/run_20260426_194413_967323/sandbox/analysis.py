import pandas as pd

def run_analysis(data: dict[str, pd.DataFrame]) -> dict[str, pd.DataFrame]:
    """
    Analyzes the preprocessed sales and inventory data to derive key trends
    from yearly summaries and monthly pivots.

    Args:
        data: A dictionary containing preprocessed pandas DataFrames,
              expected keys include 'yearly_sales_summary' and 
              'monthly_sales_pivot'.

    Returns:
        A dictionary containing the derived analysis results (yearly trends 
        and monthly summaries).
    """
    analysis_results = {}

    # --- 1. Analyze Yearly Sales Trends from the yearly_sales_summary ---
    if 'yearly_sales_summary' in data:
        yearly_summary = data['yearly_sales_summary'].copy()
        
        # Check for necessary columns to ensure valid calculations
        required_cols = ['YEAR', 'RETAIL SALES', 'RETAIL TRANSFERS', 'WAREHOUSE SALES']
        if all(col in yearly_summary.columns for col in required_cols):
            
            # Calculate total combined sales and warehouse activity per year
            yearly_summary['TOTAL_SALES'] = yearly_summary['RETAIL SALES'] + yearly_summary['WAREHOUSE SALES']
            
            # Group by year to calculate total sums for trend identification
            yearly_trends = yearly_summary.groupby('YEAR').agg(
                Total_Retail_Sales=('RETAIL SALES', 'sum'),
                Total_Transfers=('RETAIL TRANSFERS', 'sum'),
                Total_Warehouse_Sales=('WAREHOUSE SALES', 'sum'),
                Total_Combined_Sales=('TOTAL_SALES', 'sum')
            ).reset_index()
            
            analysis_results['yearly_sales_trends'] = yearly_trends
        else:
            # Handle missing columns gracefully
            analysis_results['yearly_sales_trends'] = pd.DataFrame()

    # --- 2. Analyze Monthly Sales Pivot (for granular monthly comparison) ---
    if 'monthly_sales_pivot' in data:
        monthly_pivot = data['monthly_sales_pivot'].copy()
        
        # Check if necessary columns exist for aggregation
        if 'RETAIL SALES' in monthly_pivot.columns and 'RETAIL TRANSFERS' in monthly_pivot.columns:
            
            # Calculate the average retail sales per transaction/item record for that month
            monthly_pivot['Average_Monthly_Retail_Sales'] = monthly_pivot['RETAIL SALES'].mean(axis=1)
            
            # Aggregate monthly data across all item records to find monthly trends
            monthly_summary = monthly_pivot.groupby('YEAR', as_index=False).agg(
                Avg_Monthly_Retail_Sales=('Average_Monthly_Retail_Sales', 'mean'),
                Total_Transfers_Month=('RETAIL TRANSFERS', 'sum'),
                Total_Retail_Sales_Month=('RETAIL SALES', 'sum')
            )
            analysis_results['monthly_summary'] = monthly_summary
        else:
            # Handle missing columns gracefully
            analysis_results['monthly_summary'] = pd.DataFrame()

    return analysis_results