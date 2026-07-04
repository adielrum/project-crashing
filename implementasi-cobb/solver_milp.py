import os
import json
import argparse
import numpy as np
import pandas as pd
from ortools.sat.python import cp_model
from cobb_model import load_data, data_path, save_solution_json, ResourceBasedScheduling

def solve_milp_cobb_douglas(
    tasks, precedence, resources, N, K_i, 
    alpha=0.7, beta=0.7, x_min=1.0, x_max=None, tau_min=0.0, tau_max=4.0, D_min_ratio=0.5,
    T_max=344, current_day=0, overtime_mult=1.5, hours_per_day=8, mode="cost_with_deadline",
    budget_limit=None, c_late=5000.0, c_early=2000.0, time_limit=60.0,
    completion_fraction=None, enforce_resource_capacity=True, time_scale=100,
    dx=0.1, dtau=0.1,
):
    model = cp_model.CpModel()

    if x_max is None:
        x_max = ResourceBasedScheduling._compute_x_max(alpha, x_min)

    x_options = np.arange(x_min, x_max + dx/2.0, dx)
    tau_options = np.arange(tau_min, tau_max + dtau/2.0, dtau)
    
    raw_options = []
    for x in x_options:
        for tau in tau_options:
            raw_options.append({"x": round(float(x), 4), "tau": round(float(tau), 4)})
            
    P = len(resources)
    r_k = resources["r_k_usd"].values
    r_k_ot = r_k * overtime_mult
    U_ik = resources["U_ik"].values
    D_base_ik = resources["D_base_ik"].values
    
    s_baseline = np.zeros(N)
    D_base_i = np.zeros(N)
    for i in range(N):
        for p in K_i.get(i, []):
            D_base_i[i] = max(D_base_i[i], D_base_ik[p])
            
    prec_i = precedence["i"].values.astype(int)
    prec_j = precedence["j"].values.astype(int)
    prec_lag = precedence["lag"].values.astype(float)
    prec_type = precedence["type"].values
    
    for _ in range(N):
        for idx in range(len(prec_i)):
            i = prec_i[idx]
            j = prec_j[idx]
            lag = prec_lag[idx]
            t = prec_type[idx]
            if t == "FS":
                s_baseline[j] = max(s_baseline[j], s_baseline[i] + D_base_i[i] + lag)
            elif t == "FF":
                s_baseline[j] = max(s_baseline[j], s_baseline[i] + D_base_i[i] + lag - D_base_i[j])
            elif t == "SS":
                s_baseline[j] = max(s_baseline[j], s_baseline[i] + lag)
                
    f_baseline = s_baseline + D_base_i

    completed_tasks = set()
    partial_tasks = set()
    partial_frac_by_idx = {}
    if completion_fraction is not None:
        for idx, p_i in enumerate(completion_fraction):
            if p_i >= 1.0 - 1e-6:
                completed_tasks.add(idx)
            elif p_i > 1e-6:
                partial_tasks.add(idx)
                partial_frac_by_idx[idx] = p_i
    completed_pairs = set(p for p in range(P) if int(resources.loc[p, "i"]) in completed_tasks)
    locked_start_tasks = completed_tasks | partial_tasks

    D_base_ik_eff = D_base_ik.copy()
    for p in range(P):
        i_task = int(resources.loc[p, "i"])
        if i_task in partial_tasks:
            D_base_ik_eff[p] = D_base_ik[p] * (1.0 - partial_frac_by_idx[i_task])
    D_min_ik = D_min_ratio * D_base_ik_eff

    have_capacity_data = enforce_resource_capacity and ("U_max_k" in resources.columns)
    DEMAND_SCALE = 100

    s = {}
    e = {}
    d_i = {}
    
    horizon = int(np.max(f_baseline) * time_scale) + int(100 * time_scale)
    if mode == "cost_with_deadline":
        horizon = max(horizon, int(T_max * time_scale) + int(100 * time_scale))
    
    scale = 1000
    
    b = {}
    d_ik = {}
    cost_ik = {}
    demand_ik = {}
    pair_options = {}
    resource_intervals = {}
    resource_demands = {}
    
    total_labor_cost_scaled = 0
    
    for i in range(N):
        s_lb = 0 if i not in locked_start_tasks else int(round(s_baseline[i] * time_scale))
        s_ub = horizon
        
        s[i] = model.NewIntVar(s_lb, s_ub, f"s_{i}")
        e[i] = model.NewIntVar(s_lb, s_ub, f"e_{i}")
        
        if i in partial_tasks:
            d_cap = max((D_base_ik_eff[p] for p in K_i.get(i, [])), default=0.0)
        else:
            d_cap = D_base_i[i]
        d_max_i = int(np.ceil(d_cap * time_scale)) if d_cap > 0 else 0
        d_i[i] = model.NewIntVar(0, max(d_max_i, 1), f"d_i_{i}")
        model.Add(e[i] == s[i] + d_i[i])
        
        if i in completed_tasks:
            model.Add(s[i] == int(round(s_baseline[i] * time_scale)))
            model.Add(d_i[i] == int(np.ceil(D_base_i[i] * time_scale)))
        elif i in partial_tasks:
            model.Add(s[i] == int(round(s_baseline[i] * time_scale)))
        else:
            model.Add(s[i] >= int(np.ceil(current_day * time_scale)))
            
        for p in K_i.get(i, []):
            if p in completed_pairs:
                dur_fixed = int(np.ceil(D_base_ik[p] * time_scale))
                cost_fixed = int(D_base_ik[p] * U_ik[p] * (hours_per_day * r_k[p]) * scale)
                demand_fixed = int(np.ceil(1.0 * U_ik[p] * DEMAND_SCALE))
                d_ik[p] = model.NewIntVar(dur_fixed, dur_fixed, f"d_ik_{p}")
                cost_ik[p] = model.NewIntVar(cost_fixed, cost_fixed, f"cost_ik_{p}")
                demand_ik[p] = model.NewIntVar(demand_fixed, demand_fixed, f"demand_ik_{p}")
            else:
                d_base_p = D_base_ik_eff[p]
                feasible = []
                for opt in raw_options:
                    x_val = opt["x"]
                    tau_val = opt["tau"]
                    dur = d_base_p * (1.0 / x_val)**alpha * (8.0 / (8.0 + tau_val))**beta
                    if dur < D_min_ik[p] - 1e-5:
                        continue
                    dur_int = int(np.ceil(dur * time_scale))
                    cost_val = dur * x_val * U_ik[p] * (hours_per_day * r_k[p] + tau_val * r_k_ot[p])
                    cost_int = int(cost_val * scale)
                    demand_int = int(np.ceil(x_val * U_ik[p] * DEMAND_SCALE))
                    feasible.append({
                        "x": x_val, "tau": tau_val,
                        "dur_int": dur_int, "cost_int": cost_int, "demand_int": demand_int,
                    })
                
                best_for_dur = {}
                for f in feasible:
                    k = f["dur_int"]
                    if k not in best_for_dur or f["cost_int"] < best_for_dur[k]["cost_int"]:
                        best_for_dur[k] = f
                deduped = sorted(best_for_dur.values(), key=lambda f: f["dur_int"])
                
                pruned = []
                for f in deduped:
                    dominated = False
                    for g in deduped:
                        if g is f:
                            continue
                        if (g["dur_int"] <= f["dur_int"] and g["cost_int"] <= f["cost_int"]
                                and g["x"] <= f["x"]):
                            dominated = True
                            break
                    if not dominated:
                        pruned.append(f)
                
                if not pruned:
                    dur_int = int(np.ceil(d_base_p * time_scale))
                    cost_int = int(d_base_p * U_ik[p] * (hours_per_day * r_k[p]) * scale)
                    demand_int = int(np.ceil(1.0 * U_ik[p] * DEMAND_SCALE))
                    pruned = [{"x": 1.0, "tau": 0.0, "dur_int": dur_int, "cost_int": cost_int, "demand_int": demand_int}]
                
                pair_options[p] = pruned
                n_opts = len(pruned)
                
                if n_opts == 1:
                    d_ik[p] = model.NewIntVar(pruned[0]["dur_int"], pruned[0]["dur_int"], f"d_ik_{p}")
                    cost_ik[p] = model.NewIntVar(pruned[0]["cost_int"], pruned[0]["cost_int"], f"cost_ik_{p}")
                    demand_ik[p] = model.NewIntVar(pruned[0]["demand_int"], pruned[0]["demand_int"], f"demand_ik_{p}")
                else:
                    dur_table = [f["dur_int"] for f in pruned]
                    cost_table = [f["cost_int"] for f in pruned]
                    demand_table = [f["demand_int"] for f in pruned]
                    
                    idx_var = model.NewIntVar(0, n_opts - 1, f"idx_{p}")
                    b[p] = idx_var
                    
                    d_ik[p] = model.NewIntVar(min(dur_table), max(dur_table), f"d_ik_{p}")
                    cost_ik[p] = model.NewIntVar(min(cost_table), max(cost_table), f"cost_ik_{p}")
                    demand_ik[p] = model.NewIntVar(min(demand_table), max(demand_table), f"demand_ik_{p}")
                    
                    model.AddElement(idx_var, dur_table, d_ik[p])
                    model.AddElement(idx_var, cost_table, cost_ik[p])
                    model.AddElement(idx_var, demand_table, demand_ik[p])
            
            total_labor_cost_scaled += cost_ik[p]
            model.Add(d_i[i] >= d_ik[p])

            if have_capacity_data:
                end_r = model.NewIntVar(0, horizon, f"end_r_{p}")
                model.Add(end_r == s[i] + d_ik[p])
                resource_intervals.setdefault(int(resources.loc[p, "resource_id"]), []).append(
                    model.NewIntervalVar(s[i], d_ik[p], end_r, f"ivl_{p}")
                )
                resource_demands.setdefault(int(resources.loc[p, "resource_id"]), []).append(demand_ik[p])

    if have_capacity_data:
        for rid, intervals in resource_intervals.items():
            cap_rows = resources.loc[resources["resource_id"] == rid, "U_max_k"]
            cap_val = float(cap_rows.iloc[0])
            if not np.isfinite(cap_val):
                continue
            capacity_int = int(np.floor(cap_val * DEMAND_SCALE))
            model.AddCumulative(intervals, resource_demands[rid], capacity_int)

    for idx in range(len(prec_i)):
        i, j = prec_i[idx], prec_j[idx]
        lag, t = prec_lag[idx], prec_type[idx]
        lag_int = int(np.ceil(lag * time_scale))
        if t == "FS":
            model.Add(s[i] >= e[j] + lag_int)
        elif t == "FF":
            model.Add(e[i] >= e[j] + lag_int)
        elif t == "SS":
            model.Add(s[i] >= s[j] + lag_int)
            
    Cmax = model.NewIntVar(0, horizon, "Cmax")
    for i in range(N):
        model.Add(Cmax >= e[i])
        
    tlc_var = model.NewIntVar(0, 10000000000, "tlc_var")
    model.Add(tlc_var == total_labor_cost_scaled)
        
    if mode == "cost_with_deadline":
        model.Add(Cmax <= int(np.ceil(T_max * time_scale)))
        model.Minimize(tlc_var)
    elif mode == "time_with_budget":
        model.Add(tlc_var <= int(budget_limit * scale))
        model.Minimize(Cmax)
    elif mode == "bonus_penalty":
        T_max_int = int(np.ceil(T_max * time_scale))
        late_days = model.NewIntVar(0, horizon, "late_days")
        early_days = model.NewIntVar(0, horizon, "early_days")
        model.AddMaxEquality(late_days, [0, Cmax - T_max_int])
        model.AddMaxEquality(early_days, [0, T_max_int - Cmax])
        
        c_late_scaled = int(round(c_late * scale / time_scale))
        c_early_scaled = int(round(c_early * scale / time_scale))
        
        penalty_scaled = model.NewIntVar(0, 10000000000, "penalty_scaled")
        bonus_scaled = model.NewIntVar(0, 10000000000, "bonus_scaled")
        model.Add(penalty_scaled == c_late_scaled * late_days)
        model.Add(bonus_scaled == c_early_scaled * early_days)
        
        obj = model.NewIntVar(-10000000000, 10000000000, "obj")
        model.Add(obj == tlc_var + penalty_scaled - bonus_scaled)
        model.Minimize(obj)

    idx_vars = [b[p] for p in sorted(b.keys())]
    if idx_vars:
        model.AddDecisionStrategy(
            idx_vars,
            cp_model.CHOOSE_FIRST,
            cp_model.SELECT_MIN_VALUE,
        )

    solver = cp_model.CpSolver()
    solver.parameters.max_time_in_seconds = time_limit
    solver.parameters.num_workers = 8
    status = solver.Solve(model)
    
    if status in [cp_model.OPTIMAL, cp_model.FEASIBLE]:
        x_opt = np.ones(P)
        tau_opt = np.zeros(P)
        for p in range(P):
            if p in pair_options:
                opts = pair_options[p]
                if len(opts) == 1:
                    x_opt[p] = opts[0]["x"]
                    tau_opt[p] = opts[0]["tau"]
                elif p in b:
                    chosen = solver.Value(b[p])
                    x_opt[p] = opts[chosen]["x"]
                    tau_opt[p] = opts[chosen]["tau"]
        makespan = solver.Value(Cmax) / float(time_scale)
        labor_cost = solver.Value(tlc_var) / float(scale)
        print(f"MILP Solver: Status={solver.StatusName(status)}, Makespan={makespan:.3f}, Labor Cost={labor_cost:.2f}")
        
        D_ik_opt = np.zeros(P)
        for p in range(P):
            D_ik_opt[p] = solver.Value(d_ik[p]) / float(time_scale)
        D_i_opt = np.zeros(N)
        s_opt = np.zeros(N)
        f_opt = np.zeros(N)
        for i in range(N):
            D_i_opt[i] = solver.Value(d_i[i]) / float(time_scale)
            s_opt[i] = solver.Value(s[i]) / float(time_scale)
            f_opt[i] = solver.Value(e[i]) / float(time_scale)
            
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
        total_cost = labor_cost
        if mode == "bonus_penalty":
            total_cost = labor_cost + c_late * max(0, makespan - T_max) - c_early * max(0, T_max - makespan)
        return {
            "makespan": makespan,
            "labor_cost": labor_cost,
            "total_cost": total_cost,
            "x_ik": x_opt,
            "tau_ik": tau_opt,
            "D_ik": D_ik_opt,
            "D_i": D_i_opt,
            "s": s_opt,
            "f": f_opt
        }
    else:
        print(f"MILP Solver: No feasible solution found for mode {mode}.")
        return None

if __name__ == "__main__":
    tasks, precedence, resources, N, K_i = load_data(
        path_tasks=data_path("data_tasks.csv"),
        path_precedence=data_path("data_precedence.csv"),
        path_assignments=data_path("data_assignments.csv"),
    )
    solve_milp_cobb_douglas(tasks, precedence, resources, N, K_i, mode="bonus_penalty")