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
    remove_edges=[]
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

# %%
