import os
import json
import numpy as np
import pandas as pd

def preprocess():
    base_dir = os.path.dirname(os.path.abspath(__file__))
    data_dir = os.path.join(base_dir, "../implementasi-cobb")
    out_dir = os.path.join(base_dir, "data")
    os.makedirs(out_dir, exist_ok=True)
    
    tasks = pd.read_csv(os.path.join(data_dir, "data_tasks.csv"))
    precedence = pd.read_csv(os.path.join(data_dir, "data_precedence.csv"))
    resources = pd.read_csv(os.path.join(data_dir, "data_assignments.csv"))
    
    alpha = 0.7
    beta = 0.7
    x_val = 2.0
    tau_val = 4.0
    overtime_mult = 1.5
    hours_per_day = 8
    
    activity_data = {}
    with open(os.path.join(base_dir, "../data/resource_capacity_v3.json"), "r") as f:
        resource_capacity = json.load(f)
        
    resource_requirements = {}
    
    # Predecessors parsing
    preds_dict = {}
    for _, row in precedence.iterrows():
        succ = str(row["task_id"]) if pd.notna(row["task_id"]) else None
        pred = str(row["pred_id"]) if pd.notna(row["pred_id"]) else None
        if not succ or not pred: continue
        preds_dict.setdefault(succ, []).append(pred)
        
    for _, row in resources.iterrows():
        res_id = str(row["resource_id"])
        # We already loaded resource_capacity from the base data
            
    # Process each task
    for _, row in tasks.iterrows():
        tid = str(row["task_id"])
        tname = row["task_name"]
        
        # Get assignments for this task
        task_res = resources[resources["task_id"] == row["task_id"]]
        
        if task_res.empty:
            activity_data[tid] = {
                "activity_name": tname,
                "activity_normal_time": 0,
                "activity_min_time": 0,
                "crash_cost": 0.0,
                "required_activities": preds_dict.get(tid, [])
            }
            resource_requirements[tid] = {}
            continue
            
        D_base_i = task_res["D_base"].max()
        
        cost_base = 0.0
        cost_crashed = 0.0
        D_crashed_i = 0.0
        
        reqs = {}
        
        for _, res_row in task_res.iterrows():
            D_base_ik = res_row["D_base"]
            U_ik = res_row["U_ik"]
            r_k = res_row["r_k_usd"]
            r_k_ot = r_k * overtime_mult
            
            res_id = str(res_row["resource_id"])
            reqs[res_id] = int(np.ceil(U_ik))
            
            D_crashed_ik = D_base_ik * (1.0 / x_val)**alpha * (8.0 / (8.0 + tau_val))**beta
            # Ensure it doesn't drop below 0.5 D_base_ik
            D_crashed_ik = max(D_crashed_ik, 0.5 * D_base_ik)
            
            D_crashed_i = max(D_crashed_i, D_crashed_ik)
            
            c_base_ik = D_base_ik * 1.0 * U_ik * (hours_per_day * r_k)
            c_crashed_ik = D_crashed_ik * x_val * U_ik * (hours_per_day * r_k + tau_val * r_k_ot)
            
            cost_base += c_base_ik
            cost_crashed += c_crashed_ik
            
        D_base_i_int = int(np.ceil(D_base_i))
        D_crashed_i_int = int(np.floor(D_crashed_i))
        
        delta_d = D_base_i - D_crashed_i
        delta_c = cost_crashed - cost_base
        
        crash_cost_per_day = 0.0
        if delta_d > 0.01:
            crash_cost_per_day = delta_c / delta_d
            
        activity_data[tid] = {
            "activity_name": tname,
            "activity_normal_time": D_base_i_int,
            "activity_min_time": D_crashed_i_int,
            "crash_cost": round(crash_cost_per_day, 2),
            "required_activities": preds_dict.get(tid, [])
        }
        resource_requirements[tid] = reqs
        
    # Write files
    with open(os.path.join(out_dir, "activity_data.json"), "w") as f:
        json.dump(activity_data, f, indent=2)
    with open(os.path.join(out_dir, "resource_capacity.json"), "w") as f:
        json.dump(resource_capacity, f, indent=2)
    with open(os.path.join(out_dir, "resource_requirements.json"), "w") as f:
        json.dump(resource_requirements, f, indent=2)
        
    print(f"Preprocessing completed. Files saved to {out_dir}")

if __name__ == "__main__":
    preprocess()
