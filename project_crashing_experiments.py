# ---
# jupyter:
#   jupytext:
#     formats: ipynb,py:percent
#     text_representation:
#       extension: .py
#       format_name: percent
#       format_version: '1.3'
#       jupytext_version: 1.14.5
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
from pymoo.algorithms.soo.nonconvex.ga import GA
from pymoo.operators.crossover.sbx import SBX
from pymoo.operators.mutation.pm import PM
from pymoo.termination import get_termination
from pymoo.optimize import minimize
from cobb_model import load_data, data_path, ResourceBasedScheduling, save_solution_json, generate_gantt_comparison_plot as cobb_gantt

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
    T_max=T_MAX_2, mode=mode_2, budget_limit=BUDGET_LIMIT_2, c_late=c_late_2, c_early=c_early_2
)

algorithm_2 = GA(pop_size=pop_size, crossover=SBX(prob=0.9, eta=15), mutation=PM(eta=20))
termination_2 = get_termination("n_gen", n_gen)

print("Running Genetic Algorithm...")
res_ga = minimize(prob_2, algorithm_2, termination_2, seed=42, verbose=False)

if res_ga.X is not None:
    P = prob_2.P
    x_opt = res_ga.X
    x_ik_opt = x_opt[0:P]
    tau_ik_opt = x_opt[P:2*P]
    D_ik_opt, D_i_opt = prob_2.compute_durations(x_opt)
    s_opt, f_opt = prob_2.forward_pass(D_i_opt)
    
    print(f"Makespan: {np.max(f_opt):.2f} days")
    
    df_var = pd.DataFrame({
        "Resource": res_2["resource_name"],
        "x (Crowding)": x_ik_opt,
        "tau (Overtime)": tau_ik_opt,
        "Original Duration": res_2["D_base_ik"],
        "Crashed Duration": D_ik_opt
    })
    display(df_var.head(10))
    
    out_png_2 = os.path.join(base_dir, "outputs/cobb_ga_gantt.png")
    os.makedirs(os.path.dirname(out_png_2), exist_ok=True)
    cobb_gantt(tasks, prob_2.s_baseline, prob_2.f_baseline, s_opt, f_opt, current_day_1, out_png_2)
    display(Image(filename=out_png_2))
else:
    print("No feasible solution found.")

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
