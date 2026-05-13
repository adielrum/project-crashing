"""
Flask web interface for the project crashing optimizer.

Run:
    python webapp.py
Then open http://127.0.0.1:5000

Form fields control all model parameters; "Run" triggers the solver and
embeds the resulting Plotly Gantt + tradeoff plots inline.
"""

import io
import json
import time
import traceback
from datetime import datetime

from flask import Flask, render_template, request, jsonify

from optimizer_core import DEFAULTS, load_data, solve_ga
from solver_milp import solve_milp


app = Flask(__name__)
DATA_FOLDER = "Schedules_CSV"
BASE_DATE = datetime(2023, 5, 1)

# Cache loaded data (small)
_DATA_CACHE = None


def get_data():
    global _DATA_CACHE
    if _DATA_CACHE is None:
        _DATA_CACHE = load_data(DATA_FOLDER, BASE_DATE)
    return _DATA_CACHE


# ---------------------- Plotly figure builders ----------------------

def _build_original_gantt_fig(tasks):
    from optimizer_core import day_to_date
    level2 = [(tid, t) for tid, t in tasks.items() if t.outline_level == 2]
    # Sort by BASELINE start day to preserve original schedule ordering
    sorted_tasks = sorted(level2, key=lambda x: x[1].start_day)
    task_labels = [f"{tid}: {t.name}" for tid, t in sorted_tasks]

    data = []

    for tid, t in sorted_tasks:
        start_dt = day_to_date(t.start_day, BASE_DATE).isoformat()
        end_dt = day_to_date(t.finish_day, BASE_DATE).isoformat()
        
        info = f"<b>{tid}: {t.name}</b><br>Day {t.start_day} → Day {t.finish_day} ({t.finish_day - t.start_day:.1f}d)"

        data.append(dict(
            type='scatter',
            x=[start_dt, end_dt],
            y=[f"{tid}: {t.name}", f"{tid}: {t.name}"],
            mode='lines',
            line=dict(color="#3b82f6", width=14), # standard blue
            name="Original Schedule",
            showlegend=False,
            hovertemplate=info + "<extra></extra>",
        ))

    layout = dict(
        title="Original Baseline Schedule",
        xaxis=dict(title="Date", type="date"),
        yaxis=dict(
            title="Task", autorange="reversed", tickfont=dict(size=9),
            categoryorder="array", categoryarray=task_labels,
        ),
        height=max(600, 18 * len(sorted_tasks)),
        hovermode="closest",
        margin=dict(l=300, r=40, t=80, b=60),
    )
    return dict(data=data, layout=layout)

