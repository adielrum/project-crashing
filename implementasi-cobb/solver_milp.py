import os
import json
import argparse
import numpy as np
import pandas as pd
from ortools.sat.python import cp_model
from cobb_model import load_data, data_path, save_solution_json

def solve_milp_cobb_douglas(
    tasks, precedence, resources, N, K_i, 
    alpha=0.7, beta=0.7, x_min=1.0, x_max=2.0, tau_min=0.0, tau_max=4.0, D_min_ratio=0.5,
    T_max=344, current_day=0, overtime_mult=1.5, hours_per_day=8, mode="cost_with_deadline",
    budget_limit=None, c_late=5000.0, c_early=2000.0, time_limit=60.0
):
    model = cp_model.CpModel()
    
    # Pre-calculate discrete options
    # x options: 1.0, 1.5, 2.0
    # tau options: 0, 1, 2, 3, 4
    x_options = np.arange(x_min, x_max + 0.1, 0.5)
    tau_options = np.arange(tau_min, tau_max + 0.1, 1.0)
    
    options = []
    for x in x_options:
        for tau in tau_options:
            options.append({"x": x, "tau": tau})
            
    P = len(resources)
    r_k = resources["r_k_usd"].values
    r_k_ot = r_k * overtime_mult
    U_ik = resources["U_ik"].values
    D_base_ik = resources["D_base_ik"].values
    D_min_ik = D_min_ratio * D_base_ik
    
    # Calculate initial baseline
    s_baseline = np.zeros(N)
    D_base_i = np.zeros(N)
    for i in range(N):
        for p in K_i.get(i, []):
            D_base_i[i] = max(D_base_i[i], D_base_ik[p])
            
    # Forward pass baseline
    prec_i = precedence["i"].values.astype(int)
    prec_j = precedence["j"].values.astype(int)
    prec_lag = precedence["lag"].values.astype(float)
    prec_type = precedence["type"].values
    for _ in range(N):
        s_prev = s_baseline.copy()
        for idx in range(len(prec_i)):
            i, j = prec_i[idx], prec_j[idx]
            lag, t = prec_lag[idx], prec_type[idx]
            if t == "FS": cand = s_baseline[j] + D_base_i[j] + lag
            elif t == "FF": cand = s_baseline[j] + D_base_i[j] + lag - D_base_i[i]
            elif t == "SS": cand = s_baseline[j] + lag
            else: continue
            if cand > s_baseline[i]: s_baseline[i] = cand
        if np.allclose(s_baseline, s_prev, atol=1e-8):
            break
    f_baseline = s_baseline + D_base_i
    completed_tasks = set(i for i in range(N) if f_baseline[i] <= current_day and D_base_i[i] > 1e-9)
    completed_pairs = set(p for p in range(P) if int(resources.loc[p, "i"]) in completed_tasks)

    s = {}
    e = {}
    d_i = {}
    
    horizon = int(np.max(f_baseline)) + 100
    if mode == "cost_with_deadline":
        horizon = max(horizon, int(T_max) + 100)
    
    # Variables
    # b[p][opt_idx] is boolean
    b = {}
    d_ik = {}
    cost_ik = {}
    scale = 1000  # For cost precision
    
    total_labor_cost_scaled = 0
    
    for i in range(N):
        s[i] = model.NewIntVar(0, horizon, f"s_{i}")
        e[i] = model.NewIntVar(0, horizon, f"e_{i}")
        d_i[i] = model.NewIntVar(0, horizon, f"d_i_{i}")
        model.Add(e[i] == s[i] + d_i[i])
        
        if i in completed_tasks:
            model.Add(s[i] == int(s_baseline[i]))
            model.Add(d_i[i] == int(np.ceil(D_base_i[i])))
        else:
            model.Add(s[i] >= int(np.ceil(current_day)))
            
        for p in K_i.get(i, []):
            d_ik[p] = model.NewIntVar(0, horizon, f"d_ik_{p}")
            cost_ik[p] = model.NewIntVar(0, 1000000000, f"cost_ik_{p}")
            
            if p in completed_pairs:
                model.Add(d_ik[p] == int(np.ceil(D_base_ik[p])))
                cost = int(D_base_ik[p] * U_ik[p] * (hours_per_day * r_k[p]) * scale)
                model.Add(cost_ik[p] == cost)
            else:
                b[p] = {}
                for opt_idx, opt in enumerate(options):
                    b[p][opt_idx] = model.NewBoolVar(f"b_{p}_{opt_idx}")
                model.AddExactlyOne(b[p].values())
                
                for opt_idx, opt in enumerate(options):
                    x_val = opt["x"]
                    tau_val = opt["tau"]
                    dur = D_base_ik[p] * (1.0 / x_val)**alpha * (8.0 / (8.0 + tau_val))**beta
                    # ensure D_min constraint
                    if dur < D_min_ik[p] - 1e-5:
                        model.Add(b[p][opt_idx] == 0)
                        
                    dur_int = int(np.ceil(dur))
                    model.Add(d_ik[p] == dur_int).OnlyEnforceIf(b[p][opt_idx])
                    
                    cost_val = dur * x_val * U_ik[p] * (hours_per_day * r_k[p] + tau_val * r_k_ot[p])
                    model.Add(cost_ik[p] == int(cost_val * scale)).OnlyEnforceIf(b[p][opt_idx])
            
            total_labor_cost_scaled += cost_ik[p]
            model.Add(d_i[i] >= d_ik[p])

    # Precedence
    for idx in range(len(prec_i)):
        i, j = prec_i[idx], prec_j[idx]
        lag, t = prec_lag[idx], prec_type[idx]
        if t == "FS":
            model.Add(s[i] >= e[j] + int(np.ceil(lag)))
        elif t == "FF":
            model.Add(e[i] >= e[j] + int(np.ceil(lag)))
        elif t == "SS":
            model.Add(s[i] >= s[j] + int(np.ceil(lag)))
            
    Cmax = model.NewIntVar(0, horizon, "Cmax")
    for i in range(N):
        model.Add(Cmax >= e[i])
        
    tlc_var = model.NewIntVar(0, 1000000000, "tlc_var")
    model.Add(tlc_var == total_labor_cost_scaled)
        
    if mode == "cost_with_deadline":
        model.Add(Cmax <= int(np.ceil(T_max)))
        model.Minimize(tlc_var)
    elif mode == "time_with_budget":
        model.Add(tlc_var <= int(budget_limit * scale))
        model.Minimize(Cmax)
    elif mode == "bonus_penalty":
        T_max_int = int(np.ceil(T_max))
        late_days = model.NewIntVar(0, horizon, "late_days")
        early_days = model.NewIntVar(0, horizon, "early_days")
        model.AddMaxEquality(late_days, [0, Cmax - T_max_int])
        model.AddMaxEquality(early_days, [0, T_max_int - Cmax])
        
        c_late_scaled = int(c_late * scale)
        c_early_scaled = int(c_early * scale)
        
        penalty_scaled = model.NewIntVar(0, 1000000000, "penalty_scaled")
        bonus_scaled = model.NewIntVar(0, 1000000000, "bonus_scaled")
        model.Add(penalty_scaled == c_late_scaled * late_days)
        model.Add(bonus_scaled == c_early_scaled * early_days)
        
        obj = model.NewIntVar(-1000000000, 1000000000, "obj")
        model.Add(obj == tlc_var + penalty_scaled - bonus_scaled)
        model.Minimize(obj)

    solver = cp_model.CpSolver()
    solver.parameters.max_time_in_seconds = time_limit
    status = solver.Solve(model)
    
    if status in [cp_model.OPTIMAL, cp_model.FEASIBLE]:
        x_opt = np.ones(P)
        tau_opt = np.zeros(P)
        for p in range(P):
            if p not in completed_pairs:
                for opt_idx, opt in enumerate(options):
                    if solver.Value(b[p][opt_idx]):
                        x_opt[p] = opt["x"]
                        tau_opt[p] = opt["tau"]
                        break
        makespan = solver.Value(Cmax)
        labor_cost = solver.Value(tlc_var) / scale
        print(f"MILP Solver: Status={solver.StatusName(status)}, Makespan={makespan}, Labor Cost={labor_cost}")
        
        # Prepare for saving
        # Let's populate D_ik_opt, D_i_opt, s_opt, f_opt
        D_ik_opt = np.zeros(P)
        for p in range(P):
            D_ik_opt[p] = solver.Value(d_ik[p])
        D_i_opt = np.zeros(N)
        s_opt = np.zeros(N)
        f_opt = np.zeros(N)
        for i in range(N):
            D_i_opt[i] = solver.Value(d_i[i])
            s_opt[i] = solver.Value(s[i])
            f_opt[i] = solver.Value(e[i])
            
        class FakeProblem:
            def __init__(self):
                self.r_k = r_k
                self.U_ik = U_ik
                self.W_ik = resources["W_ik"].values
                self.hours_per_day = hours_per_day
                self.r_k_ot = r_k_ot
                self.D_base_ik = D_base_ik
                self.K_i = K_i
                self.s_baseline = s_baseline
                self.f_baseline = f_baseline
                self.D_base_i = D_base_i
        
        out_json = os.path.join(os.path.dirname(__file__), f"../outputs/milp_cobb_{mode}.json")
        save_solution_json(
            tasks, resources, precedence, FakeProblem(),
            np.concatenate([x_opt, tau_opt]), x_opt, tau_opt, D_ik_opt, D_i_opt, s_opt, f_opt,
            current_day, T_max, makespan, labor_cost, labor_cost, out_json
        )
    else:
        print(f"MILP Solver: No feasible solution found for mode {mode}.")

if __name__ == "__main__":
    tasks, precedence, resources, N, K_i = load_data(
        path_tasks=data_path("data_tasks.csv"),
        path_precedence=data_path("data_precedence.csv"),
        path_assignments=data_path("data_assignments.csv"),
    )
    solve_milp_cobb_douglas(tasks, precedence, resources, N, K_i, mode="cost_with_deadline")
