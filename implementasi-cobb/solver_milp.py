import os
import json
import argparse
import numpy as np
import pandas as pd
from ortools.sat.python import cp_model
from cobb_model import load_data, data_path, save_solution_json


def solve_milp_cobb_douglas(
    tasks, precedence, resources, N, K_i,
    resource_master=None,
    alpha=0.7, beta=0.7, x_min=1.0, x_max=2.0, tau_min=0.0, tau_max=4.0, D_min_ratio=0.5,
    T_max=344, current_day=0, overtime_mult=1.5, hours_per_day=8, mode="bonus_penalty",
    budget_limit=None, c_late=5000.0, c_early=2000.0, time_limit=60.0,
    enforce_resource_constraint=True,
):
    model = cp_model.CpModel()

    # Pre-calculate discrete options (grid untuk x_{i,k} dan tau_{i,k})
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
    res_task_idx = resources["i"].values

    # ── Calculate initial baseline (x=1, tau=0, tanpa crashing) ──────────────
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

    # ── Klasifikasi status 3-kategori terhadap current_day (T0) ─────────────
    # Sesuai slide Skenario 2 (slide 26): Selesai / Berjalan / Belum Mulai.
    completed_tasks = set(
        i for i in range(N)
        if f_baseline[i] <= current_day and D_base_i[i] > 1e-9
    )
    in_progress_tasks = set(
        i for i in range(N)
        if i not in completed_tasks
        and s_baseline[i] <= current_day < f_baseline[i]
        and D_base_i[i] > 1e-9
    )

    # Proporsi progress p_i (estimasi linear dari baseline, slide 26 keterangan)
    p_i = np.zeros(N)
    for i in in_progress_tasks:
        p_i[i] = float(np.clip(
            (current_day - s_baseline[i]) / D_base_i[i], 0.0, 1.0
        ))

    completed_pairs = set(p for p in range(P) if int(resources.loc[p, "i"]) in completed_tasks)
    in_progress_pairs = set(p for p in range(P) if int(resources.loc[p, "i"]) in in_progress_tasks)

    # ── Durasi baseline efektif per pasangan (i,k) ───────────────────────────
    # Task berjalan: hanya SISA usaha kerja W_i,k*(1-p_i) relevan untuk
    # mekanisme crashing (D ∝ W pada formula durasi dasar, slide 21).
    D_base_ik_eff = D_base_ik.copy()
    for p in in_progress_pairs:
        i = int(resources.loc[p, "i"])
        D_base_ik_eff[p] = D_base_ik[p] * (1.0 - p_i[i])
    # D_min dihitung dari rasio terhadap durasi baseline EFEKTIF, supaya batas
    # crash-minimum task berjalan proporsional dengan sisa kerjanya.
    D_min_ik = D_min_ratio * D_base_ik_eff

    # ── Setup Resource Constraint (U_k^max per resource_id) ─────────────────
    if "resource_id" in resources.columns and resource_master is not None:
        resource_ids = resources["resource_id"].values
        unique_resource_ids = np.unique(resource_ids)
        R = len(unique_resource_ids)
        pairs_by_resource = {
            rid: np.where(resource_ids == rid)[0] for rid in unique_resource_ids
        }
        avail_map = resource_master.set_index("resource_id")["resource_availability"]
        U_max_k = np.array([float(avail_map.loc[rid]) for rid in unique_resource_ids])
    else:
        resource_ids = None
        unique_resource_ids = np.array([])
        R = 0
        pairs_by_resource = {}
        U_max_k = np.array([])
        enforce_resource_constraint = False

    s = {}
    e = {}
    d_i = {}

    horizon = int(np.max(f_baseline)) + 100
    if mode == "cost_with_deadline":
        horizon = max(horizon, int(T_max) + 100)

    scale = 1000  # For cost precision

    # ── Per-pair: build deduplicated feasible option tables 

    b = {}            # b[p] = index variable  (int, not dict-of-bools)
    d_ik = {}
    cost_ik = {}
    pair_options = {} # pair_options[p] = list of {x, tau, dur_int, cost_int}

    total_labor_cost_scaled = 0

    locked_pairs = completed_pairs

    for i in range(N):
        is_locked_start = i in completed_tasks or i in in_progress_tasks
        s_lb = int(s_baseline[i]) if is_locked_start else 0
        s_ub = horizon

        s[i] = model.NewIntVar(s_lb, s_ub, f"s_{i}")
        e[i] = model.NewIntVar(s_lb, s_ub, f"e_{i}")

        d_max_i = int(np.ceil(D_base_i[i])) if D_base_i[i] > 0 else 0
        d_i[i] = model.NewIntVar(0, max(d_max_i, 1), f"d_i_{i}")
        model.Add(e[i] == s[i] + d_i[i])

        if i in completed_tasks:
            model.Add(s[i] == int(s_baseline[i]))
            model.Add(d_i[i] == int(np.ceil(D_base_i[i])))
        elif i in in_progress_tasks:

            model.Add(s[i] == int(s_baseline[i]))
        else:
            model.Add(s[i] >= int(np.ceil(current_day)))

        for p in K_i.get(i, []):
            if p in locked_pairs:
                dur_fixed = int(np.ceil(D_base_ik[p]))
                cost_fixed = int(D_base_ik[p] * U_ik[p] * (hours_per_day * r_k[p]) * scale)
                d_ik[p] = model.NewIntVar(dur_fixed, dur_fixed, f"d_ik_{p}")
                cost_ik[p] = model.NewIntVar(cost_fixed, cost_fixed, f"cost_ik_{p}")
            else:
                feasible = []
                for opt in raw_options:
                    x_val = opt["x"]
                    tau_val = opt["tau"]
                    dur = D_base_ik_eff[p] * (1.0 / x_val)**alpha * (8.0 / (8.0 + tau_val))**beta
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
                    # Fallback: use baseline (no crash) atas durasi efektif
                    dur_int = int(np.ceil(D_base_ik_eff[p]))
                    cost_int = int(D_base_ik_eff[p] * U_ik[p] * (hours_per_day * r_k[p]) * scale)
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

    # ── Precedence (FS, FF, SS dengan lag) ───────────────────────────────────
    for idx in range(len(prec_i)):
        i, j = prec_i[idx], prec_j[idx]
        lag, t = prec_lag[idx], prec_type[idx]
        if t == "FS":
            model.Add(s[i] >= e[j] + int(np.ceil(lag)))
        elif t == "FF":
            model.Add(e[i] >= e[j] + int(np.ceil(lag)))
        elif t == "SS":
            model.Add(s[i] >= s[j] + int(np.ceil(lag)))

    # ── Resource Capacity Constraint (slide 27, Skenario 2) ──────────────────
    if enforce_resource_constraint and R > 0:
        for k_idx, rid in enumerate(unique_resource_ids):
            pair_idx = pairs_by_resource[rid]
            if len(pair_idx) == 0:
                continue

            intervals = []
            demands = []
            for p in pair_idx:
                i = int(res_task_idx[p])
                start_var = s[i]
                dur_var = d_ik[p]
                end_var = model.NewIntVar(0, horizon, f"end_pk_{p}")
                model.Add(end_var == start_var + dur_var)
                interval = model.NewIntervalVar(start_var, dur_var, end_var, f"interval_pk_{p}")
                intervals.append(interval)
                demands.append(int(round(U_ik[p])))

            U_max_int = int(np.floor(U_max_k[k_idx]))
            if U_max_int > 0:
                model.AddCumulative(intervals, demands, U_max_int)
            else:
                # Kapasitas 0 → tidak ada aktivitas yang boleh memakai resource ini
                for p in pair_idx:
                    model.Add(d_ik[p] == 0)

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
    elif mode == "multiobjective":
        model.Add(Cmax <= int(np.ceil(T_max)))
        model.Minimize(tlc_var)
    else:
        raise ValueError(f"Mode tidak dikenal: {mode}")

    idx_vars = [b[p] for p in sorted(b.keys())]
    if idx_vars:
        model.AddDecisionStrategy(
            idx_vars,
            cp_model.CHOOSE_FIRST,
            cp_model.SELECT_MIN_VALUE,
        )

    solver = cp_model.CpSolver()
    solver.parameters.max_time_in_seconds = time_limit
    solver.parameters.num_workers = 1
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
                self.D_base_ik_eff = D_base_ik_eff
                self.K_i = K_i
                self.s_baseline = s_baseline
                self.f_baseline = f_baseline
                self.D_base_i = D_base_i
                self.completed_tasks = completed_tasks
                self.in_progress_tasks = in_progress_tasks
                self.p_i = p_i
                self.res_task_idx = res_task_idx
                self.R = R
                self.unique_resource_ids = unique_resource_ids
                self.U_max_k = U_max_k
                self.pairs_by_resource = pairs_by_resource

            def _evaluate_resource_constraints(self, s_vec, D_ik_vec):

                if self.R == 0:
                    return np.zeros(0)
                checkpoints = s_vec
                G_res = np.empty(self.R)
                for k_idx, rid in enumerate(self.unique_resource_ids):
                    pair_idx = self.pairs_by_resource[rid]
                    if len(pair_idx) == 0:
                        G_res[k_idx] = -self.U_max_k[k_idx]
                        continue
                    s_i_k = s_vec[self.res_task_idx[pair_idx]]
                    d_i_k = D_ik_vec[pair_idx]
                    U_i_k = self.U_ik[pair_idx]
                    start_le = s_i_k[:, None] <= checkpoints[None, :]
                    end_gt = checkpoints[None, :] < (s_i_k + d_i_k)[:, None]
                    active = start_le & end_gt
                    used_at_j = (U_i_k[:, None] * active).sum(axis=0)
                    G_res[k_idx] = float(np.max(used_at_j)) - self.U_max_k[k_idx]
                return G_res

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
            "f": f_opt,
            "status": solver.StatusName(status),
        }
    else:
        print(f"MILP Solver: No feasible solution found for mode {mode}.")
        return None


