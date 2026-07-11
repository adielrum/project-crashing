import os
import sys
import copy
import numpy as np
import pandas as pd
from tqdm import tqdm

base_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.append(os.path.join(base_dir, "../comparison"))
from sensitivity_utils import plot_dual_axis_oat, plot_2panel_contour_heatmap, plot_pareto_shifts
from solver_base import (
    read_json, build_predecessors, infer_activity_states_without_state_file,
    build_model_and_solve, SolveConfig
)

def adjust_activity_data_for_cobb_douglas(activity_data, alpha, beta):
    """
    Recalculates linear activity_min_time and crash_cost for Model C based on
    Cobb-Douglas parameters (alpha, beta) under max resource allocation.
    """
    new_data = copy.deepcopy(activity_data)
    w_base = 200.0  # daily wage per worker
    w_ot = 37.5     # hourly overtime wage per worker
    
    for act, s in new_data.items():
        d0 = s.get("activity_normal_time", s.get("normal_duration", 1))
        if d0 <= 1:
            continue
            
        x_max = 2.0  # up to 2x normal crew
        tau_max = 4.0 # up to 4h overtime
        
        # New minimum duration under Cobb-Douglas
        d_min = max(1, int(np.ceil(d0 * (x_max ** (-alpha)) * (((8.0 + tau_max)/8.0) ** (-beta)))))
        d_min = min(d_min, d0)
        
        c_norm = d0 * w_base
        c_crash = d_min * (x_max * w_base + x_max * tau_max * w_ot)
        
        s["activity_min_time"] = d_min
        if d0 > d_min:
            s["crash_cost"] = round(float(max(1.0, (c_crash - c_norm) / (d0 - d_min))), 2)
        else:
            s["crash_cost"] = 0.0
        s["normal_cost"] = round(float(c_norm), 2)
        
    return new_data

def solve_linear_wrapper(activity_data, resource_requirements, resource_capacity, predecessors,
                         mode, target_end_date=None, c_late=0.0, c_early=0.0, time_limit=10.0):
    cfg = SolveConfig(
        target_end_date=target_end_date,
        current_day=0,
        time_limit=time_limit,
        num_workers=4,
        auto_fix_paint_trim_cycle=True,
        remove_edges=[],
        budget_limit=None,
        c_late=c_late,
        c_early=c_early
    )
    
    states, _ = infer_activity_states_without_state_file(
        activity_data=activity_data,
        resource_requirements=resource_requirements,
        resource_capacity=resource_capacity,
        predecessors=predecessors,
        current_day=cfg.current_day,
        time_limit=cfg.time_limit,
        num_workers=cfg.num_workers
    )
    
    sol = build_model_and_solve(
        activity_data=activity_data,
        resource_requirements=resource_requirements,
        resource_capacity=resource_capacity,
        predecessors=predecessors,
        states=states,
        cfg=cfg,
        mode=mode
    )
    
    if sol and sol.get("status") in ["OPTIMAL", "FEASIBLE"]:
        ms = sol["makespan"]
        crash_cost = sol.get("total_crash_cost", 0.0)
        if mode == "bonus_penalty" and target_end_date is not None:
            late_days = max(0, ms - target_end_date)
            early_days = max(0, target_end_date - ms)
            net_c = crash_cost + late_days * c_late - early_days * c_early
        else:
            net_c = crash_cost
        sol["net_cost"] = net_c
        return sol
    return None

