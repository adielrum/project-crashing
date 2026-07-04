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
    x_options = np.arange(x_min, x_max + 0.1, 0.25)
    tau_options = np.arange(tau_min, tau_max + 0.1, 1.0)
    
    raw_options = []
    for x in x_options:
        for tau in tau_options:
            raw_options.append({"x": x, "tau": tau})
            
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
    
    scale = 1000  # For cost precision
    
    # ── Per-pair: build deduplicated feasible option tables ──────────────
    # Instead of creating 15 booleans per pair with conditional constraints,
    # we precompute the feasible (dur_int, cost_int) tuples, deduplicate them
    # (many options ceil to the same duration), keep only the cheapest per
    # unique duration, and use a single integer index variable + AddElement.
    
    b = {}            # b[p] = index variable  (int, not dict-of-bools)
    d_ik = {}
    cost_ik = {}
    pair_options = {} # pair_options[p] = list of {x, tau, dur_int, cost_int}
    
    total_labor_cost_scaled = 0
    
    for i in range(N):
        # Tighter domain bounds for start/end using baseline knowledge
        s_lb = 0 if i not in completed_tasks else int(s_baseline[i])
        s_ub = horizon
        
        s[i] = model.NewIntVar(s_lb, s_ub, f"s_{i}")
        e[i] = model.NewIntVar(s_lb, s_ub, f"e_{i}")
        
        # Duration: at most the baseline (no crashing makes it longer), at least 0
        d_max_i = int(np.ceil(D_base_i[i])) if D_base_i[i] > 0 else 0
        d_i[i] = model.NewIntVar(0, max(d_max_i, 1), f"d_i_{i}")
        model.Add(e[i] == s[i] + d_i[i])
        
        if i in completed_tasks:
            model.Add(s[i] == int(s_baseline[i]))
            model.Add(d_i[i] == int(np.ceil(D_base_i[i])))
        else:
            model.Add(s[i] >= int(np.ceil(current_day)))
            
        for p in K_i.get(i, []):
            if p in completed_pairs:
                dur_fixed = int(np.ceil(D_base_ik[p]))
                cost_fixed = int(D_base_ik[p] * U_ik[p] * (hours_per_day * r_k[p]) * scale)
                d_ik[p] = model.NewIntVar(dur_fixed, dur_fixed, f"d_ik_{p}")
                cost_ik[p] = model.NewIntVar(cost_fixed, cost_fixed, f"cost_ik_{p}")
            else:
                # ── Build feasible options, deduplicate ──────────────
                feasible = []
                for opt in raw_options:
                    x_val = opt["x"]
                    tau_val = opt["tau"]
                    dur = D_base_ik[p] * (1.0 / x_val)**alpha * (8.0 / (8.0 + tau_val))**beta
                    # Enforce D_min constraint: skip infeasible options entirely
                    if dur < D_min_ik[p] - 1e-5:
                        continue
                    dur_int = int(np.ceil(dur))
                    cost_val = dur * x_val * U_ik[p] * (hours_per_day * r_k[p] + tau_val * r_k_ot[p])
                    cost_int = int(cost_val * scale)
                    feasible.append({
                        "x": x_val, "tau": tau_val,
                        "dur_int": dur_int, "cost_int": cost_int,
                    })
                
                # Deduplicate: for options with same dur_int, keep cheapest
                best_by_dur = {}
                for f in feasible:
                    key = f["dur_int"]
                    if key not in best_by_dur or f["cost_int"] < best_by_dur[key]["cost_int"]:
                        best_by_dur[key] = f
                deduped = sorted(best_by_dur.values(), key=lambda f: f["dur_int"])
                
                # Further prune dominated options:
                # An option is dominated if another has both lower-or-equal
                # duration AND lower-or-equal cost.
                pruned = []
                for f in deduped:
                    dominated = False
                    for g in deduped:
                        if g is f:
                            continue
                        if g["dur_int"] <= f["dur_int"] and g["cost_int"] <= f["cost_int"]:
                            dominated = True
                            break
                    if not dominated:
                        pruned.append(f)
                
                if not pruned:
                    # Fallback: use baseline (no crash)
                    dur_int = int(np.ceil(D_base_ik[p]))
                    cost_int = int(D_base_ik[p] * U_ik[p] * (hours_per_day * r_k[p]) * scale)
                    pruned = [{"x": 1.0, "tau": 0.0, "dur_int": dur_int, "cost_int": cost_int}]
                
                pair_options[p] = pruned
                n_opts = len(pruned)
                
                if n_opts == 1:
                    # Only one feasible option — fix the values directly
                    d_ik[p] = model.NewIntVar(pruned[0]["dur_int"], pruned[0]["dur_int"], f"d_ik_{p}")
                    cost_ik[p] = model.NewIntVar(pruned[0]["cost_int"], pruned[0]["cost_int"], f"cost_ik_{p}")
                else:
                    # Use AddElement: idx selects from precomputed tables
                    dur_table = [f["dur_int"] for f in pruned]
                    cost_table = [f["cost_int"] for f in pruned]
                    
                    idx_var = model.NewIntVar(0, n_opts - 1, f"idx_{p}")
                    b[p] = idx_var
                    
                    d_min_p = min(dur_table)
                    d_max_p = max(dur_table)
                    c_min_p = min(cost_table)
                    c_max_p = max(cost_table)
                    
                    d_ik[p] = model.NewIntVar(d_min_p, d_max_p, f"d_ik_{p}")
                    cost_ik[p] = model.NewIntVar(c_min_p, c_max_p, f"cost_ik_{p}")
                    
                    model.AddElement(idx_var, dur_table, d_ik[p])
                    model.AddElement(idx_var, cost_table, cost_ik[p])
            
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

    # ── Search strategy hints ────────────────────────────────────────────
    # Guide the solver to branch on the index variables first with
    # a minimum-value strategy (prefer shorter durations / lower cost).
    idx_vars = [b[p] for p in sorted(b.keys())]
    if idx_vars:
        model.AddDecisionStrategy(
            idx_vars,
            cp_model.CHOOSE_FIRST,
            cp_model.SELECT_MIN_VALUE,
        )

    solver = cp_model.CpSolver()
    solver.parameters.max_time_in_seconds = time_limit
    # Use all available cores
    solver.parameters.num_workers = 1
    # solver.parameters.log_search_progress = True  # enable for debugging
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
        makespan = solver.Value(Cmax)
        labor_cost = solver.Value(tlc_var) / scale
        print(f"MILP Solver: Status={solver.StatusName(status)}, Makespan={makespan}, Labor Cost={labor_cost}")
        
        # Prepare for saving
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
        
        out_json = os.path.join(os.path.dirname(__file__), f"../outputs/milp/milp_cobb_{mode}.json")
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
    solve_milp_cobb_douglas(tasks, precedence, resources, N, K_i, mode="cost_with_deadline")