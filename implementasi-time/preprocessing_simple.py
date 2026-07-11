import os
import json
import numpy as np
import pandas as pd

def preprocess():
    base_dir = os.path.dirname(os.path.abspath(__file__))
    data_dir = os.path.join(base_dir, "../implementasi-cobb")
    out_dir = os.path.join(base_dir, "data_simple")
    os.makedirs(out_dir, exist_ok=True)

    tasks = pd.read_csv(os.path.join(data_dir, "data_tasks.csv"))
    precedence = pd.read_csv(os.path.join(data_dir, "data_precedence.csv"))
    resources = pd.read_csv(os.path.join(data_dir, "data_assignments.csv"))

    CRASH_DURATION_RATIO = 0.5
    CRASH_COST_RATIO = 0.10

    activity_data = {}
    with open(os.path.join(base_dir, ".../data/resource_capacity.json"), "r") as f:
        resource_capacity = json.load(f)

    resource_requirements = {}

    preds_dict = {}
    for _, row in precedence.iterrows():
        succ = str(row["task_id"]) if pd.notna(row["task_id"]) else None
        pred = str(row["pred_id"]) if pd.notna(row["pred_id"]) else None
        if not succ or not pred:
            continue
        preds_dict.setdefault(succ, []).append(pred)

    for _, row in tasks.iterrows():
        tid = str(row["task_id"])
        tname = row["task_name"]

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

        reqs = {}

        for _, res_row in task_res.iterrows():
            W_ik = res_row["W_ik"]
            U_ik = res_row["U_ik"]
            r_k = res_row["r_k_usd"]

            res_id = str(res_row["resource_id"])
            reqs[res_id] = int(np.ceil(U_ik))

            cost_base += W_ik * r_k

        D_base_i_int = int(np.ceil(D_base_i))
        D_crashed_i_int = max(int(np.ceil(D_base_i * CRASH_DURATION_RATIO)), 1)

        crash_cost_per_day = CRASH_COST_RATIO * cost_base

        activity_data[tid] = {
            "activity_name": tname,
            "activity_normal_time": D_base_i_int,
            "activity_min_time": D_crashed_i_int,
            "crash_cost": round(crash_cost_per_day, 2),
            "required_activities": preds_dict.get(tid, [])
        }
        resource_requirements[tid] = reqs

    with open(os.path.join(out_dir, "activity_data.json"), "w") as f:
        json.dump(activity_data, f, indent=2)
    with open(os.path.join(out_dir, "resource_capacity.json"), "w") as f:
        json.dump(resource_capacity, f, indent=2)
    with open(os.path.join(out_dir, "resource_requirements.json"), "w") as f:
        json.dump(resource_requirements, f, indent=2)

    print(f"Simple preprocessing completed. Files saved to {out_dir}")

if __name__ == "__main__":
    preprocess()
