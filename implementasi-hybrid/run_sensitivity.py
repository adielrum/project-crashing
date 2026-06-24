import os
import json
import time
import multiprocessing
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
import plotly.graph_objects as go

from solver_base import (
    read_json,
    build_predecessors,
    infer_activity_states_without_state_file,
    SolveConfig,
    build_model_and_solve,
    build_reference_no_crash_schedule,
    write_json,
    write_schedule_csv
)

base_dir = os.path.dirname(os.path.abspath(__file__))

activity_data_path = os.path.join(base_dir, "data/activity_data.json")
resource_capacity_path = os.path.join(base_dir, "data/resource_capacity.json")
resource_req_path = os.path.join(base_dir, "data/resource_requirements.json")

activity_data = read_json(activity_data_path)
resource_capacity = read_json(resource_capacity_path)
resource_requirements = read_json(resource_req_path)

predecessors, _ = build_predecessors(activity_data, [], True)

current_day = 0
target_end_date = 344

states, _ = infer_activity_states_without_state_file(
    activity_data, resource_requirements, resource_capacity,
    predecessors, current_day, 60.0, 1
)

# Normal (no-crash) baseline duration — kept just for reference/logging.
baseline_schedule = build_reference_no_crash_schedule(
    activity_data, resource_requirements, resource_capacity,
    predecessors, current_day, 60.0, 1
)
NORMAL_DURATION = max(row["end"] for row in baseline_schedule.values())
MAKESPAN_CAP = 344


def run_bonus_penalty(c_late=5000.0, c_early=2000.0):
    cfg = SolveConfig(
        target_end_date=target_end_date,
        current_day=current_day,
        time_limit=60.0,
        num_workers=8,
        auto_fix_paint_trim_cycle=True,
        remove_edges=[],
        c_late=c_late,
        c_early=c_early
    )

    result = build_model_and_solve(
        activity_data,
        resource_requirements,
        resource_capacity,
        predecessors,
        states,
        cfg,
        mode="bonus_penalty",
    )
    return result


def solve_single(args):
    c_late, c_early = args
    result = run_bonus_penalty(c_late=c_late, c_early=c_early)
    makespan = result.get("makespan", np.nan)
    crash_cost = result.get("total_crash_cost", 0.0)

    # Calculate penalty and bonus applied (using raw, uncapped makespan)
    penalty_applied = max(0.0, (makespan - target_end_date)) * c_late if not np.isnan(makespan) else 0.0
    bonus_applied = max(0.0, (target_end_date - makespan)) * c_early if not np.isnan(makespan) else 0.0
    net_cost = crash_cost + penalty_applied - bonus_applied

    return {
        "c_late": c_late,
        "c_early": c_early,
        "makespan": makespan,
        "total_crash_cost": crash_cost,
        "penalty_applied": penalty_applied,
        "bonus_applied": bonus_applied,
        "net_cost": net_cost,
        "status": result.get("status", "FAILED")
    }


