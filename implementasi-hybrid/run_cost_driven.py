import os
import sys

base_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.append(os.path.join(base_dir, "../implementasi-base"))

from solver_base import (
    read_json,
    build_predecessors,
    infer_activity_states_without_state_file,
    SolveConfig,
    build_model_and_solve,
    write_json,
    write_schedule_csv
)

def run_hybrid_cost_driven():
    data_dir = os.path.join(base_dir, "data")
    
    activity_data = read_json(os.path.join(data_dir, "activity_data.json"))
    resource_capacity = read_json(os.path.join(data_dir, "resource_capacity.json"))
    resource_requirements = read_json(os.path.join(data_dir, "resource_requirements.json"))
    
    predecessors, _ = build_predecessors(activity_data, [], True)
    
    current_day = 0
    target_end_date = 310
    
    states, _ = infer_activity_states_without_state_file(
        activity_data, resource_requirements, resource_capacity,
        predecessors, current_day, 60.0, 1
    )
    
    cfg = SolveConfig(
        target_end_date=target_end_date,
        current_day=current_day,
        time_limit=60.0,
        num_workers=1,
        auto_fix_paint_trim_cycle=True,
        remove_edges=[]
    )
    
    result = build_model_and_solve(
        activity_data,
        resource_requirements,
        resource_capacity,
        predecessors,
        states,
        cfg,
        mode="cost_with_deadline",
    )
    
    print("Hybrid Cost Driven Result:")
    print("Status:", result["status"])
    if "makespan" in result:
        print("Makespan:", result["makespan"])
    if "total_crash_cost" in result:
        print("Total crash cost:", result["total_crash_cost"])
        
    out_dir = os.path.join(base_dir, "../outputs")
    os.makedirs(out_dir, exist_ok=True)
    write_json(os.path.join(out_dir, "hybrid_cost_driven.json"), result)
    if "schedule" in result:
        write_schedule_csv(os.path.join(out_dir, "hybrid_cost_driven_schedule.csv"), result["schedule"])

if __name__ == "__main__":
    run_hybrid_cost_driven()
