"""
Shared optimizer core: data classes, parsing, Cobb-Douglas math, GA solver,
and Plotly HTML visualization. Imported by v2/v3 CLI scripts and the webapp.
"""

import csv
import os
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timedelta

import numpy as np
import plotly.graph_objects as go
from pymoo.algorithms.soo.nonconvex.ga import GA
from pymoo.core.problem import ElementwiseProblem
from pymoo.operators.crossover.sbx import SBX
from pymoo.operators.mutation.pm import PM
from pymoo.optimize import minimize


# ============== Data Classes ==============

@dataclass
class Task:
    id: int
    name: str
    duration: int
    start_day: int
    finish_day: int
    predecessors: list = field(default_factory=list)
    outline_level: int = 2


@dataclass
class Resource:
    id: int
    name: str
    rate: float = 50.0
    max_units: float = 1.0  # capacity (typically 1.0 = 100%)


@dataclass
class Assignment:
    task_id: int
    resource_id: int
    work_hours: float
    units_percent: float
    percent_complete: float = 0.0


# ============== Defaults ==============

DEFAULTS = {
    "alpha": 0.7,
    "beta": 0.7,
    "ot_mult": 1.5,
    "c_late": 5000.0,
    "c_early": 2000.0,
    "x_grid": [1.0, 1.25, 1.5, 1.75, 2.0],
    "tau_grid": [0, 1, 2, 3, 4],
}


# ============== Date helpers ==============

def parse_date_to_day(date_str, base_date):
    try:
        dt = datetime.strptime(date_str.strip(), "%d %B %Y %I:%M %p")
        return (dt - base_date).days + 1
    except Exception:
        return 1


def day_to_date(day, base_date):
    return base_date + timedelta(days=day - 1)


def parse_duration(s):
    s = s.lower().strip()
    if 'wk' in s:
        return int(s.replace('wks', '').replace('wk', '').strip()) * 5
    return int(s.replace('days', '').replace('day', '').strip())


def parse_predecessors(s):
    out = []
    for p in (s or '').split(','):
        p = p.strip()
        if not p:
            continue
        head = ''
        for ch in p:
            if ch.isdigit() or (ch == '-' and not head):
                head += ch
            else:
                break
        if head:
            try:
                out.append(int(head))
            except ValueError:
                pass
    return out


# ============== Loader ==============

def load_data(folder, base_date):
    tasks = {}
    with open(os.path.join(folder, 'Task_Table.csv'), encoding='utf-8') as f:
        for row in csv.DictReader(f):
            tid = int(row['ID'])
            tasks[tid] = Task(
                id=tid, name=row['Name'],
                duration=parse_duration(row['Duration']),
                start_day=parse_date_to_day(row['Start'], base_date),
                finish_day=parse_date_to_day(row['Finish'], base_date),
                predecessors=parse_predecessors(row.get('Predecessors', '')),
                outline_level=int(row.get('Outline Level', 2)),
            )

    resources = {}
    with open(os.path.join(folder, 'Resource_Table.csv'), encoding='utf-8') as f:
        for row in csv.DictReader(f):
            rid = int(row['ID'])
            rate_s = row.get('Standard Rate', '$50.00/h').replace('$', '').replace('/h', '').strip()
            mu_s = row.get('Max Units', '100%').replace('%', '').strip()
            resources[rid] = Resource(
                id=rid, name=row['Name'],
                rate=float(rate_s) if rate_s else 50.0,
                max_units=float(mu_s) / 100.0 if mu_s else 1.0,
            )

    name_to_task = {t.name: t.id for t in tasks.values()}
    name_to_res = {r.name: r.id for r in resources.values()}

    assignments = []
    with open(os.path.join(folder, 'Assignment_Table.csv'), encoding='utf-8') as f:
        for row in csv.DictReader(f):
            tid = name_to_task.get(row['Task Name'])
            rid = name_to_res.get(row['Resource Name'])
            if tid is None or rid is None:
                continue
            work = float(row['Work'].replace('h', '').strip())
            units = float(row['Units'].replace('%', '').strip()) / 100.0
            pct = float(row.get('% Work Complete', '0').replace('%', '').strip()) / 100.0
            assignments.append(Assignment(tid, rid, work, units, pct))

    return tasks, resources, assignments


