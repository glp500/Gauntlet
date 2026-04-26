import pandas as pd
import matplotlib.pyplot as plt
import os

def create_figures(data: dict, results: dict, output_dir: str) -> list[str]:
    """
    Generates required figures based on the provided data and analysis results.

    Args:
        data (dict): Dictionary containing preprocessed DataFrame(s) from preprocessing.py.
        results (dict): Dictionary containing analysis results from analysis.py.
        output_dir (str): The directory where figures will be saved.

    Returns:
        list[str]: A list of paths to the generated figure files.
    """
    figure_paths = []

    # --- Figure 1: Sales Trend by Item Type ---
    
    # Check if necessary data exists for plotting
    if 'data' in data and 'ITEM TYPE' in data['data'].columns and 'RETAIL SALES' in data['data'].columns:
        df = data['data'].copy()
        
        # Aggregate retail sales by Item Type and Year for trend visualization
        # We aggregate by Year and Item Type to show overall trend per type.
        
        # Group by Year and Item Type, summing retail sales
        sales_by_type_year = df.groupby(['YEAR', 'ITEM TYPE'])['RETAIL SALES'].sum().reset_index()
        
        if not sales_by_type_year.empty:
            plt.figure(figsize=(14, 7))
            
            # Plotting sales trend for each item type across years
            for item_type in sales_by_type_year['ITEM TYPE'].unique():
                subset = sales_by_type_year[sales_by_type_year['ITEM TYPE'] == item_type]
                plt.plot(subset['YEAR'], subset['RETAIL SALES'], marker='o', linestyle='-', label=item_type)

            plt.title('Retail Sales Trend by Item Type Over Years')
            plt.xlabel('Year')
            plt.ylabel('Total Retail Sales')
            plt.grid(True)
            plt.xticks(sales_by_type_year['YEAR'])
            plt.legend(title='Item Type')
            
            # Define output path
            figure_name = 'sales_trend_by_item_type.png'
            output_path = os.path.join(output_dir, figure_name)
            plt.savefig(output_path)
            plt.close()
            figure_paths.append(output_path)

    return figure_paths