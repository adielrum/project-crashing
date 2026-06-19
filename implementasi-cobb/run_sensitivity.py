import os
import pandas as pd
import numpy as np
from cobb_model import load_data, data_path, ResourceBasedScheduling, solve
from solver_milp import solve_milp_cobb_douglas

def run_sensitivity():
    base_dir = os.path.dirname(os.path.abspath(__file__))
    out_dir = os.path.join(base_dir, "../outputs/sensitivity_analysis")
    os.makedirs(out_dir, exist_ok=True)

    tasks, precedence, resources, N, K_i = load_data(
        path_tasks=data_path("data_tasks.csv"),
        path_precedence=data_path("data_precedence.csv"),
        path_assignments=data_path("data_assignments.csv"),
    )

    CURRENT_DAY = 0
    POP_SIZE = 800
    MAX_GEN = 1000
    T_MAX_BASE = 310
    MILP_TIME_LIMIT = 5.0 # fast for testing

    print(f"=== Starting Extensive Sensitivity Analysis ===")
    print(f"Test specs: GA POP={POP_SIZE}, GEN={MAX_GEN} | MILP TimeLimit={MILP_TIME_LIMIT}s\n")

    # 1. OAT: alpha (0.3 to 0.9) - MILP
    print("--- 1/11 OAT: alpha (MILP) ---")
    alpha_vals = np.round(np.arange(0.3, 1.0, 0.1), 2)
    res_alpha = []
    for a in alpha_vals:
        sol = solve_milp_cobb_douglas(
            tasks, precedence, resources, N, K_i,
            alpha=a, beta=0.7, T_max=T_MAX_BASE, current_day=CURRENT_DAY, 
            mode="bonus_penalty", time_limit=MILP_TIME_LIMIT
        )
        if sol:
            res_alpha.append({"alpha": a, "makespan": sol["makespan"], "total_cost": sol["total_cost"]})
    pd.DataFrame(res_alpha).to_csv(os.path.join(out_dir, "oat_alpha.csv"), index=False)

    # 2. OAT: beta (0.3 to 0.9) - MILP
    print("--- 2/11 OAT: beta (MILP) ---")
    beta_vals = np.round(np.arange(0.3, 1.0, 0.1), 2)
    res_beta = []
    for b in beta_vals:
        sol = solve_milp_cobb_douglas(
            tasks, precedence, resources, N, K_i,
            alpha=0.7, beta=b, T_max=T_MAX_BASE, current_day=CURRENT_DAY, 
            mode="bonus_penalty", time_limit=MILP_TIME_LIMIT
        )
        if sol:
            res_beta.append({"beta": b, "makespan": sol["makespan"], "total_cost": sol["total_cost"]})
    pd.DataFrame(res_beta).to_csv(os.path.join(out_dir, "oat_beta.csv"), index=False)

    # 3. Grid: alpha x beta - MILP
    print("--- 3/11 Grid: alpha x beta (MILP) ---")
    res_grid_ab = []
    for a in alpha_vals:
        for b in beta_vals:
            sol = solve_milp_cobb_douglas(
                tasks, precedence, resources, N, K_i,
                alpha=a, beta=b, T_max=T_MAX_BASE, current_day=CURRENT_DAY, 
                mode="bonus_penalty", time_limit=MILP_TIME_LIMIT
            )
            if sol:
                res_grid_ab.append({"alpha": a, "beta": b, "makespan": sol["makespan"], "total_cost": sol["total_cost"]})
    pd.DataFrame(res_grid_ab).to_csv(os.path.join(out_dir, "grid_alpha_beta.csv"), index=False)

    # 4. OAT: c_late (10 variations) - MILP
    print("--- 4/11 OAT: c_late (MILP) ---")
    c_late_vals = np.linspace(1000, 10000, 10)
    res_clate = []
    for c in c_late_vals:
        sol = solve_milp_cobb_douglas(
            tasks, precedence, resources, N, K_i,
            alpha=0.7, beta=0.7, T_max=T_MAX_BASE, current_day=CURRENT_DAY, 
            mode="bonus_penalty", c_late=c, c_early=2000, time_limit=MILP_TIME_LIMIT
        )
        if sol:
            res_clate.append({"c_late": c, "makespan": sol["makespan"], "total_cost": sol["total_cost"]})
    pd.DataFrame(res_clate).to_csv(os.path.join(out_dir, "oat_c_late.csv"), index=False)

    # 5. OAT: c_early (10 variations) - MILP
    print("--- 5/11 OAT: c_early (MILP) ---")
    c_early_vals = np.linspace(0, 4500, 10)
    res_cearly = []
    for ce in c_early_vals:
        sol = solve_milp_cobb_douglas(
            tasks, precedence, resources, N, K_i,
            alpha=0.7, beta=0.7, T_max=T_MAX_BASE, current_day=CURRENT_DAY, 
            mode="bonus_penalty", c_late=5000, c_early=ce, time_limit=MILP_TIME_LIMIT
        )
        if sol:
            res_cearly.append({"c_early": ce, "makespan": sol["makespan"], "total_cost": sol["total_cost"]})
    pd.DataFrame(res_cearly).to_csv(os.path.join(out_dir, "oat_c_early.csv"), index=False)

    # 6. Grid: c_late x c_early - MILP
    print("--- 6/11 Grid: c_late x c_early (MILP) ---")
    res_grid_ce = []
    for cl in c_late_vals:
        for ce in c_early_vals:
            sol = solve_milp_cobb_douglas(
                tasks, precedence, resources, N, K_i,
                alpha=0.7, beta=0.7, T_max=T_MAX_BASE, current_day=CURRENT_DAY, 
                mode="bonus_penalty", c_late=cl, c_early=ce, time_limit=MILP_TIME_LIMIT
            )
            if sol:
                res_grid_ce.append({"c_late": cl, "c_early": ce, "makespan": sol["makespan"], "total_cost": sol["total_cost"]})
    pd.DataFrame(res_grid_ce).to_csv(os.path.join(out_dir, "grid_clate_cearly.csv"), index=False)

    # 7. OAT: T_max (more variations) - MILP
    print("--- 7/11 OAT: T_max (MILP) ---")
    tmax_vals = np.arange(290, 345, 4)  # ~14 variations
    res_tmax = []
    for t in tmax_vals:
        sol = solve_milp_cobb_douglas(
            tasks, precedence, resources, N, K_i,
            alpha=0.7, beta=0.7, T_max=int(t), current_day=CURRENT_DAY, 
            mode="bonus_penalty", time_limit=MILP_TIME_LIMIT
        )
        if sol:
            res_tmax.append({"T_max": t, "makespan": sol["makespan"], "total_cost": sol["total_cost"]})
    pd.DataFrame(res_tmax).to_csv(os.path.join(out_dir, "oat_T_max.csv"), index=False)

    # 8. Pareto Shift: alpha (0.3, 0.6, 0.9) - GA
    print("--- 8/11 Pareto Shift: alpha (GA) ---")
    pareto_a = []
    for a in [0.3, 0.6, 0.9]:
        prob = ResourceBasedScheduling(
            tasks=tasks, precedence=precedence, resources=resources, N=N, K_i=K_i,
            alpha=a, beta=0.7, T_max=344, current_day=CURRENT_DAY, mode="multiobjective"
        )
        sol = solve(prob, pop_size=POP_SIZE, seed=42, verbose=False, max_gen=MAX_GEN)
        if sol and sol.F is not None:
            for row in sol.F:
                pareto_a.append({"alpha": a, "makespan": row[0], "labor_cost": row[1]})
    pd.DataFrame(pareto_a).to_csv(os.path.join(out_dir, "pareto_alpha.csv"), index=False)

    # 9. Pareto Shift: beta (0.3, 0.6, 0.9) - GA
    print("--- 9/11 Pareto Shift: beta (GA) ---")
    pareto_b = []
    for b in [0.3, 0.6, 0.9]:
        prob = ResourceBasedScheduling(
            tasks=tasks, precedence=precedence, resources=resources, N=N, K_i=K_i,
            alpha=0.7, beta=b, T_max=344, current_day=CURRENT_DAY, mode="multiobjective"
        )
        sol = solve(prob, pop_size=POP_SIZE, seed=42, verbose=False, max_gen=MAX_GEN)
        if sol and sol.F is not None:
            for row in sol.F:
                pareto_b.append({"beta": b, "makespan": row[0], "labor_cost": row[1]})
    pd.DataFrame(pareto_b).to_csv(os.path.join(out_dir, "pareto_beta.csv"), index=False)
    
    # 10. Pareto Shift: c_early and c_late - GA
    print("--- 10/11 Pareto Shift: Base Run for Cost Parameters (GA) ---")
    prob_base = ResourceBasedScheduling(
        tasks=tasks, precedence=precedence, resources=resources, N=N, K_i=K_i,
        alpha=0.7, beta=0.7, T_max=310, current_day=CURRENT_DAY, mode="multiobjective"
    )
    sol_base = solve(prob_base, pop_size=POP_SIZE, seed=42, verbose=False, max_gen=MAX_GEN)
    if sol_base and sol_base.F is not None:
        base_front = sol_base.F
        
        # c_late variations
        print("--- 10/11 Pareto Shift: c_late ---")
        pareto_cl = []
        for cl in [2000, 5000, 8000]:
            for row in base_front:
                mkspan = row[0]
                lab_cost = row[1]
                tot_cost = lab_cost + cl * max(0, mkspan - 310) - 2000 * max(0, 310 - mkspan)
                pareto_cl.append({"c_late": cl, "makespan": mkspan, "total_cost": tot_cost})
        pd.DataFrame(pareto_cl).to_csv(os.path.join(out_dir, "pareto_c_late.csv"), index=False)
        
        # c_early variations
        print("--- 11/11 Pareto Shift: c_early ---")
        pareto_ce = []
        for ce in [0, 2000, 4000]:
            for row in base_front:
                mkspan = row[0]
                lab_cost = row[1]
                tot_cost = lab_cost + 5000 * max(0, mkspan - 310) - ce * max(0, 310 - mkspan)
                pareto_ce.append({"c_early": ce, "makespan": mkspan, "total_cost": tot_cost})
        pd.DataFrame(pareto_ce).to_csv(os.path.join(out_dir, "pareto_c_early.csv"), index=False)

    print("\n=== Sensitivity Analysis Complete ===")

if __name__ == "__main__":
    run_sensitivity()
