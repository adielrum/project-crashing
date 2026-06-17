import re
import os

with open("project_crashing_experiments.py", "r") as f:
    content = f.read()

# We want to replace everything from "# %% [markdown]\n# ## Skenario 4" onwards.
marker = "# %% [markdown]\n# ## Skenario 4: Sensitivity Analysis"
if marker in content:
    idx = content.find(marker)
    base_content = content[:idx]
else:
    base_content = content

new_section = """# %% [markdown]
# ## Skenario 4: Sensitivity Analysis
# We analyze how sensitive the model is to changes in parameters such as crowding elasticity (`alpha`), overtime efficiency (`beta`), penalty/bonus rates (`c_late`, `c_early`), and target deadline (`T_max`).
# 
# The following code was used to generate the sensitivity datasets (commented out to save time since it is computationally intensive):
# ```python
# # (Extensive generation code located in implementasi-cobb/run_sensitivity.py)
# ```

# %%
import os
import pandas as pd
import matplotlib.pyplot as plt
from mpl_toolkits.mplot3d import Axes3D

out_dir = os.path.join(base_dir, "outputs/sensitivity_analysis")

def plot_oat(file_name, param_col, title):
    path = os.path.join(out_dir, file_name)
    if os.path.exists(path):
        df = pd.read_csv(path)
        fig, ax1 = plt.subplots(figsize=(8, 5))
        
        color = 'tab:red'
        ax1.set_xlabel(param_col)
        ax1.set_ylabel('Total Cost ($)', color=color)
        ax1.plot(df[param_col], df['total_cost'], marker='o', color=color, linewidth=2, label='Total Cost')
        ax1.tick_params(axis='y', labelcolor=color)
        
        ax2 = ax1.twinx()
        color = 'tab:blue'
        ax2.set_ylabel('Makespan (days)', color=color)
        ax2.plot(df[param_col], df['makespan'], marker='s', color=color, linestyle='--', linewidth=2, label='Makespan')
        ax2.tick_params(axis='y', labelcolor=color)
        
        fig.tight_layout()
        plt.title(title)
        
        lines_1, labels_1 = ax1.get_legend_handles_labels()
        lines_2, labels_2 = ax2.get_legend_handles_labels()
        ax1.legend(lines_1 + lines_2, labels_1 + labels_2, loc='upper center')
        
        plt.grid(True, alpha=0.3)
        out_png = path.replace('.csv', '.png')
        plt.savefig(out_png, dpi=150, bbox_inches="tight")
        plt.show()
        print(f"Saved plot to {out_png}")
    else:
        print(f"Data file not found: {path}")

# Plot OATs
plot_oat("oat_alpha.csv", "alpha", "Sensitivity: Crowding Elasticity (alpha)")
plot_oat("oat_beta.csv", "beta", "Sensitivity: Overtime Efficiency (beta)")
plot_oat("oat_c_late.csv", "c_late", "Sensitivity: Penalty Rate (c_late)")
plot_oat("oat_c_early.csv", "c_early", "Sensitivity: Bonus Rate (c_early)")
plot_oat("oat_T_max.csv", "T_max", "Sensitivity: Target Deadline (T_max)")

# %%
# 3D Plots for Grids
def plot_3d_grid(file_name, x_col, y_col, z_col, title, z_label):
    path = os.path.join(out_dir, file_name)
    if os.path.exists(path):
        df = pd.read_csv(path)
        fig = plt.figure(figsize=(10, 7))
        ax = fig.add_subplot(111, projection='3d')
        
        ax.plot_trisurf(df[x_col], df[y_col], df[z_col], cmap='viridis', edgecolor='none')
        ax.set_xlabel(x_col)
        ax.set_ylabel(y_col)
        ax.set_zlabel(z_label)
        plt.title(title)
        
        out_png = path.replace('.csv', f'_{z_col}_3d.png')
        plt.savefig(out_png, dpi=150, bbox_inches="tight")
        plt.show()
        print(f"Saved 3D plot to {out_png}")
    else:
        print(f"Data file not found: {path}")

plot_3d_grid("grid_alpha_beta.csv", "alpha", "beta", "total_cost", "Total Cost vs Alpha & Beta", "Total Cost ($)")
plot_3d_grid("grid_alpha_beta.csv", "alpha", "beta", "makespan", "Makespan vs Alpha & Beta", "Makespan (days)")
plot_3d_grid("grid_clate_cearly.csv", "c_late", "c_early", "total_cost", "Total Cost vs Penalty & Bonus", "Total Cost ($)")
plot_3d_grid("grid_clate_cearly.csv", "c_late", "c_early", "makespan", "Makespan vs Penalty & Bonus", "Makespan (days)")

# %%
# Pareto Shifts
def plot_pareto_shift(file_name, param_col, title):
    path = os.path.join(out_dir, file_name)
    if os.path.exists(path):
        df = pd.read_csv(path)
        plt.figure(figsize=(10, 6))
        colors = ['r', 'g', 'b', 'c', 'm']
        vals = df[param_col].unique()
        
        for i, v in enumerate(vals):
            subset = df[df[param_col] == v].sort_values(by='makespan')
            # For c_late/c_early we use total_cost, for alpha/beta we use labor_cost
            y_col = 'total_cost' if 'cost' in df.columns or 'total_cost' in df.columns else 'labor_cost'
            if y_col not in df.columns: y_col = 'labor_cost'
            
            plt.plot(subset['makespan'], subset[y_col], marker='o', 
                     color=colors[i % len(colors)], label=f'{param_col} = {v}')
            
        plt.xlabel('Makespan (days)')
        plt.ylabel(f'{y_col.replace("_", " ").title()} ($)')
        plt.title(title)
        plt.legend()
        plt.grid(True)
        out_png = path.replace('.csv', '.png')
        plt.savefig(out_png, dpi=150, bbox_inches="tight")
        plt.show()
        print(f"Saved plot to {out_png}")
    else:
        print(f"Data file not found: {path}")

plot_pareto_shift("pareto_alpha.csv", "alpha", "Pareto Shift: Crowding Elasticity (alpha)")
plot_pareto_shift("pareto_beta.csv", "beta", "Pareto Shift: Overtime Efficiency (beta)")
plot_pareto_shift("pareto_c_late.csv", "c_late", "Pareto Shift: Penalty Rate (c_late) on Total Cost")
plot_pareto_shift("pareto_c_early.csv", "c_early", "Pareto Shift: Bonus Rate (c_early) on Total Cost")
"""

with open("project_crashing_experiments.py", "w") as f:
    f.write(base_content + new_section)
