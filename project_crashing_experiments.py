# ---
# jupyter:
#   jupytext:
#     formats: ipynb,py:percent
#     text_representation:
#       extension: .py
#       format_name: percent
#       format_version: '1.3'
#       jupytext_version: 1.19.3
#   kernelspec:
#     display_name: Python 3
#     language: python
#     name: python3
# ---

# %% [markdown]
# # Project Crashing Experiments
# This notebook allows you to easily configure parameters and run the different project crashing scenarios.
# The scenarios evaluate linear crashing (Base CP-SAT), non-linear crashing using Cobb-Douglas production functions (GA Metaheuristic & MILP), and a Hybrid approach.

# %%
import os
import sys
import pandas as pd
from IPython.display import Image, display

base_dir = os.path.abspath("")
sys.path.append(os.path.join(base_dir, "implementasi-base"))
sys.path.append(os.path.join(base_dir, "implementasi-cobb"))
sys.path.append(os.path.join(base_dir, "implementasi-hybrid"))

from solver_base import (
    read_json, build_predecessors, infer_activity_states_without_state_file,
    SolveConfig, build_model_and_solve, write_json, write_schedule_csv, 
    generate_gantt_comparison_plot, build_reference_no_crash_schedule
)

# %% [markdown]
# ## Skenario 1: Base Model (CP-SAT Linear Crashing)
# This model uses linear crashing costs per task and solves to exact optimality using Google OR-Tools CP-SAT.

# %%
# Configure Parameters for Skenario 1
mode_1 = "cost_with_deadline" # Options: cost_with_deadline, time_with_budget, bonus_penalty
target_end_date_1 = 243
budget_limit_1 = 5000.0
c_late_1 = 1000.0
c_early_1 = 500.0
current_day_1 = 0

# Load Base Data
activity_data = read_json(os.path.join(base_dir, "data/activity_data_v3.json"))
resource_capacity = read_json(os.path.join(base_dir, "data/resource_capacity_v3.json"))
resource_req = read_json(os.path.join(base_dir, "data/resource_requirements_v3.json"))

predecessors, _ = build_predecessors(activity_data, [], True)
states, _ = infer_activity_states_without_state_file(
    activity_data, resource_req, resource_capacity, predecessors, current_day_1, 60.0, 1
)

cfg_1 = SolveConfig(
    target_end_date=target_end_date_1,
    budget_limit=budget_limit_1,
    c_late=c_late_1,
    c_early=c_early_1,
    current_day=current_day_1,
    time_limit=60.0,
    num_workers=1,
    auto_fix_paint_trim_cycle=True,
    remove_edges=[]
)

res_1 = build_model_and_solve(
    activity_data, resource_req, resource_capacity, predecessors, states, cfg_1, mode=mode_1
)

print(f"Status: {res_1['status']}")
if "makespan" in res_1:
    print(f"Makespan: {res_1['makespan']} days")
if "total_crash_cost" in res_1:
    print(f"Total Crash Cost: ${res_1['total_crash_cost']}")

# Display Schedule & Gantt Chart
if "schedule" in res_1:
    df_1 = pd.DataFrame(res_1['schedule'])
    display(df_1.head(10))
    
    baseline_1 = build_reference_no_crash_schedule(
        activity_data, resource_req, resource_capacity, predecessors, current_day_1, 60.0, 1
    )
    out_png_1 = os.path.join(base_dir, "outputs/base_gantt.png")
    os.makedirs(os.path.dirname(out_png_1), exist_ok=True)
    generate_gantt_comparison_plot(baseline_1, res_1["schedule"], current_day_1, out_png_1)
    display(Image(filename=out_png_1))

# %% [markdown]
# ### Skenario 1 Sensitivity Analysis: Varying Target Deadline (T_max)
# We vary the target end date from the normal un-crashed makespan (249 days) down to the maximum crashable limit (193 days).

# %%
import matplotlib.pyplot as plt

