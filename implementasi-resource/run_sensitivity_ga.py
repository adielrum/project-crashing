import os
import sys
import numpy as np
import pandas as pd
from tqdm import tqdm
from concurrent.futures import ProcessPoolExecutor, as_completed

# Ensure each worker process uses exactly 1 pymoo thread without thread contention
os.environ["PYMOO_THREADS"] = "1"

base_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.append(os.path.join(base_dir, "../comparison"))
from sensitivity_utils import plot_dual_axis_oat, plot_2panel_contour_heatmap, plot_pareto_shifts
from cobb_model import load_data, data_path, ResourceBasedScheduling, solve

# Global variables initialized once per worker process
_tasks, _precedence, _resources, _N, _K_i = None, None, None, None, None

def _init_worker():
    global _tasks, _precedence, _resources, _N, _K_i
    _tasks, _precedence, _resources, _N, _K_i = load_data(
        path_tasks=data_path("data_tasks.csv"),
        path_precedence=data_path("data_precedence.csv"),
        path_assignments=data_path("data_assignments.csv"),
    )

def _worker_eval_so(args):
    a, b, ce, cl, tmax, pop, gen, seed, current_day = args
    prob = ResourceBasedScheduling(
        tasks=_tasks, precedence=_precedence, resources=_resources, N=_N, K_i=_K_i,
        alpha=a, beta=b, T_max=tmax, current_day=current_day, 
        mode="bonus_penalty", c_late=cl, c_early=ce
    )
    sol = solve(prob, pop_size=pop, seed=seed, verbose=False, max_gen=gen, tol=0.002, period=35)
    if sol and isinstance(sol, dict) and "makespan" in sol:
        return {
            "alpha": a, "beta": b, "c_early": ce, "c_late": cl, "T_max": tmax,
            "makespan": sol["makespan"], "total_cost": sol["total_cost"], "net_cost": sol["total_cost"]
        }
    return None

def _worker_eval_grid(args):
    a, b, ce, cl, tmax, pop, gen, seed, current_day = args
    prob = ResourceBasedScheduling(
        tasks=_tasks, precedence=_precedence, resources=_resources, N=_N, K_i=_K_i,
        alpha=a, beta=b, T_max=tmax, current_day=current_day, 
        mode="bonus_penalty", c_late=cl, c_early=ce
    )
    sol = solve(prob, pop_size=pop, seed=seed, verbose=False, max_gen=gen, tol=0.005, period=16)
    if sol and isinstance(sol, dict) and "makespan" in sol:
        return {
            "alpha": a, "beta": b, "c_early": ce, "c_late": cl, "T_max": tmax,
            "makespan": sol["makespan"], "total_cost": sol["total_cost"], "net_cost": sol["total_cost"]
        }
    return None

def _worker_eval_mo(args):
    param_name, param_val, pop, gen, seed, current_day = args
    a = param_val if param_name == "alpha" else 0.7
    b = param_val if param_name == "beta" else 0.7
    prob = ResourceBasedScheduling(
        tasks=_tasks, precedence=_precedence, resources=_resources, N=_N, K_i=_K_i,
        alpha=a, beta=b, T_max=344, current_day=current_day, mode="multiobjective"
    )
    sol = solve(prob, pop_size=pop, seed=seed, verbose=False, max_gen=gen, tol=0.002, period=35)
    rows = []
    if sol and sol.F is not None:
        for row in sol.F:
            rows.append({
                param_name: param_val,
                "makespan": row[0],
                "labor_cost": row[1],
                "total_cost": row[1]
            })
    return rows

