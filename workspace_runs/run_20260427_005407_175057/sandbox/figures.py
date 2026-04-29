import pandas as pd
import matplotlib.pyplot as plt
from typing import List

def create_figures(data: dict, results: dict, output_dir: str) -> List[str]:
    """
    Generates an informative visualization comparing total sales across different item types
    using the pre-calculated summary results from the analysis step.

    Args:
        data: Dictionary containing preprocessed data (time_series_sales).
        results: Dictionary containing analysis results, expected to include
                 'total_sales_by_item_type'.
        output_dir: Directory path to save the figures.

    Returns:
        A list containing the absolute path(s) of the saved figure(s).
    """
    
    # The required results dataframe containing total sales aggregated by item type.
    KEY_RESULTS = 'total_sales_by_item_type'
    if KEY_RESULTS not in results:
        # Return empty list if the required analysis results are missing.
        return []
    
    # Use the results DataFrame provided by the analysis module
    df_item_sales = results[KEY_RESULTS].copy()
    
    # Identify all columns that represent quantifiable sales metrics.
    # We assume columns containing 'SALES' (case insensitive check included) 
    # and are not the grouping key ('ITEM TYPE') are relevant sales measures.
    sales_cols = [col for col in df_item_sales.columns if 'SALES' in col.upper() and col != 'ITEM TYPE']
    
    if not sales_cols:
        # Cannot plot if no sales columns are found.
        return []

    # Calculate the overall total sales for each Item Type by summing across all identified sales columns.
    # We use groupby and then sum the rows (axis=1) for the total contribution per item type.
    total_sales_by_type = df_item_sales.groupby('ITEM TYPE')[sales_cols].sum().reset_index()
    
    # Create the final single metric column: the overall total sales per item type
    total_sales_by_type['Total Sales'] = total_sales_by_type[sales_cols].sum(axis=1)

    # --- Create the figure (Bar Chart) ---
    plt.figure(figsize=(14, 8))
    
    # Create a bar chart to visually compare the total contribution of each item type
    plt.bar(total_sales_by_type['ITEM TYPE'], total_sales_by_type['Total Sales'], color='darkred')
    
    # Add labels and title for clarity
    plt.title('Total Sales Contribution by Item Type (Overall Performance)', fontsize=18, pad=20)
    plt.xlabel('Item Type', fontsize=14)
    plt.ylabel('Total Sales Volume (Combined Retail & Warehouse Sales)', fontsize=14)
    
    # Rotate x-axis labels for better readability, especially for many item types
    plt.xticks(rotation=45, ha='right', fontsize=12)
    plt.yticks(fontsize=12)
    
    # Add grid for easier reading of sales values
    plt.grid(axis='y', linestyle='--', alpha=0.7)
    
    # Ensure layout fits all elements (labels, title)
    plt.tight_layout()
    
    # Save the figure following the defined output contract
    figure_path = f"{output_dir}/total_sales_by_item_type_comparison.png"
    plt.savefig(figure_path)
    plt.close()
    
    return [figure_path]