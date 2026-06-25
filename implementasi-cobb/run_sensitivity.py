import os
import pandas as pd
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import plotly.graph_objects as go
from tqdm import tqdm
from cobb_model import load_data, data_path, ResourceBasedScheduling, solve
from solver_milp import solve_milp_cobb_douglas

def plot_oat(df, param_col, title, out_path):
    fig, ax1 = plt.subplots(figsize=(8, 5))
    color = 'tab:red'
    ax1.set_xlabel(param_col)
    ax1.set_ylabel('Total Cost ($)', color=color)
    ax1.plot(df[param_col], df['total_cost'], marker='o', color=color, linewidth=2, label='Total Cost')
    ax1.tick_params(axis='y', labelcolor=color)
    ax2 = ax1.twinx()
    color = 'tab:blue'
    ax2.set_ylabel('Makespan (days)', color=color)
    ax2.plot(df[param_col], df['makespan'], marker='s', color=color, linestyle='--', linewidth=2, label='Makespan')
    ax2.tick_params(axis='y', labelcolor=color)
    fig.tight_layout()
    plt.title(title)
    lines_1, labels_1 = ax1.get_legend_handles_labels()
    lines_2, labels_2 = ax2.get_legend_handles_labels()
    ax1.legend(lines_1 + lines_2, labels_1 + labels_2, loc='upper center')
    plt.grid(True, alpha=0.3)
    plt.savefig(out_path, dpi=150, bbox_inches="tight")
    plt.close(fig)
    print(f"  -> Saved plot: {out_path}")


def plot_grid_3d(df, x_col, y_col, z_col, z_label, color_col, color_label, title, out_path):
    pivot_z = df.pivot_table(index=y_col, columns=x_col, values=z_col)
    pivot_c = df.pivot_table(index=y_col, columns=x_col, values=color_col)
    fig = go.Figure(data=[
        go.Surface(
            x=pivot_z.columns.values,
            y=pivot_z.index.values,
            z=pivot_z.values,
            surfacecolor=pivot_c.values,
            colorscale='Viridis',
            colorbar=dict(title=color_label),
            opacity=1.0,
            name=z_label,
            contours=dict(
                x=dict(show=True, color='black', width=1),
                y=dict(show=True, color='black', width=1),
                z=dict(show=True, color='black', width=1),
            ),
            lighting=dict(ambient=0.8, diffuse=0.6, specular=0.1, roughness=0.9, fresnel=0.1),
            lightposition=dict(x=1000, y=1000, z=1500),
        )
    ])
    fig.update_layout(
        title=title,
        scene=dict(
            xaxis_title=x_col,
            yaxis_title=y_col,
            zaxis_title=z_label,
            xaxis=dict(gridcolor='rgba(200,200,200,0.3)', showbackground=True, backgroundcolor='rgb(240,240,240)'),
            yaxis=dict(gridcolor='rgba(200,200,200,0.3)', showbackground=True, backgroundcolor='rgb(240,240,240)'),
            zaxis=dict(gridcolor='rgba(200,200,200,0.3)', showbackground=True, backgroundcolor='rgb(240,240,240)'),
        ),
        width=900,
        height=700,
    )
    fig.write_html(out_path)
    print(f"  -> Saved 3D plot: {out_path}")


def plot_pareto_shift(df, param_col, title, out_path):
    plt.figure(figsize=(10, 6))
    colors = ['r', 'g', 'b', 'c', 'm']
    vals = df[param_col].unique()
    y_col = 'total_cost' if 'total_cost' in df.columns else 'labor_cost'
    for i, v in enumerate(vals):
        subset = df[df[param_col] == v].sort_values(by='makespan')
        plt.plot(subset['makespan'], subset[y_col], marker='o',
                 color=colors[i % len(colors)], label=f'{param_col} = {v}')
    plt.xlabel('Makespan (days)')
    plt.ylabel(f'{y_col.replace("_", " ").title()} ($)')
    plt.title(title)
    plt.legend()
    plt.grid(True)
    plt.savefig(out_path, dpi=150, bbox_inches="tight")
    plt.close()
    print(f"  -> Saved plot: {out_path}")