# ============== Cobb-Douglas math ==============

def mode_dur_factor(x, tau, alpha, beta):
    return (1.0 / (x ** alpha)) * ((8.0 / (8.0 + tau)) ** beta)


def mode_cost_per_assignment(W, r_k, x, tau, alpha, beta, ot_mult):
    r_ot = ot_mult * r_k
    return W * (x ** (1 - alpha)) * ((8.0 / (8.0 + tau)) ** beta) * (r_k + (tau / 8.0) * r_ot)


def build_active_set(tasks, current_day):
    completed = {tid for tid, t in tasks.items() if t.finish_day < current_day}
    active = {tid for tid, t in tasks.items()
              if t.start_day <= current_day <= t.finish_day}
    return completed, active


def compute_baseline_duration_per_assignment(a, tasks):
    if a.units_percent <= 0:
        return tasks[a.task_id].duration
    return max(1.0, a.work_hours / (8.0 * a.units_percent))


def infer_remaining_fraction(a, tasks, current_day):
    """
    Fraction of work remaining for an active task.
    Uses percent_complete from data if it is explicitly set (> 0).
    Falls back to elapsed-calendar-time proportion when percent_complete == 0,
    because MS Project often exports 0 for all tasks even when work is in progress.
    """
    if a.percent_complete > 0:
        return max(0.05, 1.0 - a.percent_complete)
    t = tasks[a.task_id]
    span = max(1, t.finish_day - t.start_day)
    elapsed = max(0, current_day - t.start_day)
    return max(0.05, 1.0 - elapsed / span)


def effective_W(a, in_active, remaining_frac=None):
    """Remaining work hours for active task; baseline otherwise."""
    if not in_active:
        return a.work_hours
    frac = remaining_frac if remaining_frac is not None else max(0.05, 1.0 - a.percent_complete)
    return a.work_hours * frac


# ============== GA Solver ==============

class CrashingProblem(ElementwiseProblem):
    def __init__(self, tasks, resources, crash_assignments,
                 current_day, target_day, completed, active, params):
        self.tasks = tasks
        self.resources = resources
        self.crash_assignments = crash_assignments
        self.current_day = current_day
        self.target_day = target_day
        self.completed = completed
        self.active = active
        self.params = params

        n = len(crash_assignments)
        xl = np.concatenate([np.ones(n), np.zeros(n)])
        xu = np.concatenate([2.0 * np.ones(n), 4.0 * np.ones(n)])
        super().__init__(n_var=2 * n, n_obj=1, n_constr=0, xl=xl, xu=xu)

    def _evaluate(self, X, out, *args, **kwargs):
        n = len(self.crash_assignments)
        xs, taus = X[:n], X[n:]
        p = self.params

        per_assign = defaultdict(list)
        cost_total = 0.0
        for i, a in enumerate(self.crash_assignments):
            x_i, t_i = xs[i], taus[i]
            d_base = compute_baseline_duration_per_assignment(a, self.tasks)
            in_active = a.task_id in self.active
            if in_active:
                rem = infer_remaining_fraction(a, self.tasks, self.current_day)
                d_base *= rem
            else:
                rem = None
            per_assign[a.task_id].append(d_base * mode_dur_factor(x_i, t_i, p['alpha'], p['beta']))
            r_k = self.resources[a.resource_id].rate
            W = effective_W(a, in_active, rem)
            cost_total += mode_cost_per_assignment(W, r_k, x_i, t_i,
                                                    p['alpha'], p['beta'], p['ot_mult'])

        task_dur = {}
        for tid, durs in per_assign.items():
            task_dur[tid] = max(max(durs), 1.0)
        for tid, t in self.tasks.items():
            if t.outline_level != 2 and tid not in task_dur:
                task_dur[tid] = 0.0

        s, f = {}, {}
        for tid in sorted(self.tasks.keys()):
            t = self.tasks[tid]
            if tid in self.completed:
                s[tid], f[tid] = t.start_day, t.finish_day
                continue
            pred_finish = max([f.get(pp, 0) for pp in t.predecessors if pp in self.tasks] + [0])
            if tid in self.active:
                s[tid] = self.current_day
            else:
                s[tid] = max(self.current_day, pred_finish + 1)
            d = task_dur.get(tid, max(1, t.duration) if t.outline_level == 2 else 0)
            f[tid] = s[tid] + d

        makespan = max(f.values())
        delta = makespan - self.target_day
        late = max(0.0, delta)
        early = max(0.0, -delta)

        out["F"] = cost_total + p['c_late'] * late - p['c_early'] * early