def _build_gantt_fig(tasks, result, current_day):
    from optimizer_core import day_to_date, build_active_set
    schedule = result["schedule"]
    crash_plan = result["crash_plan"]
    level2 = [(tid, t) for tid, t in tasks.items() if t.outline_level == 2]
    # Sort by BASELINE start day to preserve original schedule ordering
    sorted_tasks = sorted(level2, key=lambda x: x[1].start_day)
    task_labels = [f"{tid}: {t.name}" for tid, t in sorted_tasks]

    # Determine which tasks are currently in-progress (started but not yet finished)
    _, active_set = build_active_set(tasks, current_day)

    data = []
    legend_shown = set()
    cur_dt = day_to_date(current_day, BASE_DATE).isoformat()

    for tid, t in sorted_tasks:
        sv, fv = schedule.get(tid, (t.start_day, t.finish_day))
        sv, fv = float(sv), float(fv)
        end_dt = day_to_date(int(round(fv)), BASE_DATE).isoformat()
        is_crashed = t.name in crash_plan
        is_done = fv < current_day
        is_active = tid in active_set

        if is_done:
            group, color = "Completed", "#cccccc"
        elif is_crashed:
            group, color = "Crashed", "#ef4444"
        else:
            group, color = "Active (normal)", "#3b82f6"

        # For active tasks the MILP pins s[tid]=current_day (remaining-work anchor),
        # but visually the bar must start from the original baseline start date.
        visual_start_day = t.start_day if is_active else int(round(sv))
        start_dt = day_to_date(visual_start_day, BASE_DATE).isoformat()

        info = [f"<b>{tid}: {t.name}</b>",
                (f"Started Day {visual_start_day} → Finishes Day {int(fv)} "
                 f"(remaining: {fv - current_day:.1f}d)") if is_active
                else f"Day {visual_start_day} → Day {int(fv)} ({fv - visual_start_day:.1f}d)"]
        if is_crashed:
            info.append("<br><b>CRASHED:</b>")
            for entry in crash_plan[t.name]:
                info.append(
                    f"&nbsp;&nbsp;{entry['resource']}: x={entry['x']}, "
                    f"τ={entry['tau']}h, +${entry['cost_delta']:,.0f}, "
                    f"saved={entry['duration_saved']:.1f}d"
                )
        text = "<br>".join(info)

        if is_active and not is_done:
            # Completed portion: original start → current_day (grey)
            data.append(dict(
                type='scatter',
                x=[start_dt, cur_dt],
                y=[f"{tid}: {t.name}", f"{tid}: {t.name}"],
                mode='lines',
                line=dict(color="#cccccc", width=14),
                name="Completed", legendgroup="Completed",
                showlegend=("Completed" not in legend_shown),
                hovertemplate=f"<b>{tid}: {t.name}</b><br>Completed portion<extra></extra>",
            ))
            legend_shown.add("Completed")
            # Remaining / optimized portion: current_day → optimized finish (colored)
            data.append(dict(
                type='scatter',
                x=[cur_dt, end_dt],
                y=[f"{tid}: {t.name}", f"{tid}: {t.name}"],
                mode='lines',
                line=dict(color=color, width=14),
                name=group, legendgroup=group,
                showlegend=(group not in legend_shown),
                hovertemplate=text + "<extra></extra>",
            ))
            legend_shown.add(group)
        else:
            data.append(dict(
                type='scatter',
                x=[start_dt, end_dt],
                y=[f"{tid}: {t.name}", f"{tid}: {t.name}"],
                mode='lines',
                line=dict(color=color, width=14),
                name=group, legendgroup=group,
                showlegend=(group not in legend_shown),
                hovertemplate=text + "<extra></extra>",
            ))
            legend_shown.add(group)

    target_dt = day_to_date(result["target_day"], BASE_DATE).isoformat()
    layout = dict(
        title=f"{result['solver']} | makespan={result['makespan']:.1f}d, "
              f"crash_extra=${result['crash_cost']:,.0f}",
        xaxis=dict(title="Date", type="date"),
        yaxis=dict(
            title="Task", autorange="reversed", tickfont=dict(size=9),
            categoryorder="array", categoryarray=task_labels,
        ),
        height=max(600, 18 * len(sorted_tasks)),
        hovermode="closest",
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
        margin=dict(l=300, r=40, t=80, b=60),
        shapes=[
            dict(type="line", x0=cur_dt, x1=cur_dt, y0=0, y1=1, yref="paper",
                 line=dict(color="black", width=2, dash="dash")),
            dict(type="line", x0=target_dt, x1=target_dt, y0=0, y1=1, yref="paper",
                 line=dict(color="blue", width=2, dash="dot")),
        ],
        annotations=[
            dict(x=cur_dt, y=1.02, yref="paper", showarrow=False,
                 text=f"Current Day {current_day}"),
            dict(x=target_dt, y=-0.05, yref="paper", showarrow=False,
                 text=f"Target {result['target_day']}", font=dict(color="blue")),
        ],
    )
    return dict(data=data, layout=layout)


def _build_tradeoff_fig(curve):
    targets = [r["target_day"] for r in curve if r.get("success")]
    costs = [r["crash_cost"] for r in curve if r.get("success")]
    data = [dict(
        type='scatter', x=targets, y=costs, mode='lines+markers',
        name='Crash extra cost',
        hovertemplate="T=%{x}, cost=$%{y:,.0f}<extra></extra>",
    )]
    layout = dict(
        title="Time-Cost Trade-off Curve",
        xaxis=dict(title="Target Project End Day"),
        yaxis=dict(title="Crash Extra Cost ($)"),
        height=500,
    )
    return dict(data=data, layout=layout)


