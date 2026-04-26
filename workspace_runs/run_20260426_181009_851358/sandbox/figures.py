import pandas as pd
import matplotlib.pyplot as plt
import os

def create_figures(data: dict[str, pd.DataFrame], results: dict[str, pd.DataFrame], output_dir: str) -> list[str]:
    """
    Generates visualizations based on the provided data and analysis results.

    Args:
        data: Dictionary containing processed DataFrames (e.g., 'sales', 'warehouse').
        results: Dictionary containing analysis results (unused in this specific implementation but kept for interface).
        output_dir: The directory where figures will be saved.

    Returns:
        A list of file paths where the generated figures were saved.
    """
    figure_paths = []
    
    # --- Figure 1: Monthly Retail Sales Trend ---
    # This figure analyzes the time series trend of retail sales from the 'sales' data.
    if 'sales' in data and 'RETAIL SALES' in data['sales'].columns:
        df_sales = data['sales'].copy()
        
        try:
            # Create a combined datetime column for proper time series plotting
            # Combine YEAR and MONTH to create a monthly index
            df_sales['YearMonth'] = pd.to_datetime(df_sales['YEAR'].astype(str) + '-' + df_sales['MONTH'].astype(str) + '-01')
        except Exception:
            # If date conversion fails, skip this figure
            pass
        else:
            # Aggregate total retail sales by month for a time series view
            monthly_sales = df_sales.groupby('YearMonth')['RETAIL SALES'].sum().reset_index()
            
            if not monthly_sales.empty:
                plt.figure(figsize=(12, 6))
                plt.plot(monthly_sales['YearMonth'], monthly_sales['RETAIL SALES'], marker='o', linestyle='-', markersize=3, label='Monthly Retail Sales')
                plt.title('Monthly Retail Sales Trend')
                plt.xlabel('Date')
                plt.ylabel('Total Retail Sales')
                plt.grid(True)
                plt.xticks(rotation=45)
                plt.tight_layout()
                
                filename = os.path.join(output_dir, 'monthly_retail_sales_trend.png')
                plt.savefig(filename)
                plt.close()
                figure_paths.append(filename)

    # --- Figure 2: Annual Warehouse Sales vs. Retail Sales Comparison ---
    # This figure compares the average annual performance of retail vs. warehouse sales.
    if 'sales' in data and 'warehouse' in data and not data['sales'].empty and not data['warehouse'].empty:
        
        # Check required columns exist
        if not all(col in data['sales'].columns for col in ['YEAR', 'RETAIL SALES']) or \
           not all(col in data['warehouse'].columns for col in ['YEAR', 'WAREHOUSE SALES']):
            pass # Skip if required columns are missing
        else:
            df_retail = data['sales'][['YEAR', 'RETAIL SALES']].copy()
            df_warehouse = data['warehouse'][['YEAR', 'WAREHOUSE SALES']].copy()

            # Calculate average retail sales by year
            avg_retail = df_retail.groupby('YEAR')['RETAIL SALES'].mean().reset_index()
            # Calculate average warehouse sales by year
            avg_warehouse = df_warehouse.groupby('YEAR')['WAREHOUSE SALES'].mean().reset_index()
            
            # Merge annual averages for plotting
            annual_comparison = pd.merge(avg_retail, avg_warehouse, on='YEAR', how='inner')
            
            if not annual_comparison.empty:
                plt.figure(figsize=(10, 6))
                
                # Plotting the annual comparison
                plt.plot(annual_comparison['YEAR'], annual_comparison['RETAIL SALES'], label='Average Retail Sales', marker='o', color='blue')
                plt.plot(annual_comparison['YEAR'], annual_comparison['WAREHOUSE SALES'], label='Average Warehouse Sales', marker='x', color='red')
                
                plt.title('Annual Comparison of Average Retail Sales vs. Warehouse Sales')
                plt.xlabel('Year')
                plt.ylabel('Sales Amount')
                plt.legend()
                plt.grid(True)
                plt.xticks(annual_comparison['YEAR'])
                plt.tight_layout()

                filename = os.path.join(output_dir, 'annual_sales_comparison.png')
                plt.savefig(filename)
                plt.close()
                figure_paths.append(filename)

    return figure_paths