def solve_ga(tasks, resources, assignments, current_day, target_day,
             params=None, pop_size=80, n_gen=120, seed=1):
    p = {**DEFAULTS, **(params or {})}
    completed, active = build_active_set(tasks, current_day)
    level2 = {tid for tid, t in tasks.items() if t.outline_level == 2}
    crash_assignments = [a for a in assignments
                         if a.task_id in level2 and a.task_id not in completed]

    problem = CrashingProblem(tasks, resources, crash_assignments,
                              current_day, target_day, completed, active, p)
    algorithm = GA(pop_size=pop_size,
                   crossover=SBX(prob=0.9, eta=15),
                   mutation=PM(eta=20),
                   eliminate_duplicates=True)
    res = minimize(problem, algorithm, ('n_gen', n_gen), seed=seed, verbose=False)

    n = len(crash_assignments)
    xs = res.X[:n]
    taus = np.clip(np.round(res.X[n:]), 0, 4).astype(int)

    crash_plan = {}
    total_baseline = 0.0
    total_delta = 0.0
    per_assign_dur = defaultdict(list)
    for i, a in enumerate(crash_assignments):
        x_i = float(xs[i])
        t_i = int(taus[i])
        d_base = compute_baseline_duration_per_assignment(a, tasks)
        in_active = a.task_id in active
        if in_active:
            rem = infer_remaining_fraction(a, tasks, current_day)
            d_base *= rem
        else:
            rem = None
        per_assign_dur[a.task_id].append(d_base * mode_dur_factor(x_i, t_i, p['alpha'], p['beta']))
        r_k = resources[a.resource_id].rate
        W = effective_W(a, in_active, rem)
        c_chosen = mode_cost_per_assignment(W, r_k, x_i, t_i, p['alpha'], p['beta'], p['ot_mult'])
        c_base = mode_cost_per_assignment(W, r_k, 1.0, 0, p['alpha'], p['beta'], p['ot_mult'])
        total_baseline += c_base
        total_delta += (c_chosen - c_base)
        if x_i > 1.05 or t_i > 0:
            crash_plan.setdefault(tasks[a.task_id].name, []).append({
                "resource": resources[a.resource_id].name,
                "x": round(x_i, 3), "tau": t_i,
                "cost_delta": round(c_chosen - c_base, 2),
                "duration_saved": round(d_base * (1 - mode_dur_factor(x_i, t_i, p['alpha'], p['beta'])), 2),
            })

    s, f = {}, {}
    for tid in sorted(tasks.keys()):
        t = tasks[tid]
        if tid in completed:
            s[tid], f[tid] = t.start_day, t.finish_day
            continue
        pred_finish = max([f.get(pp, 0) for pp in t.predecessors if pp in tasks] + [0])
        if tid in active:
            s[tid] = current_day
        else:
            s[tid] = max(current_day, pred_finish + 1)
        if t.outline_level == 2:
            d = max(per_assign_dur.get(tid, [t.duration]) or [t.duration])
            f[tid] = s[tid] + max(d, 1)
        else:
            f[tid] = s[tid]
    makespan = max(f.values())

    return {
        "success": True,
        "solver": "GA/pymoo",
        "objective": float(res.F[0]) if hasattr(res.F, '__len__') else float(res.F),
        "baseline_cost": round(total_baseline, 2),
        "crash_cost": round(total_delta, 2),
        "makespan": makespan,
        "target_day": target_day,
        "crash_plan": crash_plan,
        "schedule": {tid: (s[tid], f[tid]) for tid in tasks},
    }


