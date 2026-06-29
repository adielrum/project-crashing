import os
import json
import numpy as np
import pandas as pd

def preprocess(tasks_df=None, precedence_df=None, resources_df=None, resource_capacity=None, alpha=0.7, beta=0.7):
    base_dir = os.path.dirname(os.path.abspath(__file__))
    data_dir = os.path.join(base_dir, "../implementasi-cobb")
    out_dir = os.path.join(base_dir, "data")
    os.makedirs(out_dir, exist_ok=True)
    
    tasks = tasks_df if tasks_df is not None else pd.read_csv(os.path.join(data_dir, "data_tasks.csv"))
    precedence = precedence_df if precedence_df is not None else pd.read_csv(os.path.join(data_dir, "data_precedence.csv"))
    resources = resources_df if resources_df is not None else pd.read_csv(os.path.join(data_dir, "data_assignments.csv"))
    
    x_val = 2.0
    tau_val = 4.0
    overtime_mult = 1.5
    hours_per_day = 8
    
    activity_data = {}
    if resource_capacity is None:
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
                "activity_base_cost": 0.0,
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
            W_ik = res_row["W_ik"]
            U_ik = res_row["U_ik"]
            r_k = res_row["r_k_usd"]
            r_k_ot = r_k * overtime_mult
            
            res_id = str(res_row["resource_id"])
            reqs[res_id] = int(np.ceil(U_ik))
            
            D_crashed_ik = D_base_ik * (1.0 / x_val)**alpha * (8.0 / (8.0 + tau_val))**beta
            # Ensure it doesn't drop below 0.5 D_base_ik
            D_crashed_ik = max(D_crashed_ik, 0.5 * D_base_ik)
            
            D_crashed_i = max(D_crashed_i, D_crashed_ik)
            
            # Cobb-Douglas cost formula (matches mode_cost_per_assignment in optimizer_core.py
            # and Z_i^base / z_{i,k} definitions in Model_Hybrid.md §2):
            #   Z_i^base = Σ W_{i,k} · r_k  (x=1, τ=0 → factors collapse to 1)
            #   z_{i,k}  = W_{i,k} · x^(1-α) · (8/(8+τ))^β · (r_k + (τ/8)·r'_k)
            c_base_ik = W_ik * r_k
            c_crashed_ik = (W_ik
                            * (x_val ** (1.0 - alpha))
                            * ((8.0 / (8.0 + tau_val)) ** beta)
                            * (r_k + (tau_val / 8.0) * r_k_ot))
            
            cost_base += c_base_ik
            cost_crashed += c_crashed_ik
            
        D_base_i_int = int(np.ceil(D_base_i))
        D_crashed_i_int = int(np.ceil(D_crashed_i))  # ceil to match spec §2 and d_max rounding
        
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
            "activity_base_cost": round(cost_base, 2),
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
