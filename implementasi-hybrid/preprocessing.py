import os
import json
import numpy as np
import pandas as pd

def preprocess(
    tasks_df=None, precedence_df=None, resources_df=None, resource_capacity=None,
    alpha=0.7, beta=0.7,
    x_max=2.0, tau_max=4.0, overtime_mult=1.5, hours_per_day=8,
):
    """Preprocess CSV data into activity_data / resource_requirements / resource_capacity dicts.

    Parameters
    ----------
    x_max, tau_max, overtime_mult, hours_per_day :
        Must match the Cobb-Douglas model parameters used in Scenarios A & B so
        that the linear crash-cost slopes derived here are comparable.

    Returns
    -------
    (activity_data, resource_requirements, resource_capacity) — the three dicts.
    They are also written to ``implementasi-hybrid/data/`` as JSON files.
    """
    base_dir = os.path.dirname(os.path.abspath(__file__))
    data_dir = os.path.join(base_dir, "../implementasi-cobb")
    out_dir = os.path.join(base_dir, "data")
    os.makedirs(out_dir, exist_ok=True)
    
    tasks = tasks_df if tasks_df is not None else pd.read_csv(os.path.join(data_dir, "data_tasks.csv"))
    precedence = precedence_df if precedence_df is not None else pd.read_csv(os.path.join(data_dir, "data_precedence.csv"))
    resources = resources_df if resources_df is not None else pd.read_csv(os.path.join(data_dir, "data_assignments.csv"))
    
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
                "required_activities": preds_dict.get(tid, [])
            }
            resource_requirements[tid] = {}
            continue
            
        D_base_i = task_res["D_base"].max()
        
        cost_base = 0.0
        cost_crashed = 0.0
        D_crashed_i = 0.0
        
        # reqs maps resource_name -> {"base": u_ik^(0), "slope": V_ik}
        # per laporan.typ §2.3 Eq. <eq:resource-extremal> and <eq:resource-slope>
        reqs = {}
        
        for _, res_row in task_res.iterrows():
            D_base_ik = res_row["D_base"]
            W_ik = res_row["W_ik"]
            U_ik = res_row["U_ik"]
            r_k = res_row["r_k_usd"]
            r_k_ot = r_k * overtime_mult
            
            # Key by resource_name (not resource_id) so it matches resource_capacity.json keys
            res_name = str(res_row["resource_name"])
            
            D_crashed_ik = D_base_ik * (1.0 / x_max)**alpha * (8.0 / (8.0 + tau_max))**beta
            # Ensure it doesn't drop below 0.5 D_base_ik (crash limit safety floor)
            D_crashed_ik = max(D_crashed_ik, 0.5 * D_base_ik)
            
            D_crashed_i = max(D_crashed_i, D_crashed_ik)
            
            # Cobb-Douglas cost formula (matches mode_cost_per_assignment in optimizer_core.py
            # and Z_i^base / z_{i,k} definitions in Model_Hybrid.md §2):
            #   Z_i^base = Σ W_{i,k} · r_k  (x=1, τ=0 → factors collapse to 1)
            #   z_{i,k}  = W_{i,k} · x^(1-α) · (8/(8+τ))^β · (r_k + (τ/8)·r'_k)
            c_base_ik = W_ik * r_k
            c_crashed_ik = (W_ik
                            * (x_max ** (1.0 - alpha))
                            * ((8.0 / (8.0 + tau_max)) ** beta)
                            * (r_k + (tau_max / 8.0) * r_k_ot))
            
            cost_base += c_base_ik
            cost_crashed += c_crashed_ik
            
            # --- Resource slope per laporan.typ §2.3 Eq. <eq:resource-extremal> & <eq:resource-slope> ---
            # Baseline daily allocation:   u_{i,k}^(0) := U_{i,k}
            # Crashed daily allocation:    u_{i,k}^(crash) := x_max * U_{i,k}
            u_base_ik = U_ik
            u_crashed_ik = x_max * U_ik
            
            # Compute per-assignment duration reduction range
            delta_d_ik = D_base_ik - D_crashed_ik
            
            # Resource slope V_{i,k}  (Eq. <eq:resource-slope>)
            if delta_d_ik > 0.01:
                V_ik = (u_crashed_ik - u_base_ik) / delta_d_ik
            else:
                V_ik = 0.0
            
            reqs[res_name] = {
                "base": float(u_base_ik),
                "slope": float(V_ik),
            }
            
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
            "activity_base_cost": round(cost_base, 2),   # sum W_{i,k}*r_k (baseline labor at x=1, τ=0)
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
    print("  resource_requirements.json now uses resource NAMES as keys and includes resource slopes (V_ik).")

    return activity_data, resource_requirements, resource_capacity

if __name__ == "__main__":
    preprocess()