def run_linear_sensitivity():
    out_dir = os.path.join(base_dir, "../outputs/sensitivity_analysis/model_C_linear")
    os.makedirs(out_dir, exist_ok=True)
    
    activity_data_base = read_json(os.path.join(base_dir, "../data/activity_data_v3.json"))
    resource_capacity = read_json(os.path.join(base_dir, "../data/resource_capacity_v3.json"))
    resource_requirements = read_json(os.path.join(base_dir, "../data/resource_requirements_v3.json"))
    
    predecessors, _ = build_predecessors(activity_data=activity_data_base, remove_edges=[], auto_fix_paint_trim_cycle=True)
    
    CURRENT_DAY = 20
    T_MAX_BASE = 250
    TIME_LIMIT = 10.0
    
    print("=== Model C (Time-Based Linear CP-SAT): Running Standardized Sensitivity Suite ===")
    
    # Precompute adjusted data for standard alpha=0.7, beta=0.7 runs
    data_adj_std = adjust_activity_data_for_cobb_douglas(activity_data_base, alpha=0.7, beta=0.7)
    
    # 1. Single-Objective: OAT Alpha
    print("\n--- 1/9 [Model C] OAT: Crowding Elasticity (alpha) ---")
    alpha_vals = np.round(np.arange(0.1, 1.05, 0.1), 2)
    res_alpha = []
    for a in tqdm(alpha_vals, desc="Linear OAT alpha"):
        data_adj = adjust_activity_data_for_cobb_douglas(activity_data_base, alpha=a, beta=0.7)
        sol = solve_linear_wrapper(data_adj, resource_requirements, resource_capacity, predecessors, 
                                   mode="bonus_penalty", target_end_date=T_MAX_BASE, c_late=5000, c_early=2000, time_limit=TIME_LIMIT)
        if sol:
            res_alpha.append({"alpha": a, "makespan": sol["makespan"], "total_cost": sol["net_cost"], "net_cost": sol["net_cost"]})
    df_alpha = pd.DataFrame(res_alpha)
    df_alpha.to_csv(os.path.join(out_dir, "oat_alpha.csv"), index=False)
    if not df_alpha.empty:
        plot_dual_axis_oat(
            df_alpha, "alpha", r"Model C (Linear): Crowding Elasticity ($\alpha$)", 
            os.path.join(out_dir, "oat_alpha.png"), param_label=r"Crowding Elasticity ($\alpha$)"
        )

    # 2. Single-Objective: OAT Beta
    print("\n--- 2/9 [Model C] OAT: Overtime Efficiency (beta) ---")
    beta_vals = np.round(np.arange(0.1, 1.05, 0.1), 2)
    res_beta = []
    for b in tqdm(beta_vals, desc="Linear OAT beta"):
        data_adj = adjust_activity_data_for_cobb_douglas(activity_data_base, alpha=0.7, beta=b)
        sol = solve_linear_wrapper(data_adj, resource_requirements, resource_capacity, predecessors, 
                                   mode="bonus_penalty", target_end_date=T_MAX_BASE, c_late=5000, c_early=2000, time_limit=TIME_LIMIT)
        if sol:
            res_beta.append({"beta": b, "makespan": sol["makespan"], "total_cost": sol["net_cost"], "net_cost": sol["net_cost"]})
    df_beta = pd.DataFrame(res_beta)
    df_beta.to_csv(os.path.join(out_dir, "oat_beta.csv"), index=False)
    if not df_beta.empty:
        plot_dual_axis_oat(
            df_beta, "beta", r"Model C (Linear): Overtime Efficiency ($\beta$)", 
            os.path.join(out_dir, "oat_beta.png"), param_label=r"Overtime Efficiency ($\beta$)"
        )

    # 3. Single-Objective: TAT Alpha x Beta (2-Panel Heatmap)
    print("\n--- 3/9 [Model C] TAT: Alpha x Beta Grid Sweep ---")
    res_grid_ab = []
    for a in tqdm(alpha_vals, desc="Linear Grid alpha×beta"):
        for b in beta_vals:
            data_adj = adjust_activity_data_for_cobb_douglas(activity_data_base, alpha=a, beta=b)
            sol = solve_linear_wrapper(data_adj, resource_requirements, resource_capacity, predecessors, 
                                       mode="bonus_penalty", target_end_date=T_MAX_BASE, c_late=5000, c_early=2000, time_limit=TIME_LIMIT)
            if sol:
                res_grid_ab.append({"alpha": a, "beta": b, "makespan": sol["makespan"], "total_cost": sol["net_cost"], "net_cost": sol["net_cost"]})
    df_grid_ab = pd.DataFrame(res_grid_ab)
    df_grid_ab.to_csv(os.path.join(out_dir, "tat_alpha_beta.csv"), index=False)
    if not df_grid_ab.empty:
        plot_2panel_contour_heatmap(
            df_grid_ab, "alpha", "beta", os.path.join(out_dir, "tat_alpha_beta_2panel.png"),
            title_prefix="Model C (Linear): ", x_label=r"Crowding Elasticity ($\alpha$)", 
            y_label=r"Overtime Efficiency ($\beta$)", is_bonus_penalty=False
        )

    # 4. Single-Objective: OAT c_early
    print("\n--- 4/9 [Model C] OAT: Early Bonus Rate (c_early) ---")
    c_early_vals = np.linspace(0, 5000, 11)
    res_cearly = []
    for ce in tqdm(c_early_vals, desc="Linear OAT c_early"):
        data_adj = adjust_activity_data_for_cobb_douglas(activity_data_base, alpha=0.7, beta=0.7)
        sol = solve_linear_wrapper(data_adj, resource_requirements, resource_capacity, predecessors,
                                   mode="bonus_penalty", target_end_date=T_MAX_BASE, c_late=5000, c_early=ce, time_limit=TIME_LIMIT)
        if sol:
            res_cearly.append({"c_early": ce, "makespan": sol["makespan"], "total_cost": sol["net_cost"], "net_cost": sol["net_cost"]})
    df_cearly = pd.DataFrame(res_cearly)
    df_cearly.to_csv(os.path.join(out_dir, "oat_c_early.csv"), index=False)
    if not df_cearly.empty:
        plot_dual_axis_oat(
            df_cearly, "c_early", r"Model C (Linear): Early Completion Bonus ($c_{early}$)", 
            os.path.join(out_dir, "oat_c_early.png"), param_label=r"Early Bonus ($c_{early}$ in $/day)"
        )

    # 5. Single-Objective: OAT c_late
    print("\n--- 5/9 [Model C] OAT: Late Penalty Rate (c_late) ---")
    c_late_vals = np.linspace(0, 5000, 11)
    res_clate = []
    for cl in tqdm(c_late_vals, desc="Linear OAT c_late"):
        data_adj = adjust_activity_data_for_cobb_douglas(activity_data_base, alpha=0.7, beta=0.7)
        sol = solve_linear_wrapper(data_adj, resource_requirements, resource_capacity, predecessors,
                                   mode="bonus_penalty", target_end_date=T_MAX_BASE, c_late=cl, c_early=2000, time_limit=TIME_LIMIT)
        if sol:
            res_clate.append({"c_late": cl, "makespan": sol["makespan"], "total_cost": sol["net_cost"], "net_cost": sol["net_cost"]})
    df_clate = pd.DataFrame(res_clate)
    df_clate.to_csv(os.path.join(out_dir, "oat_c_late.csv"), index=False)
    if not df_clate.empty:
        plot_dual_axis_oat(
            df_clate, "c_late", r"Model C (Linear): Late Completion Penalty ($c_{late}$)", 
            os.path.join(out_dir, "oat_c_late.png"), param_label=r"Late Penalty ($c_{late}$ in $/day)"
        )

    # 6. Single-Objective: TAT c_late x c_early (2-Panel Heatmap)
    print("\n--- 6/9 [Model C] TAT: c_late x c_early Grid Sweep ---")
    res_grid_ce = []
    for cl in tqdm(c_late_vals, desc="Linear Grid c_late×c_early"):
        for ce in c_early_vals:
            data_adj = adjust_activity_data_for_cobb_douglas(activity_data_base, alpha=0.7, beta=0.7)
            sol = solve_linear_wrapper(data_adj, resource_requirements, resource_capacity, predecessors,
                                       mode="bonus_penalty", target_end_date=T_MAX_BASE, c_late=cl, c_early=ce, time_limit=TIME_LIMIT)
            if sol:
                res_grid_ce.append({"c_late": cl, "c_early": ce, "makespan": sol["makespan"], "total_cost": sol["net_cost"], "net_cost": sol["net_cost"]})
    df_grid_ce = pd.DataFrame(res_grid_ce)
    df_grid_ce.to_csv(os.path.join(out_dir, "tat_c_early_c_late.csv"), index=False)
    if not df_grid_ce.empty:
        plot_2panel_contour_heatmap(
            df_grid_ce, "c_early", "c_late", os.path.join(out_dir, "tat_c_early_c_late_2panel.png"),
            title_prefix="Model C (Linear): ", x_label=r"Early Bonus ($c_{early}$ $/day)", 
            y_label=r"Late Penalty ($c_{late}$ $/day)", is_bonus_penalty=True
        )

    # 7. Single-Objective: OAT T_max
    print("\n--- 7/9 [Model C] OAT: Contractual Deadline (T_max) ---")
    tmax_vals = np.arange(210, 311, 6)
    res_tmax = []
    for t in tqdm(tmax_vals, desc="Linear OAT T_max"):
        data_adj = adjust_activity_data_for_cobb_douglas(activity_data_base, alpha=0.7, beta=0.7)
        sol = solve_linear_wrapper(data_adj, resource_requirements, resource_capacity, predecessors,
                                   mode="bonus_penalty", target_end_date=int(t), c_late=5000, c_early=2000, time_limit=TIME_LIMIT)
        if sol:
            res_tmax.append({"T_max": t, "makespan": sol["makespan"], "total_cost": sol["net_cost"], "net_cost": sol["net_cost"]})
    df_tmax = pd.DataFrame(res_tmax)
    df_tmax.to_csv(os.path.join(out_dir, "oat_T_max.csv"), index=False)
    if not df_tmax.empty:
        plot_dual_axis_oat(
            df_tmax, "T_max", r"Model C (Linear): Contractual Deadline ($T_{max}$)", 
            os.path.join(out_dir, "oat_T_max.png"), param_label=r"Target Deadline ($T_{max}$ in Days)"
        )

    # 8. Multi-Objective: Pareto Shift Alpha (0.3, 0.6, 0.9)
    print("\n--- 8/9 [Model C] Multi-Objective: Pareto Shift Alpha ---")
    pareto_a = []
    pareto_deadlines = np.arange(216, 311, 8)
    for a in tqdm([0.3, 0.6, 0.9], desc="Linear Pareto Alpha"):
        data_adj = adjust_activity_data_for_cobb_douglas(activity_data_base, alpha=a, beta=0.7)
        for t in pareto_deadlines:
            sol = solve_linear_wrapper(data_adj, resource_requirements, resource_capacity, predecessors,
                                       mode="cost_with_deadline", target_end_date=int(t), time_limit=TIME_LIMIT)
            if sol:
                pareto_a.append({"alpha": a, "makespan": sol["makespan"], "labor_cost": sol["total_crash_cost"], "total_cost": sol["total_crash_cost"]})
    df_pareto_a = pd.DataFrame(pareto_a)
    df_pareto_a.to_csv(os.path.join(out_dir, "pareto_shift_alpha.csv"), index=False)
    if not df_pareto_a.empty:
        plot_pareto_shifts(
            df_pareto_a, "alpha", r"Model C (Linear): Pareto Front Shift by Crowding ($\alpha$)", 
            os.path.join(out_dir, "pareto_shift_alpha.png"), param_label=r"$\alpha$"
        )

    # 9. Multi-Objective: Pareto Shift Beta (0.3, 0.6, 0.9)
    print("\n--- 9/9 [Model C] Multi-Objective: Pareto Shift Beta ---")
    pareto_b = []
    for b in tqdm([0.3, 0.6, 0.9], desc="Linear Pareto Beta"):
        data_adj = adjust_activity_data_for_cobb_douglas(activity_data_base, alpha=0.7, beta=b)
        for t in pareto_deadlines:
            sol = solve_linear_wrapper(data_adj, resource_requirements, resource_capacity, predecessors,
                                       mode="cost_with_deadline", target_end_date=int(t), time_limit=TIME_LIMIT)
            if sol:
                pareto_b.append({"beta": b, "makespan": sol["makespan"], "labor_cost": sol["total_crash_cost"], "total_cost": sol["total_crash_cost"]})
    df_pareto_b = pd.DataFrame(pareto_b)
    df_pareto_b.to_csv(os.path.join(out_dir, "pareto_shift_beta.csv"), index=False)
    if not df_pareto_b.empty:
        plot_pareto_shifts(
            df_pareto_b, "beta", r"Model C (Linear): Pareto Front Shift by Overtime ($\beta$)", 
            os.path.join(out_dir, "pareto_shift_beta.png"), param_label=r"$\beta$"
        )

    print("\n=== Model C (Linear) Standardized Sensitivity Complete ===")

if __name__ == "__main__":
    run_linear_sensitivity()
