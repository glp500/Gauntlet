def run_analysis(data: dict[str, pd.DataFrame]) -> dict[str, pd.DataFrame]:
    """
    Analyzes the preprocessed sales and inventory data to derive key summary statistics.

    Args:
        data: A dictionary containing preprocessed pandas DataFrames
              (expected keys: 'monthly_sales_summary', 'supplier_item_summary').

    Returns:
        A dictionary containing the resulting analysis DataFrames.
    """
    analysis_results = {}

    # --- Analysis on Monthly Sales Trend ---
    if 'monthly_sales_summary' in data:
        monthly_data = data['monthly_sales_summary']

        # Calculate total sales by year and month for temporal trend analysis
        monthly_data['Month_Year'] = pd.to_datetime(
            monthly_data['YEAR'].astype(str) + '-' + monthly_data['MONTH'].astype(str) + '-01'
        )

        # Aggregate total sales per month for trend visualization
        monthly_sales_trend = monthly_data.groupby('Month_Year')['RETAIL SALES'].sum().reset_index()
        monthly_sales_trend = monthly_sales_trend.sort_values(by='Month_Year')
        monthly_sales_trend = monthly_sales_trend.rename(columns={'RETAIL SALES': 'Total Monthly Sales'})

        analysis_results['monthly_sales_trend'] = monthly_sales_trend

    # --- Analysis on Supplier and Item Type Summary ---
    if 'supplier_item_summary' in data:
        supplier_item_data = data['supplier_item_summary']

        # Analyze average sales across different categories
        supplier_summary = supplier_item_data.groupby(['SUPPLIER', 'ITEM TYPE'])['RETAIL SALES'].agg(
            'mean'
        ).reset_index()
        supplier_summary = supplier_summary.rename(columns={'RETAIL SALES': 'Average Retail Sales'})

        analysis_results['supplier_item_summary'] = supplier_summary

    return analysis_results