scen1_tmax_file = os.path.join(base_dir, "outputs/sensitivity_analysis/scenario_1_tmax.csv")
if os.path.exists(scen1_tmax_file):
    df_s1 = pd.read_csv(scen1_tmax_file)
    
    plt.figure(figsize=(9, 5))
    # Note: T_max corresponds to target_end_date here. Skenario 1 minimizes total_crash_cost to meet T_max.
    # Therefore, total cost increases as T_max decreases.
    plt.plot(df_s1["target_end_date"], df_s1["total_crash_cost"], marker='o', color='tab:red', linewidth=2)
    plt.xlabel('Target Deadline (T_max)')
    plt.ylabel('Total Crash Cost ($)')
    plt.title('Skenario 1: Cost to Crash to Target Deadline')
    plt.grid(True, alpha=0.3)
    
    # We let matplotlib use default numeric axis (ascending from left to right)
    
    out_scen1_png = os.path.join(base_dir, "outputs/sensitivity_analysis/scenario_1_tmax_plot.png")
    plt.savefig(out_scen1_png, dpi=150, bbox_inches="tight")
    plt.show()
    print(f"Saved Skenario 1 sensitivity plot to {out_scen1_png}")

# %% [markdown]
# ## Skenario 2: Cobb-Douglas Production Function (Genetic Algorithm)
# This model uses a non-linear continuous production function for crashing. We solve it using the NSGA-II/GA metaheuristic algorithm.
#
# *Note: For testing purposes in this notebook, `pop_size` and `n_gen` are set small. Increase them for a full run.*

# %%
import numpy as np
from cobb_model import (
    load_data, ResourceBasedScheduling, solve as solve_cobb,
    extract_solution, generate_gantt_comparison_plot as cobb_gantt,
)

# Configure Parameters for Skenario 2 (GA)
mode_2 = "bonus_penalty" # Options: cost_with_deadline, time_with_budget, bonus_penalty
T_MAX_2 = 310
BUDGET_LIMIT_2 = 500000.0
c_late_2 = 5000.0
c_early_2 = 2000.0

pop_size = 20  # INCREASE THIS FOR FULL RUN (e.g. 200)
n_gen = 20     # INCREASE THIS FOR FULL RUN (e.g. 100)

tasks, prec_2, res_2, N_2, K_i_2 = load_data(
    path_tasks=os.path.join(base_dir, "implementasi-cobb/data_tasks.csv"),
    path_precedence=os.path.join(base_dir, "implementasi-cobb/data_precedence.csv"),
    path_assignments=os.path.join(base_dir, "implementasi-cobb/data_assignments.csv"),
)

prob_2 = ResourceBasedScheduling(
    tasks=tasks, precedence=prec_2, resources=res_2, N=N_2, K_i=K_i_2,
    T_max=T_MAX_2, mode=mode_2, budget_limit=BUDGET_LIMIT_2, c_late=c_late_2, c_early=c_early_2,
)

print("Running Genetic Algorithm...")
ga_solution = solve_cobb(prob_2, pop_size=pop_size, seed=42, verbose=False, max_gen=n_gen)

if ga_solution is not None:
    print(f"Makespan: {ga_solution['makespan']:.2f} days")
    
    df_var = pd.DataFrame({
        "Resource": res_2["resource_name"],
        "x (Crowding)": ga_solution["x_ik"],
        "tau (Overtime)": ga_solution["tau_ik"],
        "Original Duration": res_2["D_base_ik"],
        "Crashed Duration": ga_solution["D_ik"],
    })
    display(df_var.head(10))
    
    out_png_2 = os.path.join(base_dir, "outputs/cobb_ga_gantt.png")
    os.makedirs(os.path.dirname(out_png_2), exist_ok=True)
    cobb_gantt(tasks, prob_2.s_baseline, prob_2.f_baseline, ga_solution["s"], ga_solution["f"], current_day_1, out_png_2)
    display(Image(filename=out_png_2))
else:
    print("No feasible solution found.")

# %% [markdown]
# ## Skenario 2: Cobb-Douglas (Multi-Objective Optimization via NSGA-II)
# We can also perform multi-objective optimization using the NSGA-II algorithm to minimize both Makespan and Labor Cost simultaneously, finding the Pareto Front of optimal trade-offs.

# %%
import matplotlib.pyplot as plt

problem_moo = ResourceBasedScheduling(
    tasks=tasks, precedence=prec_2, resources=res_2, N=N_2, K_i=K_i_2,
    alpha=0.7, beta=0.7, x_min=1.0, tau_min=0.0, tau_max=4.0, D_min_ratio=0.5,
    T_max=344, current_day=current_day_1, overtime_mult=1.5, hours_per_day=8,
    mode="multiobjective",
)

