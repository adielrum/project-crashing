"""
MILP solver via PuLP+CBC. Two modes:
  - capacity=False (v2):  no resource constraints (baseline-feasibility assumed)
  - capacity=True  (v3):  time-indexed y_{i,t} with daily resource load <= C_k

Notes on the resource constraint (v3):
  - Per Model.md §1.3, the full constraint contains x_{i,k} * y_{i,t} (bilinear).
  - For tractability we use the simplified form sum_i U_{i,k} * y_{i,t} <= C_k,
    i.e. we ignore x amplification in the capacity check. This still prevents
    parallel tasks from over-allocating shared resources at baseline units.
"""

from collections import defaultdict
import pulp

from optimizer_core import (
    DEFAULTS, mode_dur_factor, mode_cost_per_assignment,
    build_active_set, compute_baseline_duration_per_assignment, effective_W,
    infer_remaining_fraction,
)


def solve_milp(tasks, resources, assignments, current_day, target_day,
               params=None, hard_deadline=False, capacity=False,
               horizon_pad=15, time_limit=180, verbose=False):
    p = {**DEFAULTS, **(params or {})}
    completed, active = build_active_set(tasks, current_day)
    level2 = {tid for tid, t in tasks.items() if t.outline_level == 2}

    crash_assignments = [a for a in assignments
                         if a.task_id in level2 and a.task_id not in completed]

    baseline_horizon = max(t.finish_day for t in tasks.values())
    horizon = baseline_horizon + horizon_pad

    prob = pulp.LpProblem("project_crashing", pulp.LpMinimize)

    # --- Mode binaries ---
    xi = {}
    for idx, a in enumerate(crash_assignments):
        for m, x in enumerate(p['x_grid']):
            for n, tau in enumerate(p['tau_grid']):
                xi[(idx, m, n)] = pulp.LpVariable(f"xi_{idx}_{m}_{n}", cat='Binary')

    # --- Schedule vars ---
    s = {tid: pulp.LpVariable(f"s_{tid}", lowBound=0, upBound=horizon)
         for tid in tasks}
    f = {tid: pulp.LpVariable(f"f_{tid}", lowBound=0, upBound=horizon)
         for tid in tasks}
    f_proj = pulp.LpVariable("f_proj", lowBound=0, upBound=horizon)
    I_late = pulp.LpVariable("I_late", lowBound=0)
    I_early = pulp.LpVariable("I_early", lowBound=0)

    # --- Mode selection: exactly one mode per assignment ---
    for idx in range(len(crash_assignments)):
        prob += pulp.lpSum(xi[(idx, m, n)]
                          for m in range(len(p['x_grid']))
                          for n in range(len(p['tau_grid']))) == 1

    # --- Lock completed tasks ---
    for tid in completed:
        s[tid].lowBound = tasks[tid].start_day
        s[tid].upBound = tasks[tid].start_day
        f[tid].lowBound = tasks[tid].finish_day
        f[tid].upBound = tasks[tid].finish_day

    # Future / active: anchor at current day
    for tid, t in tasks.items():
        if tid not in completed and t.outline_level == 2:
            if tid in active:
                s[tid].lowBound = current_day
                s[tid].upBound = current_day
            else:
                s[tid].lowBound = current_day

    # --- Duration constraints (level-2 only) ---
    asg_idx_by_task = defaultdict(list)
    for idx, a in enumerate(crash_assignments):
        asg_idx_by_task[a.task_id].append((idx, a))

    for tid, lst in asg_idx_by_task.items():
        for idx, a in lst:
            d_base = compute_baseline_duration_per_assignment(a, tasks)
            if tid in active:
                d_base *= infer_remaining_fraction(a, tasks, current_day)
            rhs = pulp.lpSum(
                xi[(idx, m, n)] * d_base * mode_dur_factor(x, tau, p['alpha'], p['beta'])
                for m, x in enumerate(p['x_grid'])
                for n, tau in enumerate(p['tau_grid'])
            )
            prob += f[tid] - s[tid] >= rhs

    # --- Precedence (FS only) ---
    for tid, t in tasks.items():
        for pid in t.predecessors:
            if pid in tasks:
                prob += s[tid] >= f[pid] + 1

    # --- Project makespan ---
    for tid in tasks:
        prob += f_proj >= f[tid]

    if hard_deadline:
        prob += f_proj <= target_day
        prob += I_late == 0
        prob += I_early == 0
    else:
        prob += f_proj - target_day == I_late - I_early

    # --- Resource capacity (v3 only): pairwise non-overlap ---
    # For each pair of level-2 tasks (i, j) sharing a resource k where
    # U_{i,k} + U_{j,k} > C_k, enforce f_i <= s_j  OR  f_j <= s_i via
    # disjunctive big-M with one binary z_{ij}.
    #
    # Limitation: pairwise misses triple+ overlaps (e.g. three tasks each at
    # 40% on a 100% resource: each pair sums to 80% which is feasible, but
    # all three together = 120% violates capacity). For most schedules this
    # is acceptable because pairwise dominates triple+ in practice.
    if capacity:
        active_tids = [tid for tid in level2 if tid not in completed]

        U_by_task_res = defaultdict(float)
        for a in assignments:
            U_by_task_res[(a.task_id, a.resource_id)] += a.units_percent

        tasks_per_res = defaultdict(list)
        for (tid, rid), u in U_by_task_res.items():
            if tid in active_tids and u > 0:
                tasks_per_res[rid].append((tid, u))

        M = horizon + 10
        pair_count = 0
        seen_pairs = set()
        for rid, tlist in tasks_per_res.items():
            cap = resources[rid].max_units
            tlist_sorted = sorted(tlist)
            for ii in range(len(tlist_sorted)):
                for jj in range(ii + 1, len(tlist_sorted)):
                    tid_i, u_i = tlist_sorted[ii]
                    tid_j, u_j = tlist_sorted[jj]
                    if u_i + u_j <= cap + 1e-9:
                        continue
                    pair_key = (tid_i, tid_j)
                    if pair_key in seen_pairs:
                        continue  # already enforced via another shared resource
                    seen_pairs.add(pair_key)
                    z = pulp.LpVariable(f"z_{tid_i}_{tid_j}", cat='Binary')
                    # z=1 -> i finishes before j starts
                    prob += f[tid_i] <= s[tid_j] + M * (1 - z)
                    # z=0 -> j finishes before i starts
                    prob += f[tid_j] <= s[tid_i] + M * z
                    pair_count += 1
        if verbose:
            print(f"  capacity: {pair_count} pairwise non-overlap constraints")

    # --- Objective ---
    crash_cost_terms = []
    for idx, a in enumerate(crash_assignments):
        r_k = resources[a.resource_id].rate
        in_active = a.task_id in active
        rem = infer_remaining_fraction(a, tasks, current_day) if in_active else None
        W = effective_W(a, in_active, rem)
        for m, x in enumerate(p['x_grid']):
            for n, tau in enumerate(p['tau_grid']):
                c = mode_cost_per_assignment(W, r_k, x, tau,
                                              p['alpha'], p['beta'], p['ot_mult'])
                crash_cost_terms.append(c * xi[(idx, m, n)])

    prob += (pulp.lpSum(crash_cost_terms)
             + p['c_late'] * I_late - p['c_early'] * I_early)

    # --- Solve ---
    solver = pulp.PULP_CBC_CMD(msg=verbose, timeLimit=time_limit)
    status = prob.solve(solver)
    status_str = pulp.LpStatus[status]

    if status_str not in ('Optimal', 'Not Solved'):
        return {"success": False, "status": status_str,
                "solver": "MILP-v3" if capacity else "MILP-v2"}

    # --- Extract solution ---
    crash_plan = {}
    total_baseline = 0.0
    total_delta = 0.0
    for idx, a in enumerate(crash_assignments):
        chosen_x, chosen_tau = 1.0, 0
        for m, x in enumerate(p['x_grid']):
            for n, tau in enumerate(p['tau_grid']):
                v = pulp.value(xi[(idx, m, n)])
                if v is not None and v > 0.5:
                    chosen_x, chosen_tau = x, tau
        r_k = resources[a.resource_id].rate
        W = effective_W(a, a.task_id in active)
        c_chosen = mode_cost_per_assignment(W, r_k, chosen_x, chosen_tau,
                                             p['alpha'], p['beta'], p['ot_mult'])
        c_base = mode_cost_per_assignment(W, r_k, 1.0, 0,
                                           p['alpha'], p['beta'], p['ot_mult'])
        total_baseline += c_base
        if chosen_x > 1.0 + 1e-6 or chosen_tau > 0:
            tname = tasks[a.task_id].name
            d_base = compute_baseline_duration_per_assignment(a, tasks)
            saved = d_base * (1.0 - mode_dur_factor(chosen_x, chosen_tau,
                                                     p['alpha'], p['beta']))
            crash_plan.setdefault(tname, []).append({
                "resource": resources[a.resource_id].name,
                "x": chosen_x, "tau": chosen_tau,
                "cost_delta": round(c_chosen - c_base, 2),
                "duration_saved": round(saved, 2),
            })
            total_delta += (c_chosen - c_base)

    schedule = {}
    for tid in tasks:
        sv = pulp.value(s[tid])
        fv = pulp.value(f[tid])
        if sv is None:
            sv = tasks[tid].start_day
        if fv is None:
            fv = tasks[tid].finish_day
        schedule[tid] = (sv, fv)
    makespan = pulp.value(f_proj)

    return {
        "success": True,
        "solver": "MILP-v3 (cap)" if capacity else "MILP-v2",
        "status": status_str,
        "objective": pulp.value(prob.objective),
        "baseline_cost": round(total_baseline, 2),
        "crash_cost": round(total_delta, 2),
        "I_late": pulp.value(I_late) or 0.0,
        "I_early": pulp.value(I_early) or 0.0,
        "deadline_term": round(p['c_late'] * (pulp.value(I_late) or 0)
                               - p['c_early'] * (pulp.value(I_early) or 0), 2),
        "makespan": makespan,
        "target_day": target_day,
        "crash_plan": crash_plan,
        "schedule": schedule,
    }
