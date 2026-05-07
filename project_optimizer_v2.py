"""
v2: MILP + GA crashing optimizer WITHOUT resource capacity constraints.
"""

import json
from datetime import datetime

from optimizer_core import (
    DEFAULTS, load_data, solve_ga,
    render_gantt_html, render_tradeoff_html, render_resource_load_html,
)
from solver_milp import solve_milp


def run(folder, base_date, current_day, target_day, params=None,
        output_prefix="v2", capacity=False):
    print(f"Loading data from {folder}...")
    tasks, resources, assignments = load_data(folder, base_date)
    horizon = max(t.finish_day for t in tasks.values())
    print(f"  {len(tasks)} tasks, {len(resources)} resources, "
          f"{len(assignments)} assignments. Baseline horizon: {horizon}d")

    print(f"\n[1/3] MILP ({'with capacity' if capacity else 'no capacity'})...")
    milp = solve_milp(tasks, resources, assignments, current_day, target_day,
                      params=params, capacity=capacity)
    if milp.get("success"):
        print(f"  makespan={milp['makespan']:.1f}d  baseline=${milp['baseline_cost']:,.0f}  "
              f"crash_extra=${milp['crash_cost']:,.0f}  "
              f"late={milp['I_late']:.1f}d  early={milp['I_early']:.1f}d  "
              f"deadline=${milp['deadline_term']:,.0f}")
        print(f"  crashed tasks: {len(milp['crash_plan'])}")
        render_gantt_html(tasks, milp, base_date, current_day,
                          output_file=f"gantt_{output_prefix}_milp.html")
        render_resource_load_html(tasks, resources, assignments, milp,
                                  base_date, current_day,
                                  output_file=f"resource_load_{output_prefix}_milp.html")
    else:
        print(f"  FAILED: {milp.get('status')}")

    print("\n[2/3] GA (pymoo)...")
    ga = solve_ga(tasks, resources, assignments, current_day, target_day,
                  params=params)
    print(f"  makespan={ga['makespan']:.1f}d  baseline=${ga['baseline_cost']:,.0f}  "
          f"crash_extra=${ga['crash_cost']:,.0f}")
    print(f"  crashed tasks: {len(ga['crash_plan'])}")
    render_gantt_html(tasks, ga, base_date, current_day,
                      output_file=f"gantt_{output_prefix}_ga.html")

    print("\n[3/3] Trade-off curve (MILP, hard deadline)...")
    probe = solve_milp(tasks, resources, assignments, current_day,
                       current_day, params=params, capacity=capacity)
    min_make = int(probe['makespan']) if probe.get('success') else target_day
    base_make = int(milp['makespan']) if milp.get('success') else horizon
    lo = min_make
    hi = max(base_make + 30, target_day + 30)
    step = max(1, (hi - lo) // 10)

    curve = []
    for tgt in range(lo, hi + 1, step):
        r = solve_milp(tasks, resources, assignments, current_day, tgt,
                       params=params, capacity=capacity, hard_deadline=True)
        if r.get("success"):
            curve.append(r)
            print(f"  T={tgt}: extra=${r['crash_cost']:,.0f}, makespan={r['makespan']:.1f}")
    render_tradeoff_html(curve, output_file=f"tradeoff_{output_prefix}.html")

    out = {
        "config": {**(params or DEFAULTS), "current_day": current_day,
                   "target_day": target_day, "capacity": capacity},
        "milp": _strip(milp) if milp.get("success") else milp,
        "ga": _strip(ga),
        "tradeoff_curve": [
            {"target_day": r["target_day"], "crash_cost": r["crash_cost"],
             "makespan": r["makespan"]}
            for r in curve
        ],
    }
    out_path = f"optimization_results_{output_prefix}.json"
    with open(out_path, 'w') as fh:
        json.dump(out, fh, indent=2, default=str)
    print(f"\nResults -> {out_path}")
    return out


def _strip(res):
    return {k: v for k, v in res.items() if k != "schedule"}


def main():
    folder = "/Users/macintoshhd/Documents/Adiel/pemod/Pemod-Sandbox/Schedules_CSV"
    base_date = datetime(2023, 5, 1)

    print("=" * 60)
    print("PROJECT CRASHING OPTIMIZER v2 (no resource capacity)")
    print("=" * 60)

    horizon = 480
    while True:
        try:
            cd = int(input(f"\nCurrent project day [1..{horizon}]: "))
            if 1 <= cd <= horizon:
                break
        except ValueError:
            pass
    while True:
        try:
            td = int(input(f"Target project end day [{cd}..{horizon}]: "))
            if cd <= td <= horizon:
                break
        except ValueError:
            pass

    run(folder, base_date, cd, td, output_prefix="v2", capacity=False)


if __name__ == "__main__":
    main()
