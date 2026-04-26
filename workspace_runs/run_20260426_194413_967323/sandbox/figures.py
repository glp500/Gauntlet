import pandas as pd
import matplotlib.pyplot as plt
import os

def create_figures(data: dict, results: dict, output_dir: str) -> list[str]:
    """
    Generates visualizations based on the provided data and analysis results,
    focusing on yearly trends of sales, transfers, and warehouse activity.

    Args:
        data: Dictionary containing preprocessed data (unused directly for this specific figure, but part of the contract).
        results: Dictionary containing analysis results, expected to contain 'yearly_sales_trends'.
        output_dir: The directory where figures will be saved.

    Returns:
        A list of file paths where the generated figures were saved.
    """
    figure_paths = []
    
    # Ensure the output directory exists
    if not os.path.exists(output_dir):
        os.makedirs(output_dir)

    # Check if the expected yearly trend results exist
    if 'yearly_sales_trends' in results:
        df_trends = results['yearly_sales_trends']
        
        # Define required columns based on the expected analysis output
        required_cols = ['YEAR', 'RETAIL SALES', 'RETAIL TRANSFERS', 'WAREHOUSE SALES']
        
        # Check if the DataFrame contains the necessary columns
        if all(col in df_trends.columns for col in required_cols):
            
            # Prepare data for plotting
            years = df_trends['YEAR']
            sales = df_trends['RETAIL SALES']
            transfers = df_trends['RETAIL TRANSFERS']
            warehouse_sales = df_trends['WAREHOUSE SALES']

            # Create the figure with 3 subplots stacked vertically
            fig, axes = plt.subplots(3, 1, figsize=(10, 12), sharex=True)
            fig.suptitle('Yearly Sales, Transfers, and Warehouse Activity Trends', fontsize=16)

            # Plot 1: Retail Sales Trend
            axes[0].plot(years, sales, marker='o', linestyle='-', color='blue')
            axes[0].set_title('Retail Sales Trend')
            axes[0].set_ylabel('Sales Amount')
            axes[0].grid(True, linestyle='--', alpha=0.6)

            # Plot 2: Retail Transfers Trend
            axes[1].plot(years, transfers, marker='o', linestyle='-', color='green')
            axes[1].set_title('Retail Transfers Trend')
            axes[1].set_ylabel('Transfers Amount')
            axes[1].grid(True, linestyle='--', alpha=0.6)

            # Plot 3: Warehouse Sales Trend
            axes[2].plot(years, warehouse_sales, marker='o', linestyle='-', color='red')
            axes[2].set_title('Warehouse Sales Trend')
            axes[2].set_ylabel('Warehouse Sales Amount')
            axes[2].grid(True, linestyle='--', alpha=0.6)
            
            # Adjust layout for suptitle and ensure better spacing
            plt.tight_layout(rect=[0, 0.03, 1, 0.95]) 
            
            # Save the figure
            filename = os.path.join(output_dir, 'yearly_sales_trend.png')
            plt.savefig(filename)
            plt.close(fig)
            figure_paths.append(filename)
        
    return figure_paths