import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns
import os

folder = '/Users/macintoshhd/Documents/Adiel/pemod/Pemod-3.0/project-crashing/outputs/temp-pareto'
files = [f for f in os.listdir(folder) if f.endswith('.csv')]

for file in files:
    path = os.path.join(folder, file)
    df = pd.read_csv(path)
    
    # Identify parameter column
    cols = df.columns
    param_col = cols[0]
    obj1_col = cols[1]
    obj2_col = cols[2]
    
    plt.figure(figsize=(10, 6))
    
    # Sort data for better plotting if we are plotting lines, but scatter is better for pareto
    sns.scatterplot(
        data=df,
        x=obj1_col,
        y=obj2_col,
        hue=param_col,
        palette='viridis' if df[param_col].nunique() > 10 else 'tab10',
        alpha=0.7
    )
    
    plt.title(f'Pareto Front for {param_col}')
    plt.xlabel(obj1_col.replace('_', ' ').title())
    plt.ylabel(obj2_col.replace('_', ' ').title())
    plt.grid(True, linestyle='--', alpha=0.5)
    
    output_filename = f'plot_{file.replace(".csv", ".png")}'
    output_path = os.path.join(folder, output_filename)
    plt.savefig(output_path, dpi=300, bbox_inches='tight')
    plt.close()
    
    print(f"Created plot: {output_filename}")
