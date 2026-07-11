import os
import sys
import matplotlib.pyplot as plt

base_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.append(os.path.join(base_dir, "../implementasi-base"))

from solver_base import (
    read_json,
    build_predecessors,
    infer_activity_states_without_state_file,
    SolveConfig,
    build_model_and_solve,
    build_reference_no_crash_schedule
)

def run_hybrid_multiobjective():
    data_dir = os.path.join(base_dir, "data")
    
    activity_data = read_json(os.path.join(data_dir, "activity_data.json"))
    resource_capacity = read_json(os.path.join(data_dir, "resource_capacity.json"))
    resource_requirements = read_json(os.path.join(data_dir, "resource_requirements.json"))
    
    predecessors, _ = build_predecessors(activity_data, [], True)
    
    current_day = 0
    states, _ = infer_activity_states_without_state_file(
        activity_data, resource_requirements, resource_capacity,
        predecessors, current_day, 60.0, 1
    )
    
    baseline = build_reference_no_crash_schedule(
        activity_data, resource_requirements, resource_capacity,
        predecessors, current_day, 60.0, 1
    )
    normal_duration = max(row["end"] for row in baseline.values())
    
    cfg_min = SolveConfig(
        target_end_date=None, current_day=current_day, time_limit=60.0,
        num_workers=1, auto_fix_paint_trim_cycle=True, remove_edges=[]
    )
    res_min = build_model_and_solve(
        activity_data, resource_requirements, resource_capacity,
        predecessors, states, cfg_min, mode="min_makespan"
    )
    max_crashed_duration = res_min.get("makespan", int(normal_duration) - 20)
    
    print(f"Normal Duration: {normal_duration}")
    print(f"Max Crashed Duration: {max_crashed_duration}")
    
    points = []
    
    for t in range(int(max_crashed_duration), int(normal_duration) + 1, max(1, (int(normal_duration) - int(max_crashed_duration)) // 10)):
        print(f"Solving for Target Deadline = {t}")
        cfg = SolveConfig(
            target_end_date=t, current_day=current_day, time_limit=30.0,
            num_workers=1, auto_fix_paint_trim_cycle=True, remove_edges=[]
        )
        res = build_model_and_solve(
            activity_data, resource_requirements, resource_capacity,
            predecessors, states, cfg, mode="cost_with_deadline"
        )
        if res["status"] in ["OPTIMAL", "FEASIBLE"]:
            cost = res.get("total_crash_cost", 0)
            makespan = res.get("makespan", t)
            points.append((makespan, cost))
            print(f"  -> Makespan: {makespan}, Cost: {cost}")
        else:
            print(f"  -> {res['status']}")
            
    if points:
        points.sort()
        ms = [p[0] for p in points]
        c = [p[1] for p in points]
        
        plt.figure(figsize=(8, 6))
        plt.plot(ms, c, marker='o', linestyle='-', color='g')
        plt.xlabel('Makespan (days)')
        plt.ylabel('Estimated Total Crash Cost ($)')
        plt.title('Time-Cost Pareto Front (Hybrid Model)')
        plt.grid(True)
        
        out_dir = os.path.join(base_dir, "../outputs/time-based")
        os.makedirs(out_dir, exist_ok=True)
        plt.savefig(os.path.join(out_dir, "hybrid_pareto_front.png"))
        print(f"Saved Pareto front plot to {os.path.join(out_dir, 'hybrid_pareto_front.png')}")

if __name__ == "__main__":
    run_hybrid_multiobjective()
