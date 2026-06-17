import os
import sys
import pandas as pd
import numpy as np

# Adjust imports
base_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.append(base_dir)

from solver_base import (
    read_json, build_predecessors, infer_activity_states_without_state_file,
    SolveConfig, build_model_and_solve, build_reference_no_crash_schedule
)

def run_sensitivity_scenario_1():
    out_dir = os.path.join(base_dir, "../outputs/sensitivity_analysis")
    os.makedirs(out_dir, exist_ok=True)

    activity_data = read_json(os.path.join(base_dir, "../data/activity_data_v3.json"))
    resource_capacity = read_json(os.path.join(base_dir, "../data/resource_capacity_v3.json"))
    resource_req = read_json(os.path.join(base_dir, "../data/resource_requirements_v3.json"))

    current_day = 0
    predecessors, _ = build_predecessors(activity_data, [], True)
    states, _ = infer_activity_states_without_state_file(
        activity_data, resource_req, resource_capacity, predecessors, current_day, 60.0, 1
    )

    ref_schedule_dict = build_reference_no_crash_schedule(
        activity_data, resource_req, resource_capacity, predecessors, current_day, 60.0, 1
    )
    normal_makespan = max(t['end'] for t in ref_schedule_dict.values()) if ref_schedule_dict else 310

    print(f"Normal Makespan: {normal_makespan}")

    # To find max crashable, let's run a loop from normal_makespan down to 100 in steps of 2.
    res_tmax = []
    tmax_vals = np.arange(normal_makespan, 100, -2)
    
    print(f"Varying target_end_date from {normal_makespan} downwards...")
    for t in tmax_vals:
        cfg = SolveConfig(
            target_end_date=int(t),
            budget_limit=None, 
            c_late=1000.0,
            c_early=500.0,
            current_day=current_day,
            time_limit=15.0, # 15 seconds per run
            num_workers=1,
            auto_fix_paint_trim_cycle=True,
            remove_edges=[]
        )
        sol = build_model_and_solve(
            activity_data, resource_req, resource_capacity, predecessors, states, cfg, mode="cost_with_deadline"
        )
        if sol['status'] in ["OPTIMAL", "FEASIBLE"]:
            mk = sol.get('makespan', t)
            cost = sol.get('total_crash_cost', 0)
            res_tmax.append({"target_end_date": int(t), "makespan": mk, "total_crash_cost": cost})
            print(f"T_max={t}: Status={sol['status']}, Makespan={mk}, Cost={cost}")
        else:
            print(f"T_max={t}: Status={sol['status']} (Infeasible, hit max crashable limit)")
            break

    df = pd.DataFrame(res_tmax)
    out_csv = os.path.join(out_dir, "scenario_1_tmax.csv")
    df.to_csv(out_csv, index=False)
    print(f"Saved results to {out_csv}")

if __name__ == "__main__":
    run_sensitivity_scenario_1()