def _build_resload_fig(tasks, resources, assignments, result):
    from collections import defaultdict
    from optimizer_core import day_to_date
    import numpy as np
    schedule = result["schedule"]
    crash_plan = result["crash_plan"]
    x_per_assignment = {}
    for tname, entries in crash_plan.items():
        for e in entries:
            x_per_assignment[(tname, e["resource"])] = e.get("x", 1.0)

    horizon = max(int(f) for s, f in schedule.values())
    by_resource = defaultdict(lambda: np.zeros(horizon + 2))
    for a in assignments:
        if a.task_id not in schedule:
            continue
        s_d, f_d = schedule[a.task_id]
        s_d, f_d = int(round(s_d)), int(round(f_d))
        x_eff = x_per_assignment.get(
            (tasks[a.task_id].name, resources[a.resource_id].name), 1.0
        )
        load = a.units_percent * x_eff
        for t in range(max(1, s_d), min(horizon, f_d) + 1):
            by_resource[a.resource_id][t] += load

    data = []
    for rid, loads in sorted(by_resource.items(), key=lambda kv: -kv[1].sum()):
        if loads.sum() < 0.5:
            continue
        x_dates = [day_to_date(t, BASE_DATE).isoformat() for t in range(1, horizon + 1)]
        y_vals = list(loads[1:horizon + 1])
        data.append(dict(
            type='scatter', x=x_dates, y=y_vals, mode='lines',
            name=resources[rid].name,
            hovertemplate=(f"{resources[rid].name}<br>"
                           f"Day %{{x}}: %{{y:.2f}} (cap={resources[rid].max_units})"
                           "<extra></extra>"),
        ))
    layout = dict(
        title="Daily resource load (after crashing)",
        xaxis=dict(title="Date", type="date"),
        yaxis=dict(title="Units"),
        height=500,
        legend=dict(font=dict(size=9)),
        shapes=[dict(type="line", x0=0, x1=1, xref="paper", y0=1.0, y1=1.0,
                     line=dict(color="red", dash="dash"))],
        annotations=[dict(x=0.5, xref="paper", y=1.03, yref="paper",
                          text="capacity = 1.0", showarrow=False,
                          font=dict(color="red", size=11))],
    )
    return dict(data=data, layout=layout)


# ---------------------- Routes ----------------------

@app.route('/')
def index():
    return render_template('index.html')


@app.route('/original_gantt')
def original_gantt():
    try:
        tasks, _, _ = get_data()
        fig = _build_original_gantt_fig(tasks)
        return jsonify(success=True, original_gantt_fig=fig)
    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify(success=False, error=str(e))


@app.route('/run', methods=['POST'])
def run_optimizer():
    try:
        body = request.get_json(force=True)
        params = {
            "alpha": float(body.get("alpha", 0.7)),
            "beta": float(body.get("beta", 0.7)),
            "ot_mult": float(body.get("ot_mult", 1.5)),
            "c_late": float(body.get("c_late", 5000)),
            "c_early": float(body.get("c_early", 2000)),
            "x_grid": DEFAULTS["x_grid"],
            "tau_grid": DEFAULTS["tau_grid"],
        }
        current_day = int(body.get("current_day", 100))
        target_day = int(body.get("target_day", 300))
        method = body.get("method", "milp_v2")
        hard_deadline = bool(body.get("hard_deadline", False))
        do_tradeoff = bool(body.get("tradeoff", False))

        tasks, resources, assignments = get_data()

        # Solve
        if method == "ga":
            result = solve_ga(tasks, resources, assignments,
                              current_day, target_day, params=params)
        else:
            capacity = (method == "milp_v3")
            result = solve_milp(tasks, resources, assignments,
                                current_day, target_day, params=params,
                                hard_deadline=hard_deadline, capacity=capacity,
                                time_limit=120)

        if not result.get("success"):
            return jsonify(success=False,
                           error=f"Solver returned: {result.get('status', 'unknown')}")

        # Visualizations
        gantt_fig = _build_gantt_fig(tasks, result, current_day)
        resload_fig = _build_resload_fig(tasks, resources, assignments, result)

        tradeoff_fig = None
        if do_tradeoff and method.startswith("milp"):
            capacity = (method == "milp_v3")
            # Probe min makespan
            probe = solve_milp(tasks, resources, assignments,
                               current_day, current_day, params=params,
                               capacity=capacity, time_limit=60)
            min_make = int(probe['makespan']) if probe.get('success') else target_day
            base_make = int(result['makespan']) if result.get('success') else 480
            lo = min_make
            hi = max(base_make + 30, target_day + 30)
            step = max(1, (hi - lo) // 8)
            curve = []
            for tgt in range(lo, hi + 1, step):
                r = solve_milp(tasks, resources, assignments, current_day, tgt,
                               params=params, capacity=capacity,
                               hard_deadline=True, time_limit=60)
                if r.get("success"):
                    curve.append(r)
            if curve:
                tradeoff_fig = _build_tradeoff_fig(curve)

        return jsonify(
            success=True,
            solver=result["solver"],
            makespan=result["makespan"],
            baseline_cost=result["baseline_cost"],
            crash_cost=result["crash_cost"],
            I_late=result.get("I_late", 0),
            I_early=result.get("I_early", 0),
            deadline_term=result.get("deadline_term", 0),
            crash_plan=result["crash_plan"],
            gantt_fig=gantt_fig,
            tradeoff_fig=tradeoff_fig,
            resload_fig=resload_fig,
        )

    except Exception as e:
        traceback.print_exc()
        return jsonify(success=False, error=str(e))


if __name__ == '__main__':
    print("Web UI on http://127.0.0.1:5000")
    app.run(debug=False, host='127.0.0.1', port=5000)