def run_sensitivity():
    base_dir = os.path.dirname(os.path.abspath(__file__))
    out_dir = os.path.join(base_dir, "../outputs/sensitivity_analysis")
    oat_dir = os.path.join(out_dir, "OAT")
    grid_dir = os.path.join(out_dir, "Grid")
    pareto_dir = os.path.join(out_dir, "Pareto")
    os.makedirs(oat_dir, exist_ok=True)
    os.makedirs(grid_dir, exist_ok=True)
    os.makedirs(pareto_dir, exist_ok=True)

    tasks, precedence, resources, N, K_i = load_data(
        path_tasks=data_path("data_tasks.csv"),
        path_precedence=data_path("data_precedence.csv"),
        path_assignments=data_path("data_assignments.csv"),
    )

    CURRENT_DAY = 0
    POP_SIZE = 800
    MAX_GEN = 1000
    T_MAX_BASE = 310
    MILP_TIME_LIMIT = 20.0 # fast for testing

    print(f"=== Starting Extensive Sensitivity Analysis ===")
    print(f"Test specs: GA POP={POP_SIZE}, GEN={MAX_GEN} | MILP TimeLimit={MILP_TIME_LIMIT}s\n")

    # 1. OAT: alpha (0.0 to 1.0) - MILP
    print("--- 1/11 OAT: alpha (MILP) ---")
    alpha_vals = np.round(np.arange(0.0, 1.0, 0.1), 2)
    res_alpha = []
    for a in tqdm(alpha_vals, desc="OAT alpha"):
        sol = solve_milp_cobb_douglas(
            tasks, precedence, resources, N, K_i,
            alpha=a, beta=0.7, T_max=T_MAX_BASE, current_day=CURRENT_DAY, 
            mode="bonus_penalty", time_limit=MILP_TIME_LIMIT
        )
        if sol:
            res_alpha.append({"alpha": a, "makespan": sol["makespan"], "total_cost": sol["total_cost"]})
    df_alpha = pd.DataFrame(res_alpha)
    df_alpha.to_csv(os.path.join(out_dir, "oat_alpha.csv"), index=False)
    if not df_alpha.empty:
        plot_oat(df_alpha, "alpha", "Sensitivity: Crowding Elasticity (alpha)", os.path.join(oat_dir, "oat_alpha.png"))

    # 2. OAT: beta (0.0 to 1.0) - MILP
    print("--- 2/11 OAT: beta (MILP) ---")
    beta_vals = np.round(np.arange(0.0, 1.0, 0.1), 2)
    res_beta = []
    for b in tqdm(beta_vals, desc="OAT beta"):
        sol = solve_milp_cobb_douglas(
            tasks, precedence, resources, N, K_i,
            alpha=0.7, beta=b, T_max=T_MAX_BASE, current_day=CURRENT_DAY, 
            mode="bonus_penalty", time_limit=MILP_TIME_LIMIT
        )
        if sol:
            res_beta.append({"beta": b, "makespan": sol["makespan"], "total_cost": sol["total_cost"]})
    df_beta = pd.DataFrame(res_beta)
    df_beta.to_csv(os.path.join(out_dir, "oat_beta.csv"), index=False)
    if not df_beta.empty:
        plot_oat(df_beta, "beta", "Sensitivity: Overtime Efficiency (beta)", os.path.join(oat_dir, "oat_beta.png"))

    # 3. Grid: alpha x beta - MILP
    print("--- 3/11 Grid: alpha x beta (MILP) ---")
    res_grid_ab = []
    for a in tqdm(alpha_vals, desc="Grid alpha×beta"):
        for b in beta_vals:
            sol = solve_milp_cobb_douglas(
                tasks, precedence, resources, N, K_i,
                alpha=a, beta=b, T_max=T_MAX_BASE, current_day=CURRENT_DAY, 
                mode="bonus_penalty", time_limit=MILP_TIME_LIMIT
            )
            if sol:
                res_grid_ab.append({"alpha": a, "beta": b, "makespan": sol["makespan"], "total_cost": sol["total_cost"]})
    df_grid_ab = pd.DataFrame(res_grid_ab)
    df_grid_ab.to_csv(os.path.join(out_dir, "grid_alpha_beta.csv"), index=False)
    if not df_grid_ab.empty:
        plot_grid_3d(df_grid_ab, "alpha", "beta", "total_cost", "Total Cost ($)", "makespan", "Makespan (days)", "Total Cost vs Alpha & Beta", os.path.join(grid_dir, "grid_alpha_beta_cost.html"))
        plot_grid_3d(df_grid_ab, "alpha", "beta", "makespan", "Makespan (days)", "total_cost", "Total Cost ($)", "Makespan vs Alpha & Beta", os.path.join(grid_dir, "grid_alpha_beta_makespan.html"))

    # 4. OAT: c_late (10 variations) - MILP
    print("--- 4/11 OAT: c_late (MILP) ---")
    c_late_vals = np.linspace(0, 5000, 10)
    res_clate = []
    for c in tqdm(c_late_vals, desc="OAT c_late"):
        sol = solve_milp_cobb_douglas(
            tasks, precedence, resources, N, K_i,
            alpha=0.7, beta=0.7, T_max=T_MAX_BASE, current_day=CURRENT_DAY, 
            mode="bonus_penalty", c_late=c, c_early=2000, time_limit=MILP_TIME_LIMIT
        )
        if sol:
            res_clate.append({"c_late": c, "makespan": sol["makespan"], "total_cost": sol["total_cost"]})
    df_clate = pd.DataFrame(res_clate)
    df_clate.to_csv(os.path.join(out_dir, "oat_c_late.csv"), index=False)
    if not df_clate.empty:
        plot_oat(df_clate, "c_late", "Sensitivity: Penalty Rate (c_late)", os.path.join(oat_dir, "oat_c_late.png"))

    # 5. OAT: c_early (10 variations) - MILP
    print("--- 5/11 OAT: c_early (MILP) ---")
    c_early_vals = np.linspace(0, 5000, 10)
    res_cearly = []
    for ce in tqdm(c_early_vals, desc="OAT c_early"):
        sol = solve_milp_cobb_douglas(
            tasks, precedence, resources, N, K_i,
            alpha=0.7, beta=0.7, T_max=T_MAX_BASE, current_day=CURRENT_DAY, 
            mode="bonus_penalty", c_late=5000, c_early=ce, time_limit=MILP_TIME_LIMIT
        )
        if sol:
            res_cearly.append({"c_early": ce, "makespan": sol["makespan"], "total_cost": sol["total_cost"]})
    df_cearly = pd.DataFrame(res_cearly)
    df_cearly.to_csv(os.path.join(out_dir, "oat_c_early.csv"), index=False)
    if not df_cearly.empty:
        plot_oat(df_cearly, "c_early", "Sensitivity: Bonus Rate (c_early)", os.path.join(oat_dir, "oat_c_early.png"))

    # 6. Grid: c_late x c_early - MILP
    print("--- 6/11 Grid: c_late x c_early (MILP) ---")
    res_grid_ce = []
    for cl in tqdm(c_late_vals, desc="Grid c_late×c_early"):
        for ce in c_early_vals:
            sol = solve_milp_cobb_douglas(
                tasks, precedence, resources, N, K_i,
                alpha=0.7, beta=0.7, T_max=T_MAX_BASE, current_day=CURRENT_DAY, 
                mode="bonus_penalty", c_late=cl, c_early=ce, time_limit=MILP_TIME_LIMIT
            )
            if sol:
                res_grid_ce.append({"c_late": cl, "c_early": ce, "makespan": sol["makespan"], "total_cost": sol["total_cost"]})
    df_grid_ce = pd.DataFrame(res_grid_ce)
    df_grid_ce.to_csv(os.path.join(out_dir, "grid_clate_cearly.csv"), index=False)
    if not df_grid_ce.empty:
        plot_grid_3d(df_grid_ce, "c_late", "c_early", "total_cost", "Total Cost ($)", "makespan", "Makespan (days)", "Total Cost vs Penalty & Bonus", os.path.join(grid_dir, "grid_clate_cearly_cost.html"))
        plot_grid_3d(df_grid_ce, "c_late", "c_early", "makespan", "Makespan (days)", "total_cost", "Total Cost ($)", "Makespan vs Penalty & Bonus", os.path.join(grid_dir, "grid_clate_cearly_makespan.html"))

    # 7. OAT: T_max (more variations) - MILP
    print("--- 7/11 OAT: T_max (MILP) ---")
    tmax_vals = np.arange(290, 345, 4)  # ~14 variations
    res_tmax = []
    for t in tqdm(tmax_vals, desc="OAT T_max"):
        sol = solve_milp_cobb_douglas(
            tasks, precedence, resources, N, K_i,
            alpha=0.7, beta=0.7, T_max=int(t), current_day=CURRENT_DAY, 
            mode="bonus_penalty", time_limit=MILP_TIME_LIMIT
        )
        if sol:
            res_tmax.append({"T_max": t, "makespan": sol["makespan"], "total_cost": sol["total_cost"]})
    df_tmax = pd.DataFrame(res_tmax)
    df_tmax.to_csv(os.path.join(out_dir, "oat_T_max.csv"), index=False)
    if not df_tmax.empty:
        plot_oat(df_tmax, "T_max", "Sensitivity: Target Deadline (T_max)", os.path.join(oat_dir, "oat_T_max.png"))

    # # 8. Pareto Shift: alpha (0.3, 0.6, 0.9) - GA
    # print("--- 8/11 Pareto Shift: alpha (GA) ---")
    # pareto_a = []
    # for a in tqdm([0.3, 0.6, 0.9], desc="Pareto alpha"):
    #     prob = ResourceBasedScheduling(
    #         tasks=tasks, precedence=precedence, resources=resources, N=N, K_i=K_i,
    #         alpha=a, beta=0.7, T_max=344, current_day=CURRENT_DAY, mode="multiobjective"
    #     )
    #     sol = solve(prob, pop_size=POP_SIZE, seed=42, verbose=False, max_gen=MAX_GEN)
    #     if sol and sol.F is not None:
    #         for row in sol.F:
    #             pareto_a.append({"alpha": a, "makespan": row[0], "labor_cost": row[1]})
    # df_pareto_a = pd.DataFrame(pareto_a)
    # df_pareto_a.to_csv(os.path.join(out_dir, "pareto_alpha.csv"), index=False)
    # if not df_pareto_a.empty:
    #     plot_pareto_shift(df_pareto_a, "alpha", "Pareto Shift: Crowding Elasticity (alpha)", os.path.join(pareto_dir, "pareto_alpha.png"))

    # # 9. Pareto Shift: beta (0.3, 0.6, 0.9) - GA
    # print("--- 9/11 Pareto Shift: beta (GA) ---")
    # pareto_b = []
    # for b in tqdm([0.3, 0.6, 0.9], desc="Pareto beta"):
    #     prob = ResourceBasedScheduling(
    #         tasks=tasks, precedence=precedence, resources=resources, N=N, K_i=K_i,
    #         alpha=0.7, beta=b, T_max=344, current_day=CURRENT_DAY, mode="multiobjective"
    #     )
    #     sol = solve(prob, pop_size=POP_SIZE, seed=42, verbose=False, max_gen=MAX_GEN)
    #     if sol and sol.F is not None:
    #         for row in sol.F:
    #             pareto_b.append({"beta": b, "makespan": row[0], "labor_cost": row[1]})
    # df_pareto_b = pd.DataFrame(pareto_b)
    # df_pareto_b.to_csv(os.path.join(out_dir, "pareto_beta.csv"), index=False)
    # if not df_pareto_b.empty:
    #     plot_pareto_shift(df_pareto_b, "beta", "Pareto Shift: Overtime Efficiency (beta)", os.path.join(pareto_dir, "pareto_beta.png"))
    
    # # 10. Pareto Shift: c_early and c_late - GA
    # print("--- 10/11 Pareto Shift: Base Run for Cost Parameters (GA) ---")
    # prob_base = ResourceBasedScheduling(
    #     tasks=tasks, precedence=precedence, resources=resources, N=N, K_i=K_i,
    #     alpha=0.7, beta=0.7, T_max=310, current_day=CURRENT_DAY, mode="multiobjective"
    # )
    # sol_base = solve(prob_base, pop_size=POP_SIZE, seed=42, verbose=False, max_gen=MAX_GEN)
    # if sol_base and sol_base.F is not None:
    #     base_front = sol_base.F
        
    #     # c_late variations
    #     print("--- 10/11 Pareto Shift: c_late ---")
    #     pareto_cl = []
    #     for cl in [2000, 5000, 8000]:
    #         for row in base_front:
    #             mkspan = row[0]
    #             lab_cost = row[1]
    #             tot_cost = lab_cost + cl * max(0, mkspan - 310) - 2000 * max(0, 310 - mkspan)
    #             pareto_cl.append({"c_late": cl, "makespan": mkspan, "total_cost": tot_cost})
    #     df_pareto_cl = pd.DataFrame(pareto_cl)
    #     df_pareto_cl.to_csv(os.path.join(out_dir, "pareto_c_late.csv"), index=False)
    #     if not df_pareto_cl.empty:
    #         plot_pareto_shift(df_pareto_cl, "c_late", "Pareto Shift: Penalty Rate (c_late) on Total Cost", os.path.join(pareto_dir, "pareto_c_late.png"))
        
    #     # c_early variations
    #     print("--- 11/11 Pareto Shift: c_early ---")
    #     pareto_ce = []
    #     for ce in [0, 2000, 4000]:
    #         for row in base_front:
    #             mkspan = row[0]
    #             lab_cost = row[1]
    #             tot_cost = lab_cost + 5000 * max(0, mkspan - 310) - ce * max(0, 310 - mkspan)
    #             pareto_ce.append({"c_early": ce, "makespan": mkspan, "total_cost": tot_cost})
    #     df_pareto_ce = pd.DataFrame(pareto_ce)
    #     df_pareto_ce.to_csv(os.path.join(out_dir, "pareto_c_early.csv"), index=False)
    #     if not df_pareto_ce.empty:
    #         plot_pareto_shift(df_pareto_ce, "c_early", "Pareto Shift: Bonus Rate (c_early) on Total Cost", os.path.join(pareto_dir, "pareto_c_early.png"))

    print("\n=== Sensitivity Analysis Complete ===")

if __name__ == "__main__":
    run_sensitivity()
