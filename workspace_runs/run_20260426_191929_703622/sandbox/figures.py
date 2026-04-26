import pandas as pd
import matplotlib.pyplot as plt
import os

def create_figures(data: dict, results: dict, output_dir: str) -> list[str]:
    """
    Generates figures based on the provided data and analysis results.

    Args:
        data: Dictionary containing raw or preprocessed dataframes (e.g., monthly_sales_summary, supplier_item_summary).
        results: Dictionary containing the output tables from run_analysis (not directly used here, but provided for contract).
        output_dir: The directory where figures should be saved.

    Returns:
        A list of file paths for the created figures.
    """
    figure_paths = []
    
    # --- Figure 1: Monthly Sales Trend ---
    
    # Visualize the trend of Retail Sales over time using the monthly summary data
    if 'monthly_sales_summary' in data:
        sales_data = data['monthly_sales_summary']
        
        if not sales_data.empty:
            # Ensure data is sorted for correct trend visualization
            sales_data = sales_data.sort_values(by=['YEAR', 'MONTH'])
            
            plt.figure(figsize=(12, 6))
            
            # Plotting RETAIL SALES trend over time
            if 'RETAIL SALES' in sales_data.columns:
                # Assuming the structure allows direct plotting of time series
                sales_data.plot(x='YEAR', y='RETAIL SALES', kind='line', marker='o', ax=plt.gca())
                
                plt.title('Monthly Retail Sales Trend Over Time')
                plt.xlabel('Year')
                plt.ylabel('Retail Sales ($)')
                plt.grid(True, linestyle='--', alpha=0.6)
                plt.tight_layout()
                
                output_filename = os.path.join(output_dir, 'monthly_sales_trend.png')
                plt.savefig(output_filename)
                plt.close()
                figure_paths.append(output_filename)

    # --- Figure 2: Supplier Performance (Aggregation) ---
    
    # Visualize total warehouse sales aggregated by supplier
    if 'supplier_item_summary' in data:
        supplier_data = data['supplier_item_summary']
        
        if not supplier_data.empty:
            try:
                # Aggregate total warehouse sales by supplier
                # We assume 'WAREHOUSE SALES' exists in this summary data
                supplier_summary = supplier_data.groupby('SUPPLIER')['WAREHOUSE SALES'].sum().sort_values(ascending=False)
                
                if not supplier_summary.empty:
                    plt.figure(figsize=(10, 6))
                    supplier_summary.plot(kind='bar')
                    
                    plt.title('Total Warehouse Sales by Supplier')
                    plt.xlabel('Supplier')
                    plt.ylabel('Total Warehouse Sales ($)')
                    plt.xticks(rotation=45, ha='right')
                    plt.grid(axis='y', linestyle='--', alpha=0.6)
                    plt.tight_layout()
                    
                    output_filename = os.path.join(output_dir, 'supplier_performance_bar.png')
                    plt.savefig(output_filename)
                    plt.close()
                    figure_paths.append(output_filename)
            except KeyError:
                # Handle case where necessary columns are missing in the summary data
                pass
            
    return figure_paths