print("Running NSGA-II Multi-Objective Optimization...")
res_moo = solve_cobb(problem_moo, pop_size=200, seed=42, verbose=True)

if res_moo is not None and res_moo.F is not None:
    F = res_moo.F
    sorted_indices = np.argsort(F[:, 0])
    F_sorted = F[sorted_indices]
    
    plt.figure(figsize=(8, 6))
    plt.scatter(F_sorted[:, 0], F_sorted[:, 1], color='b', marker='o')
    plt.plot(F_sorted[:, 0], F_sorted[:, 1], color='b', linestyle='-')
    plt.xlabel('Makespan (days)')
    plt.ylabel('Labor Cost ($)')
    plt.title('Time-Cost Pareto Front (Cobb-Douglas NSGA-II)')
    plt.grid(True)
    
    out_pareto = os.path.join(base_dir, "outputs/cobb_pareto_front.png")
    os.makedirs(os.path.dirname(out_pareto), exist_ok=True)
    plt.savefig(out_pareto, dpi=150, bbox_inches="tight")
    plt.show()
    print(f"Saved Pareto front plot to: {out_pareto}")
else:
    print("Multi-objective: No feasible solutions found.")

# %% [markdown]
# ## Skenario 2: Cobb-Douglas (MILP Discretization via CP-SAT)
# Alternatively, we can discretize the Cobb-Douglas variables ($x \in [1.0, 1.5, 2.0]$ and $\tau \in \{0, 1, 2, 3, 4\}$) and solve the problem exactly using CP-SAT.

# %%
from solver_milp import solve_milp_cobb_douglas

mode_milp = "cost_with_deadline"
T_MAX_MILP = 344

print("Running MILP Exact Solver...")
solve_milp_cobb_douglas(
    tasks, prec_2, res_2, N_2, K_i_2,
    mode=mode_milp, T_max=T_MAX_MILP, time_limit=30.0
)

# %% [markdown]
# ## Skenario 3: Hybrid Model (Preprocessing + CP-SAT)
# In this scenario, we estimate the cost of crashing linearly from the non-linear Cobb-Douglas function, then feed the estimated bounds into the standard CP-SAT model.

# %%
import preprocessing

print("Preprocessing Hybrid Data...")
# Ensure preprocessing writes to implementasi-hybrid/data correctly
preprocessing.preprocess()

act_hyb = read_json(os.path.join(base_dir, "implementasi-hybrid/data/activity_data.json"))
cap_hyb = read_json(os.path.join(base_dir, "implementasi-hybrid/data/resource_capacity.json"))
req_hyb = read_json(os.path.join(base_dir, "implementasi-hybrid/data/resource_requirements.json"))

mode_3 = "time_with_budget"
target_end_date_3 = 310
budget_limit_3 = 20000.0

pred_hyb, _ = build_predecessors(act_hyb, [], True)
states_hyb, _ = infer_activity_states_without_state_file(
    act_hyb, req_hyb, cap_hyb, pred_hyb, 0, 60.0, 1
)

cfg_3 = SolveConfig(
    target_end_date=target_end_date_3, budget_limit=budget_limit_3,
    time_limit=30.0, num_workers=1, auto_fix_paint_trim_cycle=True,
    remove_edges=[], current_day=0
)

res_3 = build_model_and_solve(
    act_hyb, req_hyb, cap_hyb, pred_hyb, states_hyb, cfg_3, mode=mode_3
)

print(f"Hybrid Model Status: {res_3['status']}")
if "makespan" in res_3:
    print(f"Makespan: {res_3['makespan']} days")
if "total_crash_cost" in res_3:
    print(f"Estimated Crash Cost: ${res_3['total_crash_cost']}")
    
if "schedule" in res_3:
    display(pd.DataFrame(res_3['schedule']).head(10))
    
    baseline_3 = build_reference_no_crash_schedule(
        act_hyb, req_hyb, cap_hyb, pred_hyb, 0, 60.0, 1
    )
    out_png_3 = os.path.join(base_dir, "outputs/hybrid_gantt.png")
    os.makedirs(os.path.dirname(out_png_3), exist_ok=True)
    generate_gantt_comparison_plot(baseline_3, res_3["schedule"], 0, out_png_3)
    display(Image(filename=out_png_3))

# %% [markdown]
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