def run_ga_sensitivity():
    out_dir = os.path.join(base_dir, "../outputs/sensitivity_analysis")
    os.makedirs(out_dir, exist_ok=True)
    
    CURRENT_DAY = 20
    T_MAX_BASE = 250
    POP_SO = 1000
    GEN_SO = 500
    POP_MO = 1000
    GEN_MO = 500
    POP_GRID = 500
    GEN_GRID = 350
    MAX_WORKERS = min(6, os.cpu_count() or 4)
    
    print(f"=== Model A (Resource-Based GA): Running Standardized Sensitivity Suite (Workers={MAX_WORKERS}) ===")
    
    # Helper to run batches with a specific worker evaluation function
    def run_batch(job_args_list, desc, worker_func=_worker_eval_so):
        results = []
        with ProcessPoolExecutor(max_workers=MAX_WORKERS, initializer=_init_worker) as executor:
            futures = {executor.submit(worker_func, args): args for args in job_args_list}
            for fut in tqdm(as_completed(futures), total=len(futures), desc=desc):
                res = fut.result()
                if res:
                    results.append(res)
        return results

    # 1. Single-Objective: OAT Alpha
    print("\n--- 1/9 [Model A] OAT: Crowding Elasticity (alpha) ---")
    if os.path.exists(os.path.join(out_dir, "oat_alpha.csv")) and os.path.exists(os.path.join(out_dir, "oat_alpha.png")):
        print("  [Skip] oat_alpha already completed on disk.")
    else:
        alpha_vals = np.round(np.arange(0.1, 1.05, 0.1), 2)
        jobs = [(a, 0.7, 2000, 5000, T_MAX_BASE, POP_SO, GEN_SO, 42, CURRENT_DAY) for a in alpha_vals]
        res_alpha = run_batch(jobs, "GA OAT alpha", _worker_eval_so)
        df_alpha = pd.DataFrame(res_alpha)
        if not df_alpha.empty and "alpha" in df_alpha.columns:
            df_alpha = df_alpha.sort_values(by="alpha")
        df_alpha.to_csv(os.path.join(out_dir, "oat_alpha.csv"), index=False)
        if not df_alpha.empty:
            plot_dual_axis_oat(
                df_alpha, "alpha", r"Model A (GA): Crowding Elasticity ($\alpha$)", 
                os.path.join(out_dir, "oat_alpha.png"), param_label=r"Crowding Elasticity ($\alpha$)"
            )

    # 2. Single-Objective: OAT Beta
    print("\n--- 2/9 [Model A] OAT: Overtime Efficiency (beta) ---")
    if os.path.exists(os.path.join(out_dir, "oat_beta.csv")) and os.path.exists(os.path.join(out_dir, "oat_beta.png")):
        print("  [Skip] oat_beta already completed on disk.")
    else:
        beta_vals = np.round(np.arange(0.1, 1.05, 0.1), 2)
        jobs = [(0.7, b, 2000, 5000, T_MAX_BASE, POP_SO, GEN_SO, 42, CURRENT_DAY) for b in beta_vals]
        res_beta = run_batch(jobs, "GA OAT beta", _worker_eval_so)
        df_beta = pd.DataFrame(res_beta)
        if not df_beta.empty and "beta" in df_beta.columns:
            df_beta = df_beta.sort_values(by="beta")
        df_beta.to_csv(os.path.join(out_dir, "oat_beta.csv"), index=False)
        if not df_beta.empty:
            plot_dual_axis_oat(
                df_beta, "beta", r"Model A (GA): Overtime Efficiency ($\beta$)", 
                os.path.join(out_dir, "oat_beta.png"), param_label=r"Overtime Efficiency ($\beta$)"
            )

    # 3. Single-Objective: OAT c_early
    print("\n--- 3/9 [Model A] OAT: Early Bonus Rate (c_early) ---")
    if os.path.exists(os.path.join(out_dir, "oat_c_early.csv")) and os.path.exists(os.path.join(out_dir, "oat_c_early.png")):
        print("  [Skip] oat_c_early already completed on disk.")
    else:
        c_early_vals = np.linspace(0, 5000, 11)
        jobs = [(0.7, 0.7, ce, 5000, T_MAX_BASE, POP_SO, GEN_SO, 42, CURRENT_DAY) for ce in c_early_vals]
        res_cearly = run_batch(jobs, "GA OAT c_early", _worker_eval_so)
        df_cearly = pd.DataFrame(res_cearly)
        if not df_cearly.empty and "c_early" in df_cearly.columns:
            df_cearly = df_cearly.sort_values(by="c_early")
        df_cearly.to_csv(os.path.join(out_dir, "oat_c_early.csv"), index=False)
        if not df_cearly.empty:
            plot_dual_axis_oat(
                df_cearly, "c_early", r"Model A (GA): Early Completion Bonus ($c_{early}$)", 
                os.path.join(out_dir, "oat_c_early.png"), param_label=r"Early Bonus ($c_{\mathrm{early}}$)",
                show_ms_label=False, show_cost_label=True
            )

    # 4. Single-Objective: OAT c_late (Includes critical $250 and $750 Cost Ridge evaluation points)
    print("\n--- 4/9 [Model A] OAT: Late Penalty Rate (c_late) ---")
    if os.path.exists(os.path.join(out_dir, "oat_c_late.csv")) and os.path.exists(os.path.join(out_dir, "oat_c_late.png")):
        print("  [Skip] oat_c_late already completed on disk.")
    else:
        c_late_vals = sorted(list(np.linspace(0, 5000, 11)) + [250.0, 750.0])
        jobs = [(0.7, 0.7, 2000, cl, T_MAX_BASE, POP_SO, GEN_SO, 42, CURRENT_DAY) for cl in c_late_vals]
        res_clate = run_batch(jobs, "GA OAT c_late", _worker_eval_so)
        df_clate = pd.DataFrame(res_clate)
        if not df_clate.empty and "c_late" in df_clate.columns:
            df_clate = df_clate.sort_values(by="c_late")
        df_clate.to_csv(os.path.join(out_dir, "oat_c_late.csv"), index=False)
        if not df_clate.empty:
            plot_dual_axis_oat(
                df_clate, "c_late", r"Model A (GA): Late Completion Penalty ($c_{late}$)", 
                os.path.join(out_dir, "oat_c_late.png"), param_label=r"Late Penalty ($c_{\mathrm{late}}$)",
                show_ms_label=True, show_cost_label=False
            )

    # 5. Single-Objective: OAT T_max
    print("\n--- 5/9 [Model A] OAT: Contractual Deadline (T_max) ---")
    if os.path.exists(os.path.join(out_dir, "oat_T_max.csv")) and os.path.exists(os.path.join(out_dir, "oat_T_max.png")):
        print("  [Skip] oat_T_max already completed on disk.")
    else:
        tmax_vals = np.arange(210, 311, 6)
        jobs = [(0.7, 0.7, 2000, 5000, int(t), POP_SO, GEN_SO, 42, CURRENT_DAY) for t in tmax_vals]
        res_tmax = run_batch(jobs, "GA OAT T_max", _worker_eval_so)
        df_tmax = pd.DataFrame(res_tmax)
        if not df_tmax.empty and "T_max" in df_tmax.columns:
            df_tmax = df_tmax.sort_values(by="T_max")
        df_tmax.to_csv(os.path.join(out_dir, "oat_T_max.csv"), index=False)
        if not df_tmax.empty:
            plot_dual_axis_oat(
                df_tmax, "T_max", r"Model A (GA): Contractual Deadline ($T_{max}$)", 
                os.path.join(out_dir, "oat_T_max.png"), param_label=r"Target Deadline ($T_{\max}$)"
            )

    # 6. Multi-Objective: Pareto Shift Alpha (0.3, 0.6, 0.9)
    print("\n--- 6/9 [Model A] Multi-Objective: Pareto Shift Alpha ---")
    if os.path.exists(os.path.join(out_dir, "pareto_shift_alpha.csv")) and os.path.exists(os.path.join(out_dir, "pareto_shift_alpha.png")):
        print("  [Skip] pareto_shift_alpha already completed on disk.")
    else:
        pareto_a = []
        mo_jobs_a = [("alpha", a, POP_MO, GEN_MO, 42, CURRENT_DAY) for a in [0.3, 0.6, 0.9]]
        with ProcessPoolExecutor(max_workers=MAX_WORKERS, initializer=_init_worker) as executor:
            futures = {executor.submit(_worker_eval_mo, args): args for args in mo_jobs_a}
            for fut in tqdm(as_completed(futures), total=len(futures), desc="GA Pareto Alpha"):
                rows = fut.result()
                if rows:
                    pareto_a.extend(rows)
        df_pareto_a = pd.DataFrame(pareto_a)
        df_pareto_a.to_csv(os.path.join(out_dir, "pareto_shift_alpha.csv"), index=False)
        if not df_pareto_a.empty:
            plot_pareto_shifts(
                df_pareto_a, "alpha", r"Model A (GA): Pareto Front Shift by Crowding ($\alpha$)", 
                os.path.join(out_dir, "pareto_shift_alpha.png"), param_label=r"$\alpha$",
                ylim_shared=(0.505, 0.615), show_ylabel=True
            )

    # 7. Multi-Objective: Pareto Shift Beta (0.3, 0.6, 0.9)
    print("\n--- 7/9 [Model A] Multi-Objective: Pareto Shift Beta ---")
    if os.path.exists(os.path.join(out_dir, "pareto_shift_beta.csv")) and os.path.exists(os.path.join(out_dir, "pareto_shift_beta.png")):
        print("  [Skip] pareto_shift_beta already completed on disk.")
    else:
        pareto_b = []
        mo_jobs_b = [("beta", b, POP_MO, GEN_MO, 42, CURRENT_DAY) for b in [0.3, 0.6, 0.9]]
        with ProcessPoolExecutor(max_workers=MAX_WORKERS, initializer=_init_worker) as executor:
            futures = {executor.submit(_worker_eval_mo, args): args for args in mo_jobs_b}
            for fut in tqdm(as_completed(futures), total=len(futures), desc="GA Pareto Beta"):
                rows = fut.result()
                if rows:
                    pareto_b.extend(rows)
        df_pareto_b = pd.DataFrame(pareto_b)
        df_pareto_b.to_csv(os.path.join(out_dir, "pareto_shift_beta.csv"), index=False)
        if not df_pareto_b.empty:
            plot_pareto_shifts(
                df_pareto_b, "beta", r"Model A (GA): Pareto Front Shift by Overtime ($\beta$)", 
                os.path.join(out_dir, "pareto_shift_beta.png"), param_label=r"$\beta$",
                ylim_shared=(0.505, 0.615), show_ylabel=False
            )

    # 8. Two-At-a-Time: Alpha x Beta Grid Sweep (2-Panel Heatmap)
    print("\n--- 8/9 [Model A] TAT: Alpha x Beta Grid Sweep ---")
    if os.path.exists(os.path.join(out_dir, "tat_alpha_beta.csv")) and os.path.exists(os.path.join(out_dir, "tat_alpha_beta_2panel.png")):
        print("  [Skip] tat_alpha_beta already completed on disk.")
    else:
        alpha_vals = np.round(np.arange(0.1, 1.05, 0.1), 2)
        beta_vals = np.round(np.arange(0.1, 1.05, 0.1), 2)
        jobs = [(a, b, 2000, 5000, T_MAX_BASE, POP_GRID, GEN_GRID, 42, CURRENT_DAY) for a in alpha_vals for b in beta_vals]
        res_grid_ab = run_batch(jobs, "GA Grid alpha×beta", _worker_eval_grid)
        df_grid_ab = pd.DataFrame(res_grid_ab)
        df_grid_ab.to_csv(os.path.join(out_dir, "tat_alpha_beta.csv"), index=False)
        if not df_grid_ab.empty:
            plot_2panel_contour_heatmap(
                df_grid_ab, "alpha", "beta", os.path.join(out_dir, "tat_alpha_beta_2panel.png"),
                title_prefix="Model A (GA): ", x_label=r"Overcrowding Elasticity ($\alpha$)", 
                y_label=r"Overtime Elasticity ($\beta$)", is_bonus_penalty=False
            )

    # 9. Two-At-a-Time: c_late x c_early Grid Sweep (2-Panel Heatmap)
    print("\n--- 9/9 [Model A] TAT: c_late x c_early Grid Sweep ---")
    if os.path.exists(os.path.join(out_dir, "tat_c_early_c_late.csv")) and os.path.exists(os.path.join(out_dir, "tat_c_early_c_late_2panel.png")):
        print("  [Skip] tat_c_early_c_late already completed on disk.")
    else:
        c_early_vals = np.linspace(0, 5000, 11)
        c_late_vals = np.linspace(0, 5000, 11)
        jobs = [(0.7, 0.7, ce, cl, T_MAX_BASE, POP_GRID, GEN_GRID, 42, CURRENT_DAY) for cl in c_late_vals for ce in c_early_vals]
        res_grid_ce = run_batch(jobs, "GA Grid c_late×c_early", _worker_eval_grid)
        df_grid_ce = pd.DataFrame(res_grid_ce)
        df_grid_ce.to_csv(os.path.join(out_dir, "tat_c_early_c_late.csv"), index=False)
        if not df_grid_ce.empty:
            plot_2panel_contour_heatmap(
                df_grid_ce, "c_early", "c_late", os.path.join(out_dir, "tat_c_early_c_late_2panel.png"),
                title_prefix="Model A (GA): ", x_label=r"Early Bonus ($c_{\mathrm{early}}$)", 
                y_label=r"Late Penalty ($c_{\mathrm{late}}$)", is_bonus_penalty=True
            )

    print("\n=== Model A (GA) Standardized Sensitivity Complete ===")

if __name__ == "__main__":
    run_ga_sensitivity()