# ============== Plotly HTML Visualization ==============

def render_gantt_html(tasks, result, base_date, current_day, output_file=None,
                      title=None):
    """
    Gantt chart showing optimized schedule. Tasks sorted by baseline start day.
    Crashed tasks colored red, active normal blue, completed grey.
    Returns HTML string. If output_file given, writes to disk too.
    """
    schedule = result["schedule"]
    crash_plan = result["crash_plan"]
    level2 = [(tid, t) for tid, t in tasks.items() if t.outline_level == 2]
    sorted_tasks = sorted(level2, key=lambda x: x[1].start_day)
    task_names = [t.name for _, t in sorted_tasks]

    fig = go.Figure()
    legend_shown = set()

    # Determine which tasks are active (in-progress at current_day)
    _, active_set = build_active_set(tasks, current_day)

    for tid, t in sorted_tasks:
        sv, fv = schedule.get(tid, (t.start_day, t.finish_day))
        sv, fv = float(sv), float(fv)
        end_dt = day_to_date(int(round(fv)), base_date)
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
        # but visually we must show the bar from the original baseline start date.
        visual_start_day = t.start_day if is_active else int(round(sv))
        start_dt = day_to_date(visual_start_day, base_date)

        info = [f"<b>{t.name}</b>",
                f"Started Day {visual_start_day} → Finishes Day {int(fv)} "
                f"(remaining: {fv - current_day:.1f}d)" if is_active
                else f"Day {visual_start_day} → Day {int(fv)} ({fv - visual_start_day:.1f}d)"]
        if is_crashed:
            info.append("<br><b>CRASHED:</b>")
            for entry in crash_plan[t.name]:
                info.append(
                    f"&nbsp;&nbsp;{entry['resource']}: "
                    f"x={entry['x']}, τ={entry['tau']}h, "
                    f"+${entry['cost_delta']:,.0f}, "
                    f"saved={entry['duration_saved']:.1f}d"
                )
        text = "<br>".join(info)

        # For active tasks: draw completed portion (original start → current_day) in grey,
        # then the remaining/optimized portion (current_day → fv) in the task color.
        if is_active and not is_done:
            cur_dt = day_to_date(current_day, base_date)
            # Completed segment
            fig.add_trace(go.Scatter(
                x=[start_dt, cur_dt], y=[t.name, t.name],
                mode='lines', line=dict(color="#cccccc", width=14),
                name="Completed", legendgroup="Completed",
                showlegend=("Completed" not in legend_shown),
                hovertemplate=f"<b>{t.name}</b><br>Completed portion<extra></extra>",
            ))
            legend_shown.add("Completed")
            # Remaining segment
            fig.add_trace(go.Scatter(
                x=[cur_dt, end_dt], y=[t.name, t.name],
                mode='lines', line=dict(color=color, width=14),
                name=group, legendgroup=group,
                showlegend=(group not in legend_shown),
                hovertemplate=text + "<extra></extra>",
            ))
            legend_shown.add(group)
        else:
            fig.add_trace(go.Scatter(
                x=[start_dt, end_dt], y=[t.name, t.name],
                mode='lines', line=dict(color=color, width=14),
                name=group, legendgroup=group,
                showlegend=(group not in legend_shown),
                hovertemplate=text + "<extra></extra>",
            ))
            legend_shown.add(group)

    cur_dt = day_to_date(current_day, base_date)
    target_dt = day_to_date(result["target_day"], base_date)
    fig.add_shape(type="line", x0=cur_dt, x1=cur_dt, y0=0, y1=1, yref="paper",
                  line=dict(color="black", width=2, dash="dash"))
    fig.add_shape(type="line", x0=target_dt, x1=target_dt, y0=0, y1=1, yref="paper",
                  line=dict(color="blue", width=2, dash="dot"))
    fig.add_annotation(x=cur_dt, y=1.02, yref="paper", showarrow=False,
                       text=f"Current Day {current_day}", font=dict(color="black"))
    fig.add_annotation(x=target_dt, y=-0.05, yref="paper", showarrow=False,
                       text=f"Target Day {result['target_day']}", font=dict(color="blue"))

    title = title or (f"{result['solver']} | makespan={result['makespan']:.1f}d, "
                      f"crash_extra=${result['crash_cost']:,.0f}")
    fig.update_layout(
        title=title,
        xaxis_title="Date",
        yaxis_title="Task",
        height=max(600, 18 * len(sorted_tasks)),
        hovermode="closest",
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
        margin=dict(l=300, r=40, t=80, b=60),
    )
    fig.update_yaxes(autorange="reversed", tickfont=dict(size=9),
                     categoryorder="array", categoryarray=task_names)
    fig.update_xaxes(type="date")

    html = fig.to_html(include_plotlyjs='cdn', full_html=True)
    if output_file:
        with open(output_file, 'w') as fh:
            fh.write(html)
    return html


