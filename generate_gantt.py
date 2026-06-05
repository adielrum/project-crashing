import pandas as pd
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
import sys
import os
import argparse

def generate_gantt(csv_path, output_path=None):
    if not os.path.exists(csv_path):
        print(f"Error: File not found: {csv_path}")
        sys.exit(1)
        
    try:
        df = pd.read_csv(csv_path)
    except Exception as e:
        print(f"Error reading CSV: {e}")
        sys.exit(1)
    
    # Ensure required columns are present
    required_cols = ['activity', 'start', 'duration', 'crash_days']
    for col in required_cols:
        if col not in df.columns:
            print(f"Error: Required column '{col}' not found in CSV.")
            sys.exit(1)
            
    # Reverse dataframe so the first task is at the top of the plot
    df = df.iloc[::-1].reset_index(drop=True)
    
    fig, ax = plt.subplots(figsize=(12, max(6, len(df) * 0.4)))
    
    # Legend patches
    crashed_patch = mpatches.Patch(color='red', label='Crashed (crash_days > 0)')
    normal_patch = mpatches.Patch(color='blue', label='Normal (crash_days = 0)')
    
    for i, row in df.iterrows():
        color = 'red' if row['crash_days'] > 0 else 'blue'
        ax.barh(row['activity'], row['duration'], left=row['start'], color=color, edgecolor='black', height=0.6)
        
    ax.set_xlabel('Time (Days)')
    ax.set_ylabel('Activity')
    ax.set_title(f'Gantt Chart - {os.path.basename(csv_path)}')
    
    ax.legend(handles=[normal_patch, crashed_patch], loc='upper right')
    ax.grid(axis='x', linestyle='--', alpha=0.7)
    
    plt.tight_layout()
    
    if output_path is None:
        output_path = os.path.splitext(csv_path)[0] + '_gantt.png'
        
    plt.savefig(output_path, dpi=300, bbox_inches='tight')
    print(f"Successfully generated Gantt chart: {output_path}")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Generate a Gantt chart PNG from a schedule CSV.")
    parser.add_argument("csv_path", help="Path to the input schedule CSV file.")
    parser.add_argument("-o", "--output", help="Path to the output PNG file. Defaults to <input_name>_gantt.png.")
    
    args = parser.parse_args()
    generate_gantt(args.csv_path, args.output)