def run_milp_multiobjective(
    tasks, precedence, resources, N, K_i, resource_master=None,
    alpha=0.7, beta=0.7, x_min=1.0, x_max=2.0, tau_min=0.0, tau_max=4.0,
    D_min_ratio=0.5, current_day=0, overtime_mult=1.5, hours_per_day=8,
    c_late=5000.0, c_early=2000.0, time_limit=20.0,
    enforce_resource_constraint=True,
    t_max_values=None,
):
    if t_max_values is None:
        # Default sweep range; sesuaikan dengan kebutuhan proyek.
        t_max_values = np.arange(280, 350, 5)

    pareto_points = []
    for t_max in t_max_values:
        sol = solve_milp_cobb_douglas(
            tasks, precedence, resources, N, K_i,
            resource_master=resource_master,
            alpha=alpha, beta=beta, x_min=x_min, x_max=x_max,
            tau_min=tau_min, tau_max=tau_max, D_min_ratio=D_min_ratio,
            T_max=float(t_max), current_day=current_day,
            overtime_mult=overtime_mult, hours_per_day=hours_per_day,
            mode="multiobjective", time_limit=time_limit,
            enforce_resource_constraint=enforce_resource_constraint,
        )
        if sol is not None:
            pareto_points.append({
                "T_max": float(t_max),
                "makespan": sol["makespan"],
                "labor_cost": sol["labor_cost"],
            })

    return pareto_points


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Solve Model 2 (Cobb-Douglas) crashing via MILP/CP-SAT discretization"
    )
    parser.add_argument("--path-tasks", default=data_path("data_tasks.csv"))
    parser.add_argument("--path-precedence", default=data_path("data_precedence.csv"))
    parser.add_argument("--path-assignments", default=data_path("data_assignments.csv"))
    parser.add_argument("--path-resources", default=data_path("data_resources.csv"))
    parser.add_argument("--current-day", type=int, default=0)
    parser.add_argument("--T-max", type=float, default=344)
    parser.add_argument(
        "--mode", default="cost_with_deadline",
        choices=["cost_with_deadline", "time_with_budget", "bonus_penalty", "multiobjective"],
    )
    parser.add_argument("--budget-limit", type=float, default=500000.0)
    parser.add_argument("--time-limit", type=float, default=60.0)
    parser.add_argument("--no-resource-constraint", action="store_true",
                         help="Matikan resource capacity constraint (U_k^max)")
    args = parser.parse_args()

    tasks, precedence, resources, N, K_i, resource_master = load_data(
        path_tasks=args.path_tasks,
        path_precedence=args.path_precedence,
        path_assignments=args.path_assignments,
        path_resources=args.path_resources,
    )

    solution = solve_milp_cobb_douglas(
        tasks, precedence, resources, N, K_i,
        resource_master=resource_master,
        T_max=args.T_max,
        current_day=args.current_day,
        mode=args.mode,
        budget_limit=args.budget_limit,
        time_limit=args.time_limit,
        enforce_resource_constraint=not args.no_resource_constraint,
    )

    if solution is not None:
        print(f"\nMakespan     : {solution['makespan']:.2f} hari")
        print(f"Labor Cost   : {solution['labor_cost']:.2f} USD")
        print(f"Total Cost   : {solution['total_cost']:.2f} USD")