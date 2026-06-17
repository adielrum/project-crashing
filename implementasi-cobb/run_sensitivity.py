import os
import pandas as pd
import numpy as np
from cobb_model import load_data, data_path, ResourceBasedScheduling, solve

def run_sensitivity():
    # Setup paths
    base_dir = os.path.dirname(os.path.abspath(__file__))
    out_dir = os.path.join(base_dir, "../outputs/sensitivity_analysis")
    os.makedirs(out_dir, exist_ok=True)

    # Load data
    tasks, precedence, resources, N, K_i = load_data(
        path_tasks=data_path("data_tasks.csv"),
        path_precedence=data_path("data_precedence.csv"),
        path_assignments=data_path("data_assignments.csv"),
    )

    CURRENT_DAY = 0
    POP_SIZE = 200
    MAX_GEN = 100

    print("=== Starting Sensitivity Analysis ===")

    # ---------------------------------------------------------
    # 1. OAT: alpha (Crowding Elasticity)
    # Mode: cost_with_deadline, T_max = 310
    # ---------------------------------------------------------
    print("\n--- OAT: alpha ---")
    alpha_values = [0.5, 0.6, 0.7, 0.8, 0.9]
    res_alpha = []
    for a in alpha_values:
        print(f"Running alpha = {a}...")
        prob = ResourceBasedScheduling(
            tasks=tasks, precedence=precedence, resources=resources, N=N, K_i=K_i,
            alpha=a, beta=0.7, T_max=310, current_day=CURRENT_DAY,
            mode="cost_with_deadline"
        )
        sol = solve(prob, pop_size=POP_SIZE, seed=42, verbose=False, max_gen=MAX_GEN)
        if sol is not None:
            res_alpha.append({"alpha": a, "makespan": sol["makespan"], "labor_cost": sol["labor_cost"], "total_cost": sol["total_cost"]})

    df_alpha = pd.DataFrame(res_alpha)
    df_alpha.to_csv(os.path.join(out_dir, "oat_alpha.csv"), index=False)
    print("Saved oat_alpha.csv")

    # ---------------------------------------------------------
    # 2. OAT: c_late (Penalty Rate)
    # Mode: bonus_penalty, T_max = 310, c_early = 2000
    # ---------------------------------------------------------
    print("\n--- OAT: c_late ---")
    c_late_values = [2000.0, 3500.0, 5000.0, 6500.0, 8000.0]
    res_clate = []
    for c in c_late_values:
        print(f"Running c_late = {c}...")
        prob = ResourceBasedScheduling(
            tasks=tasks, precedence=precedence, resources=resources, N=N, K_i=K_i,
            alpha=0.7, beta=0.7, T_max=310, current_day=CURRENT_DAY,
            mode="bonus_penalty", c_late=c, c_early=2000.0
        )
        sol = solve(prob, pop_size=POP_SIZE, seed=42, verbose=False, max_gen=MAX_GEN)
        if sol is not None:
            res_clate.append({"c_late": c, "makespan": sol["makespan"], "labor_cost": sol["labor_cost"], "total_cost": sol["total_cost"]})

    df_clate = pd.DataFrame(res_clate)
    df_clate.to_csv(os.path.join(out_dir, "oat_c_late.csv"), index=False)
    print("Saved oat_c_late.csv")

    # ---------------------------------------------------------
    # 3. OAT: T_max (Target Deadline)
    # Mode: cost_with_deadline
    # ---------------------------------------------------------
    print("\n--- OAT: T_max ---")
    tmax_values = [300, 310, 320, 330, 344]
    res_tmax = []
    for t in tmax_values:
        print(f"Running T_max = {t}...")
        prob = ResourceBasedScheduling(
            tasks=tasks, precedence=precedence, resources=resources, N=N, K_i=K_i,
            alpha=0.7, beta=0.7, T_max=t, current_day=CURRENT_DAY,
            mode="cost_with_deadline"
        )
        sol = solve(prob, pop_size=POP_SIZE, seed=42, verbose=False, max_gen=MAX_GEN)
        if sol is not None:
            res_tmax.append({"T_max": t, "makespan": sol["makespan"], "labor_cost": sol["labor_cost"], "total_cost": sol["total_cost"]})

    df_tmax = pd.DataFrame(res_tmax)
    df_tmax.to_csv(os.path.join(out_dir, "oat_T_max.csv"), index=False)
    print("Saved oat_T_max.csv")

    # ---------------------------------------------------------
    # 4. Pareto Shift: alpha (Multi-objective)
    # ---------------------------------------------------------
    print("\n--- Pareto Shift: alpha ---")
    pareto_data = []
    for a in [0.5, 0.7, 0.9]:
        print(f"Running NSGA-II for alpha = {a}...")
        prob = ResourceBasedScheduling(
            tasks=tasks, precedence=precedence, resources=resources, N=N, K_i=K_i,
            alpha=a, beta=0.7, T_max=344, current_day=CURRENT_DAY,
            mode="multiobjective"
        )
        res_moo = solve(prob, pop_size=POP_SIZE, seed=42, verbose=False, max_gen=MAX_GEN)
        if res_moo is not None and res_moo.F is not None:
            F = res_moo.F
            for row in F:
                pareto_data.append({"alpha": a, "makespan": row[0], "labor_cost": row[1]})

    df_pareto = pd.DataFrame(pareto_data)
    df_pareto.to_csv(os.path.join(out_dir, "pareto_alpha.csv"), index=False)
    print("Saved pareto_alpha.csv")

    print("\n=== Sensitivity Analysis Complete ===")

if __name__ == "__main__":
    run_sensitivity()