if __name__ == "__main__":
    # Define a 100x100 grid for penalty (c_late) and bonus (c_early)
    c_late_vals = np.linspace(0, 5000, 100)
    c_early_vals = np.linspace(0, 2000, 100)

    tasks = [(float(cl), float(ce)) for cl in c_late_vals for ce in c_early_vals]

    num_cores = max(1, multiprocessing.cpu_count() - 1)
    print(f"Starting grid search (10,000 runs) using {num_cores} workers...")

    start_time = time.time()
    results = []

    with multiprocessing.Pool(processes=num_cores) as pool:
        count = 0
        total_tasks = len(tasks)
        for res in pool.imap_unordered(solve_single, tasks, chunksize=10):
            results.append(res)
            count += 1
            if count % 500 == 0:
                elapsed = time.time() - start_time
                pct = (count / total_tasks) * 100
                est_total = (elapsed / count) * total_tasks
                remaining = est_total - elapsed
                print(f"Progress: {count}/{total_tasks} ({pct:.1f}%) | Elapsed: {elapsed:.1f}s | Est. Remaining: {remaining:.1f}s")

    total_elapsed = time.time() - start_time
    print(f"Grid search completed in {total_elapsed:.1f}s.")

    df = pd.DataFrame(results)

    # Keep the raw, uncapped makespan in its own column, then add a capped
    # column used for plotting. Nothing is lost from the CSV.
    df["makespan_raw"] = df["makespan"]
    df["makespan"] = df["makespan_raw"].clip(upper=MAKESPAN_CAP)

    # Save the raw results to CSV (includes both raw and capped columns)
    out_dir = os.path.join(base_dir, "../outputs/sensitivity_analysis")
    os.makedirs(out_dir, exist_ok=True)
    csv_path = os.path.join(out_dir, "grid_skenario3_bonus_penalty_100x100.csv")
    df.to_csv(csv_path, index=False)
    print(f"Results saved to {csv_path}")

    n_capped = int((df["makespan_raw"] > MAKESPAN_CAP).sum())
    if n_capped:
        print(f"Capped {n_capped}/{len(df)} grid points where raw makespan exceeded "
              f"{MAKESPAN_CAP} days for display purposes.")

    # Pivot results for heatmap plotting (uses capped makespan column)
    pivot_makespan = df.pivot(index='c_late', columns='c_early', values='makespan')
    pivot_crash_cost = df.pivot(index='c_late', columns='c_early', values='total_crash_cost')
    pivot_net_cost = df.pivot(index='c_late', columns='c_early', values='net_cost')

    x_early = pivot_makespan.columns.values
    y_late = pivot_makespan.index.values

    # Extent: [xmin, xmax, ymin, ymax] -> [c_early_min, c_early_max, c_late_min, c_late_max]
    extent = [df['c_early'].min(), df['c_early'].max(), df['c_late'].min(), df['c_late'].max()]

    # Create the heatmap plots
    fig, axes = plt.subplots(1, 3, figsize=(22, 6))

    # 1. Makespan Heatmap (capped at MAKESPAN_CAP, color scale starts at data min)
    im1 = axes[0].imshow(
        pivot_makespan.values,
        extent=extent,
        origin='lower',
        cmap='viridis',
        aspect='auto',
        vmin=pivot_makespan.values.min(),
        vmax=MAKESPAN_CAP
    )
    axes[0].set_title(f'Optimal Makespan (Days)\n(capped at {MAKESPAN_CAP}d)')
    axes[0].set_xlabel('Early Bonus (c_early)')
    axes[0].set_ylabel('Late Penalty (c_late)')
    fig.colorbar(im1, ax=axes[0], label='Days')

    # 2. Total Crash Cost Heatmap
    im2 = axes[1].imshow(
        pivot_crash_cost.values,
        extent=extent,
        origin='lower',
        cmap='plasma',
        aspect='auto'
    )
    axes[1].set_title('Total Crash Cost ($)')
    axes[1].set_xlabel('Early Bonus (c_early)')
    axes[1].set_ylabel('Late Penalty (c_late)')
    fig.colorbar(im2, ax=axes[1], label='Cost ($)')

    # 3. Net Cost Heatmap
    im3 = axes[2].imshow(
        pivot_net_cost.values,
        extent=extent,
        origin='lower',
        cmap='coolwarm',
        aspect='auto'
    )
    axes[2].set_title('Net Project Cost ($)\n(Crash Cost + Penalty - Bonus)')
    axes[2].set_xlabel('Early Bonus (c_early)')
    axes[2].set_ylabel('Late Penalty (c_late)')
    fig.colorbar(im3, ax=axes[2], label='Net Cost ($)')

    plt.tight_layout()
    plot_path = os.path.join(out_dir, "grid_skenario3_bonus_penalty_heatmap.png")
    plt.savefig(plot_path, dpi=300)
    plt.close()
    print(f"Heatmap plot saved to {plot_path}")

    # Create interactive 3D plot
    fig = go.Figure()

    # z-axis range for makespan: start a bit below the actual minimum (not 0)
    # so the floor of the surface isn't squashed against the axis, and cap
    # the top at MAKESPAN_CAP so the degenerate spike doesn't dominate scale.
    z_min_data = float(pivot_makespan.values.min())
    z_floor = max(0.0, z_min_data - 0.05 * (MAKESPAN_CAP - z_min_data))

    # Add Surface for Makespan (visible by default) — shape (z-axis) based on
    # capped makespan, but color mapped to total crash cost so you can read both
    # dimensions at once from the single surface.
    crash_cost_min = float(pivot_crash_cost.values.min())
    crash_cost_max = float(pivot_crash_cost.values.max())
    fig.add_trace(go.Surface(
        z=pivot_makespan.values,
        x=x_early,
        y=y_late,
        surfacecolor=pivot_crash_cost.values,   # color = crash cost
        colorscale='Plasma',
        cmin=crash_cost_min,
        cmax=crash_cost_max,
        colorbar=dict(title="Crash Cost ($)", x=-0.1),
        name='Makespan',
        visible=True
    ))

    # Add Surface for Total Crash Cost (hidden by default) — shape (z-axis)
    # based on crash cost, but color mapped to makespan (capped).
    fig.add_trace(go.Surface(
        z=pivot_crash_cost.values,
        x=x_early,
        y=y_late,
        surfacecolor=pivot_makespan.values,     # color = makespan (capped)
        colorscale='Viridis',
        cmin=z_min_data,
        cmax=MAKESPAN_CAP,
        colorbar=dict(title="Makespan (days)", x=-0.1),
        name='Total Crash Cost',
        visible=False
    ))

    # Add Surface for Net Project Cost (hidden by default)
    fig.add_trace(go.Surface(
        z=pivot_net_cost.values,
        x=x_early,
        y=y_late,
        colorscale='RdBu',
        reversescale=True,
        colorbar=dict(title="Net Cost ($)", x=-0.1),
        name='Net Project Cost',
        visible=False
    ))

    # Update layout with dropdown and axis titles
    fig.update_layout(
        title=f'Interactive 3D Sensitivity Analysis (Skenario 2) — Makespan shape, Crash Cost color (capped at {MAKESPAN_CAP}d)',
        scene=dict(
            xaxis_title='Early Bonus (c_early)',
            yaxis_title='Late Penalty (c_late)',
            zaxis_title='Makespan (days)',
            zaxis=dict(range=[z_floor, MAKESPAN_CAP]),
            camera=dict(
                eye=dict(x=1.8, y=1.8, z=1.2)
            )
        ),
        updatemenus=[
            dict(
                active=0,
                buttons=list([
                    dict(
                        label="Makespan (Days) — Color: Crash Cost",
                        method="update",
                        args=[{"visible": [True, False, False]},
                              {"scene.zaxis.title.text": "Makespan (days)",
                               "scene.zaxis.range": [z_floor, MAKESPAN_CAP]}]
                    ),
                    dict(
                        label="Total Crash Cost ($) — Color: Makespan",
                        method="update",
                        args=[{"visible": [False, True, False]},
                              {"scene.zaxis.title.text": "Crash Cost ($)",
                               "scene.zaxis.range": [None, None]}]
                    ),
                    dict(
                        label="Net Project Cost ($)",
                        method="update",
                        args=[{"visible": [False, False, True]},
                              {"scene.zaxis.title.text": "Net Cost ($)",
                               "scene.zaxis.range": [None, None]}]
                    ),
                ]),
                direction="down",
                pad={"r": 10, "t": 10},
                showactive=True,
                x=0.1,
                xanchor="left",
                y=1.15,
                yanchor="top"
            ),
        ],
        width=1000,
        height=800
    )

    html_path = os.path.join(out_dir, "grid_skenario3_bonus_penalty_3d.html")
    fig.write_html(html_path)
    print(f"Interactive 3D Plotly chart saved to {html_path}")