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

from flask import Flask, render_template_string, request, jsonify

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


# ---------------------- HTML template ----------------------

PAGE = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<title>Project Crashing Optimizer</title>
<script src="https://cdn.plot.ly/plotly-2.32.0.min.js"></script>
<style>
* { box-sizing: border-box; }
body {
  font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
  margin: 0; background: #f5f7fa; color: #222;
}
header {
  background: #2c3e50; color: white; padding: 14px 24px;
}
header h1 { margin: 0; font-size: 20px; }
.layout {
  display: grid; grid-template-columns: 340px 1fr; min-height: calc(100vh - 50px);
}
.sidebar {
  background: white; padding: 20px; border-right: 1px solid #ddd;
  overflow-y: auto; max-height: calc(100vh - 50px);
}
.main { padding: 20px; overflow-y: auto; max-height: calc(100vh - 50px); }
fieldset { border: 1px solid #ddd; border-radius: 6px; margin: 0 0 14px; padding: 12px; }
legend { font-weight: 600; padding: 0 6px; color: #555; font-size: 13px; }
label { display: block; font-size: 12px; color: #555; margin: 8px 0 3px; }
input[type=number], input[type=text], select {
  width: 100%; padding: 6px 8px; font-size: 13px; border: 1px solid #ccc;
  border-radius: 4px; background: white;
}
input[type=checkbox] { margin-right: 6px; }
button {
  width: 100%; padding: 10px; font-size: 14px; font-weight: 600;
  background: #3498db; color: white; border: none; border-radius: 6px;
  cursor: pointer; margin-top: 8px;
}
button:hover { background: #2980b9; }
button:disabled { background: #95a5a6; cursor: wait; }
.status { padding: 12px; background: #ecf0f1; border-radius: 4px;
  font-family: ui-monospace, "SF Mono", Menlo, monospace; font-size: 12px;
  white-space: pre-wrap; min-height: 80px; }
.tabs { display: flex; gap: 4px; margin-bottom: 12px; border-bottom: 2px solid #ddd; }
.tab {
  padding: 8px 16px; cursor: pointer; background: none; border: none;
  font-size: 14px; color: #555; border-bottom: 3px solid transparent;
  margin-bottom: -2px; width: auto;
}
.tab.active { color: #3498db; border-bottom-color: #3498db; font-weight: 600; }
.tab-panel { display: none; }
.tab-panel.active { display: block; }
.summary { display: grid; grid-template-columns: repeat(auto-fit, minmax(140px, 1fr));
  gap: 10px; margin-bottom: 14px; }
.metric { background: white; padding: 10px 12px; border-radius: 6px;
  border: 1px solid #e0e0e0; }
.metric .label { font-size: 11px; color: #888; text-transform: uppercase; }
.metric .value { font-size: 17px; font-weight: 600; color: #2c3e50; margin-top: 2px; }
.crash-table { width: 100%; border-collapse: collapse; font-size: 12px;
  background: white; }
.crash-table th, .crash-table td { padding: 6px 8px; text-align: left;
  border-bottom: 1px solid #eee; }
.crash-table th { background: #f8f9fa; font-weight: 600; color: #555; }
.row-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 8px; }
.help { color: #888; font-size: 11px; margin-top: 2px; }
</style>
</head>
<body>
<header><h1>Resource-Constrained Project Crashing Optimizer</h1></header>
<div class="layout">
  <div class="sidebar">
    <form id="opt-form">
      <fieldset>
        <legend>Schedule</legend>
        <div class="row-grid">
          <div>
            <label>Current day</label>
            <input type="number" name="current_day" value="100" min="1" max="480">
          </div>
          <div>
            <label>Target end day</label>
            <input type="number" name="target_day" value="300" min="1" max="480">
          </div>
        </div>
      </fieldset>

      <fieldset>
        <legend>Cobb-Douglas</legend>
        <div class="row-grid">
          <div>
            <label>α (overcrowding)</label>
            <input type="number" name="alpha" value="0.7" step="0.05" min="0.1" max="0.95">
          </div>
          <div>
            <label>β (overtime)</label>
            <input type="number" name="beta" value="0.7" step="0.05" min="0.1" max="0.95">
          </div>
        </div>
        <div class="help">Lower → faster diminishing returns</div>
      </fieldset>

      <fieldset>
        <legend>Costs</legend>
        <label>Overtime multiplier (r' / r)</label>
        <input type="number" name="ot_mult" value="1.5" step="0.1" min="1.0" max="3.0">
        <div class="row-grid">
          <div>
            <label>Late penalty $/d</label>
            <input type="number" name="c_late" value="5000" step="500" min="0">
          </div>
          <div>
            <label>Early bonus $/d</label>
            <input type="number" name="c_early" value="2000" step="500" min="0">
          </div>
        </div>
      </fieldset>

      <fieldset>
        <legend>Solver</legend>
        <label>Method</label>
        <select name="method">
          <option value="milp_v2">MILP v2 (no capacity)</option>
          <option value="milp_v3">MILP v3 (pairwise capacity)</option>
          <option value="ga">GA (pymoo)</option>
        </select>
        <label>
          <input type="checkbox" name="hard_deadline">
          Hard deadline (makespan ≤ target)
        </label>
        <label>
          <input type="checkbox" name="tradeoff">
          Build trade-off curve (slow)
        </label>
      </fieldset>

      <button type="submit" id="run-btn">▶ Run optimizer</button>
    </form>

    <div style="margin-top: 16px;">
      <div class="status" id="status">Ready.</div>
    </div>
  </div>

  <div class="main">
    <div class="tabs">
      <button class="tab active" data-tab="summary">Summary</button>
      <button class="tab" data-tab="gantt">Gantt</button>
      <button class="tab" data-tab="tradeoff">Trade-off</button>
      <button class="tab" data-tab="crashlist">Crash plan</button>
      <button class="tab" data-tab="resload">Resource load</button>
    </div>

    <div id="summary" class="tab-panel active">
      <div class="summary" id="metrics"></div>
      <p style="color:#888; font-size:13px;">Run the optimizer to see results.</p>
    </div>
    <div id="gantt" class="tab-panel"><div id="gantt-chart"></div></div>
    <div id="tradeoff" class="tab-panel"><div id="tradeoff-chart"></div></div>
    <div id="crashlist" class="tab-panel"><div id="crash-content"></div></div>
    <div id="resload" class="tab-panel"><div id="resload-chart"></div></div>
  </div>
</div>

<script>
// Pre-computed trade-off curve (from optimization_results_v2.json)
window._staticTradeoff = {
  data: [{
    type: 'scatter', mode: 'lines+markers',
    name: 'Crash extra cost (pre-computed)',
    x: [379,384,389,394,399,404,409,414,419,424,429],
    y: [37517,29275,23053,17780,13080,10554,9033,7644,6402,5240,4064],
    hovertemplate: 'T=%{x}, cost=$%{y:,.0f}<extra></extra>',
    line: {color: '#636efa'},
    marker: {size: 8}
  }],
  layout: {
    title: 'Time-Cost Trade-off Curve (pre-computed, α=0.7, β=0.7)',
    xaxis: {title: 'Target Project End Day'},
    yaxis: {title: 'Crash Extra Cost ($)'},
    height: 500,
    annotations: [{
      text: 'Pre-computed with default parameters. Enable "Build trade-off curve" for live data.',
      xref: 'paper', yref: 'paper', x: 0.5, y: -0.15,
      showarrow: false, font: {size: 11, color: '#888'}
    }]
  }
};

// Tabs
document.querySelectorAll('.tab').forEach(btn => {
  btn.addEventListener('click', () => {
    document.querySelectorAll('.tab').forEach(b => b.classList.remove('active'));
    document.querySelectorAll('.tab-panel').forEach(p => p.classList.remove('active'));
    btn.classList.add('active');
    document.getElementById(btn.dataset.tab).classList.add('active');
    // Re-trigger plotly resize
    window.dispatchEvent(new Event('resize'));
  });
});

// Render static tradeoff on page load
if (window._staticTradeoff) {
  Plotly.newPlot('tradeoff-chart', window._staticTradeoff.data,
                 window._staticTradeoff.layout, {responsive: true});
}

const form = document.getElementById('opt-form');
const status = document.getElementById('status');
const runBtn = document.getElementById('run-btn');

form.addEventListener('submit', async (e) => {
  e.preventDefault();
  const fd = new FormData(form);
  const payload = {};
  for (const [k, v] of fd.entries()) payload[k] = v;
  payload.hard_deadline = fd.has('hard_deadline');
  payload.tradeoff = fd.has('tradeoff');

  runBtn.disabled = true;
  runBtn.textContent = 'Running...';
  status.textContent = 'Solving...';
  const t0 = performance.now();

  try {
    const res = await fetch('/run', {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify(payload)
    });
    const data = await res.json();
    const elapsed = ((performance.now() - t0) / 1000).toFixed(1);

    if (!data.success) {
      status.textContent = `FAILED (${elapsed}s)\n${data.error || data.status || ''}`;
      return;
    }

    status.textContent = `OK (${elapsed}s)\nSolver: ${data.solver}\nMakespan: ${data.makespan.toFixed(1)}d`;

    // Metrics
    const metrics = document.getElementById('metrics');
    metrics.innerHTML = '';
    const fmtMoney = v => '$' + (v||0).toLocaleString('en-US', {maximumFractionDigits: 0});
    const cards = [
      ['Solver', data.solver],
      ['Makespan', `${data.makespan.toFixed(1)} d`],
      ['Baseline cost', fmtMoney(data.baseline_cost)],
      ['Crash extra', fmtMoney(data.crash_cost)],
      ['Late', `${(data.I_late||0).toFixed(1)} d`],
      ['Early', `${(data.I_early||0).toFixed(1)} d`],
      ['Deadline term', fmtMoney(data.deadline_term||0)],
      ['Crashed tasks', Object.keys(data.crash_plan||{}).length],
    ];
    for (const [l, v] of cards) {
      const div = document.createElement('div');
      div.className = 'metric';
      div.innerHTML = `<div class="label">${l}</div><div class="value">${v}</div>`;
      metrics.appendChild(div);
    }

    // Gantt
    if (data.gantt_fig) {
      Plotly.newPlot('gantt-chart', data.gantt_fig.data, data.gantt_fig.layout,
                     {responsive: true});
    }

    // Tradeoff
    if (data.tradeoff_fig) {
      Plotly.newPlot('tradeoff-chart', data.tradeoff_fig.data, data.tradeoff_fig.layout,
                     {responsive: true});
    } else if (window._staticTradeoff) {
      Plotly.newPlot('tradeoff-chart', window._staticTradeoff.data,
                     window._staticTradeoff.layout, {responsive: true});
    } else {
      document.getElementById('tradeoff-chart').innerHTML =
        '<p style="color:#888;">Trade-off curve not computed. Enable the option or see the pre-computed curve above.</p>';
    }

    // Crash plan table
    const cc = document.getElementById('crash-content');
    if (data.crash_plan && Object.keys(data.crash_plan).length) {
      let html = '<table class="crash-table"><thead><tr>'
        + '<th>Task</th><th>Resource</th><th>x</th><th>τ (h)</th>'
        + '<th>+Cost</th><th>Days saved</th></tr></thead><tbody>';
      for (const [task, entries] of Object.entries(data.crash_plan)) {
        for (const e of entries) {
          html += `<tr><td>${task}</td><td>${e.resource}</td>`
            + `<td>${e.x}</td><td>${e.tau}</td>`
            + `<td>${fmtMoney(e.cost_delta)}</td>`
            + `<td>${e.duration_saved.toFixed(1)}</td></tr>`;
        }
      }
      html += '</tbody></table>';
      cc.innerHTML = html;
    } else {
      cc.innerHTML = '<p style="color:#888;">No crashing applied.</p>';
    }

    // Resource load
    if (data.resload_fig) {
      Plotly.newPlot('resload-chart', data.resload_fig.data, data.resload_fig.layout,
                     {responsive: true});
    }

  } catch (err) {
    status.textContent = `ERROR\n${err.message}`;
  } finally {
    runBtn.disabled = false;
    runBtn.textContent = '▶ Run optimizer';
  }
});
</script>
</body>
</html>
"""


# ---------------------- Plotly figure builders ----------------------

def _build_gantt_fig(tasks, result, current_day):
    from optimizer_core import day_to_date, build_active_set
    schedule = result["schedule"]
    crash_plan = result["crash_plan"]
    level2 = [(tid, t) for tid, t in tasks.items() if t.outline_level == 2]
    # Sort by BASELINE start day to preserve original schedule ordering
    sorted_tasks = sorted(level2, key=lambda x: x[1].start_day)
    task_names = [t.name for _, t in sorted_tasks]

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

        info = [f"<b>{t.name}</b>",
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
                y=[t.name, t.name],
                mode='lines',
                line=dict(color="#cccccc", width=14),
                name="Completed", legendgroup="Completed",
                showlegend=("Completed" not in legend_shown),
                hovertemplate=f"<b>{t.name}</b><br>Completed portion<extra></extra>",
            ))
            legend_shown.add("Completed")
            # Remaining / optimized portion: current_day → optimized finish (colored)
            data.append(dict(
                type='scatter',
                x=[cur_dt, end_dt],
                y=[t.name, t.name],
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
                y=[t.name, t.name],
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
            categoryorder="array", categoryarray=task_names,
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
    return render_template_string(PAGE)


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
