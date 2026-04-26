import pandas as pd
import matplotlib.pyplot as plt
import os

def create_figures(data: dict, results: dict, output_dir: str) -> list[str]:
    """
    Generates required figures based on input data and analysis results.

    Args:
        data: Dictionary containing preprocessed data (e.g., monthly_sales_summary).
        results: Dictionary containing analysis results.
        output_dir: The directory where figures should be saved.

    Returns:
        A list of paths to the created figure files.
    """
    figure_paths = []

    # 1. Visualize Monthly Sales Trend
    if 'monthly_sales_summary' in data:
        try:
            monthly_data = data['monthly_sales_summary'].sort_values(by=['YEAR', 'MONTH'])

            # Prepare data for plotting (e.g., total sales trend)
            # Assuming 'RETAIL SALES' is the key metric for the trend
            if 'RETAIL SALES' in monthly_data.columns:
                plt.figure(figsize=(12, 6))
                
                # Create a plot showing the trend over time
                monthly_data.plot(x='YEAR-MONTH', y='RETAIL SALES', marker='o', linestyle='-')
                
                plt.title('Monthly Retail Sales Trend Over Time')
                plt.xlabel('Time')
                plt.ylabel('Retail Sales Amount')
                plt.grid(True)
                plt.xticks(rotation=45)
                plt.tight_layout()

                output_filename = os.path.join(output_dir, 'monthly_sales_trend.png')
                plt.savefig(output_filename)
                plt.close()
                figure_paths.append(output_filename)
        except Exception as e:
            # Handle potential errors during plotting or data access
            # In a strict sandbox, logging errors might be limited, but we ensure robustness.
            # print(f"Error during monthly sales trend plotting: {e}")
            pass

    # Add other figures here if necessary based on results structure...

    return figure_paths