def render_tradeoff_html(curve, output_file=None):
    targets = [r["target_day"] for r in curve if r.get("success")]
    costs = [r["crash_cost"] for r in curve if r.get("success")]
    makes = [r["makespan"] for r in curve if r.get("success")]
    fig = go.Figure()
    fig.add_trace(go.Scatter(x=targets, y=costs, mode='lines+markers',
                             name='Crash extra cost',
                             hovertemplate="T=%{x}, cost=$%{y:,.0f}<extra></extra>"))
    fig.update_layout(
        title="Time-Cost Trade-off Curve",
        xaxis_title="Target Project End Day",
        yaxis_title="Crash Extra Cost ($)",
        height=500,
    )
    html = fig.to_html(include_plotlyjs='cdn', full_html=True)
    if output_file:
        with open(output_file, 'w') as fh:
            fh.write(html)
    return html


def render_resource_load_html(tasks, resources, assignments, result,
                              base_date, current_day, output_file=None,
                              title=None):
    """Stacked daily load per resource — useful to inspect capacity violations."""
    schedule = result["schedule"]
    crash_plan = result["crash_plan"]

    # Compute x_a per assignment from crash_plan (for marking crashed contributions)
    x_per_assignment = {}
    for tname, entries in crash_plan.items():
        for e in entries:
            x_per_assignment[(tname, e["resource"])] = e.get("x", 1.0)

    horizon = max(int(f) for s, f in schedule.values())
    days = list(range(1, horizon + 1))
    # Per resource: daily load array
    by_resource = defaultdict(lambda: np.zeros(horizon + 1))
    for a in assignments:
        if a.task_id not in schedule:
            continue
        s_d, f_d = schedule[a.task_id]
        s_d, f_d = int(round(s_d)), int(round(f_d))
        x_eff = x_per_assignment.get((tasks[a.task_id].name, resources[a.resource_id].name), 1.0)
        load = a.units_percent * x_eff
        for t in range(max(1, s_d), min(horizon, f_d) + 1):
            by_resource[a.resource_id][t] += load

    fig = go.Figure()
    for rid, loads in sorted(by_resource.items(), key=lambda kv: -kv[1].sum()):
        if loads.sum() < 0.5:
            continue
        cap = resources[rid].max_units
        x_dates = [day_to_date(t, base_date) for t in days]
        y_vals = loads[1:horizon + 1]
        fig.add_trace(go.Scatter(
            x=x_dates, y=y_vals, mode='lines',
            name=resources[rid].name,
            hovertemplate=f"{resources[rid].name}<br>Day %{{x}}: %{{y:.2f}} (cap={cap})<extra></extra>",
        ))

    fig.update_layout(
        title=title or "Daily resource load (post-crashing)",
        xaxis_title="Date",
        yaxis_title="Units",
        height=500,
        legend=dict(font=dict(size=9)),
    )
    fig.add_shape(type="line", x0=0, x1=1, xref="paper", y0=1.0, y1=1.0,
                  line=dict(color="red", dash="dash"))
    html = fig.to_html(include_plotlyjs='cdn', full_html=True)
    if output_file:
        with open(output_file, 'w') as fh:
            fh.write(html)
    return html
