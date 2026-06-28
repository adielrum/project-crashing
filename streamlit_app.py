import os
import sys
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import streamlit as st
import contextlib
import io
import time

base_dir = os.path.abspath("")
sys.path.append(os.path.join(base_dir, "implementasi-base"))
sys.path.append(os.path.join(base_dir, "implementasi-cobb"))
sys.path.append(os.path.join(base_dir, "implementasi-hybrid"))

from solver_base import (
    read_json, build_predecessors, infer_activity_states_without_state_file,
    SolveConfig as BaseSolveConfig, build_model_and_solve as build_model_and_solve_base, 
    build_reference_no_crash_schedule, generate_gantt_comparison_plot as base_gantt,
    generate_resource_usage_plot
)
import preprocessing

from cobb_model import (
    load_data as load_data_cobb, ResourceBasedScheduling, solve as solve_cobb,
    extract_solution, generate_gantt_comparison_plot as cobb_gantt,
)
from solver_milp import solve_milp_cobb_douglas

class StreamlitWriter(io.StringIO):
    def __init__(self, placeholder):
        super().__init__()
        self.placeholder = placeholder
    def write(self, msg):
        super().write(msg)
        self.placeholder.text(self.getvalue()[-2000:])

@contextlib.contextmanager
def st_redirect(placeholder):
    old_stdout = sys.stdout
    sys.stdout = StreamlitWriter(placeholder)
    try:
        yield
    finally:
        sys.stdout = old_stdout

st.set_page_config(layout="wide", page_title="Project Crashing Optimizer")
st.title("Project Crashing Optimization WebApp")

model_choice = st.sidebar.selectbox("Select Model", ["Base (Linear CP-SAT)", "Cobb-Douglas (MILP CP-SAT)", "Cobb-Douglas (NSGA-II Multi-Objective)", "Hybrid (Preproc + CP-SAT)"])

st.sidebar.header("Parameters")

if model_choice in ["Base (Linear CP-SAT)", "Hybrid (Preproc + CP-SAT)"]:
    mode = st.sidebar.selectbox("Mode", ["cost_with_deadline", "time_with_budget", "bonus_penalty", "min_makespan"])
else:
    mode = st.sidebar.selectbox("Mode", ["bonus_penalty", "cost_with_deadline", "time_with_budget"])

target_end_date = st.sidebar.number_input("Target End Date", min_value=1, value=243 if "Base" in model_choice else 310)
budget_limit = st.sidebar.number_input("Budget Limit ($)", min_value=0.0, value=5000.0 if "Base" in model_choice else 500000.0)
c_late = st.sidebar.number_input("Penalty Cost per Day Late ($)", min_value=0.0, value=1000.0)
c_early = st.sidebar.number_input("Bonus per Day Early ($)", min_value=0.0, value=500.0)
current_day = st.sidebar.number_input("Current Day", min_value=0, value=0)

if "GA" in model_choice or "NSGA" in model_choice:
    pop_size = st.sidebar.number_input("Population Size", min_value=10, value=20)
    n_gen = st.sidebar.number_input("Generations", min_value=10, value=20)

# Cobb-Douglas parameters: Alpha and Beta
alpha = 0.7
beta = 0.7
if "Cobb-Douglas" in model_choice or "Hybrid" in model_choice:
    st.sidebar.subheader("Cobb-Douglas Elasticities")
    alpha = st.sidebar.slider("Alpha (Crowding Elasticity)", min_value=0.0, max_value=2.0, value=0.7, step=0.05)
    beta = st.sidebar.slider("Beta (Overtime Elasticity)", min_value=0.0, max_value=2.0, value=0.7, step=0.05)

# Custom data upload section on the main page
st.markdown("### 📁 Custom Data Upload (Optional)")
if model_choice == "Base (Linear CP-SAT)":
    st.info("Upload JSON files to override default project data. Leave fields blank to use default dataset.")
    col1, col2, col3 = st.columns(3)
    with col1:
        uploaded_act = st.file_uploader("Upload Activity Data (JSON)", type=["json"])
    with col2:
        uploaded_cap = st.file_uploader("Upload Resource Capacity (JSON)", type=["json"])
    with col3:
        uploaded_req = st.file_uploader("Upload Resource Requirements (JSON)", type=["json"])
    
    uploaded_tasks = None
    uploaded_precedence = None
    uploaded_assignments = None
else:
    # Cobb-Douglas or Hybrid
    st.info("Upload CSV files to override default project data. Leave fields blank to use default dataset.")
    col1, col2, col3 = st.columns(3)
    with col1:
        uploaded_tasks = st.file_uploader("Upload Tasks (CSV)", type=["csv"])
    with col2:
        uploaded_precedence = st.file_uploader("Upload Precedence (CSV)", type=["csv"])
    with col3:
        uploaded_assignments = st.file_uploader("Upload Assignments/Resources (CSV)", type=["csv"])
        
    # Hybrid also has optional Resource Capacity JSON
    uploaded_cap = None
    if model_choice == "Hybrid (Preproc + CP-SAT)":
        uploaded_cap = st.file_uploader("Upload Resource Capacity (JSON) - Optional", type=["json"])
    
    uploaded_act = None
    uploaded_req = None

# Show uploaded files preview
with st.expander("🔍 Preview Uploaded Data", expanded=False):
    has_preview = False
    import json
    if model_choice == "Base (Linear CP-SAT)":
        if uploaded_act:
            try:
                act_data = json.load(uploaded_act)
                uploaded_act.seek(0)
                st.write("**Activity Data (first 5 records):**")
                st.json(list(act_data.items())[:5])
                has_preview = True
            except Exception as e:
                st.error(f"Error parsing Activity Data: {e}")
        if uploaded_cap:
            try:
                cap_data = json.load(uploaded_cap)
                uploaded_cap.seek(0)
                st.write("**Resource Capacity:**")
                st.json(cap_data)
                has_preview = True
            except Exception as e:
                st.error(f"Error parsing Resource Capacity: {e}")
        if uploaded_req:
            try:
                req_data = json.load(uploaded_req)
                uploaded_req.seek(0)
                st.write("**Resource Requirements (first 5 records):**")
                st.json(list(req_data.items())[:5])
                has_preview = True
            except Exception as e:
                st.error(f"Error parsing Resource Requirements: {e}")
    else:
        if uploaded_tasks:
            try:
                df = pd.read_csv(uploaded_tasks)
                uploaded_tasks.seek(0)
                st.write("**Tasks Data Preview:**")
                st.dataframe(df.head())
                has_preview = True
            except Exception as e:
                st.error(f"Error parsing Tasks CSV: {e}")
        if uploaded_precedence:
            try:
                df = pd.read_csv(uploaded_precedence)
                uploaded_precedence.seek(0)
                st.write("**Precedence Data Preview:**")
                st.dataframe(df.head())
                has_preview = True
            except Exception as e:
                st.error(f"Error parsing Precedence CSV: {e}")
        if uploaded_assignments:
            try:
                df = pd.read_csv(uploaded_assignments)
                uploaded_assignments.seek(0)
                st.write("**Assignments/Resources Data Preview:**")
                st.dataframe(df.head())
                has_preview = True
            except Exception as e:
                st.error(f"Error parsing Assignments CSV: {e}")
        if uploaded_cap:
            try:
                cap_data = json.load(uploaded_cap)
                uploaded_cap.seek(0)
                st.write("**Resource Capacity:**")
                st.json(cap_data)
                has_preview = True
            except Exception as e:
                st.error(f"Error parsing Resource Capacity: {e}")
    if not has_preview:
        st.write("No custom data files uploaded yet. Default datasets will be used.")

if "run_id" not in st.session_state:
    st.session_state.run_id = 0

if st.sidebar.button("Run Optimization"):
    st.session_state.run_id += 1
    # Clear old results
    for key in list(st.session_state.keys()):
        if key != "run_id":
            del st.session_state[key]
    st.session_state.optimizing = True

if st.session_state.get("optimizing", False):
    status_placeholder = st.empty()
    gantt_placeholder = st.empty()
    verbose_placeholder = st.empty()
    
    if model_choice == "Base (Linear CP-SAT)":
        status_placeholder.info("Loading data and solving Base Model...")
        import json
        if uploaded_act is not None:
            activity_data = json.load(uploaded_act)
            uploaded_act.seek(0)
        else:
            activity_data = read_json(os.path.join(base_dir, "data/activity_data_v3.json"))
            
        if uploaded_cap is not None:
            resource_capacity = json.load(uploaded_cap)
            uploaded_cap.seek(0)
        else:
            resource_capacity = read_json(os.path.join(base_dir, "data/resource_capacity_v3.json"))
            
        if uploaded_req is not None:
            resource_req = json.load(uploaded_req)
            uploaded_req.seek(0)
        else:
            resource_req = read_json(os.path.join(base_dir, "data/resource_requirements_v3.json"))
        
        predecessors, _ = build_predecessors(activity_data, [], True)
        states, _ = infer_activity_states_without_state_file(
            activity_data, resource_req, resource_capacity, predecessors, current_day, 60.0, 1
        )
        
        cfg = BaseSolveConfig(
            target_end_date=target_end_date,
            budget_limit=budget_limit,
            c_late=c_late,
            c_early=c_early,
            current_day=current_day,
            time_limit=60.0,
            num_workers=1,
            auto_fix_paint_trim_cycle=True,
            remove_edges=[]
        )
        
        res = build_model_and_solve_base(
            activity_data, resource_req, resource_capacity, predecessors, states, cfg, mode=mode
        )
        
        st.session_state.base_res = res
        st.session_state.base_act_data = activity_data
        st.session_state.base_res_req = resource_req
        st.session_state.base_res_cap = resource_capacity
        st.session_state.base_pred = predecessors
        st.session_state.optimizing = False
        st.rerun()
            
    elif model_choice == "Hybrid (Preproc + CP-SAT)":
        status_placeholder.info("Preprocessing and solving Hybrid Model...")
        
        tasks_df = pd.read_csv(uploaded_tasks) if uploaded_tasks is not None else None
        if uploaded_tasks is not None:
            uploaded_tasks.seek(0)
            
        precedence_df = pd.read_csv(uploaded_precedence) if uploaded_precedence is not None else None
        if uploaded_precedence is not None:
            uploaded_precedence.seek(0)
            
        resources_df = pd.read_csv(uploaded_assignments) if uploaded_assignments is not None else None
        if uploaded_assignments is not None:
            uploaded_assignments.seek(0)
            
        res_cap_dict = None
        if uploaded_cap is not None:
            import json
            res_cap_dict = json.load(uploaded_cap)
            uploaded_cap.seek(0)
            
        preprocessing.preprocess(
            tasks_df=tasks_df,
            precedence_df=precedence_df,
            resources_df=resources_df,
            resource_capacity=res_cap_dict,
            alpha=alpha,
            beta=beta
        )
        
        act_hyb = read_json(os.path.join(base_dir, "implementasi-hybrid/data/activity_data.json"))
        cap_hyb = read_json(os.path.join(base_dir, "implementasi-hybrid/data/resource_capacity.json"))
        req_hyb = read_json(os.path.join(base_dir, "implementasi-hybrid/data/resource_requirements.json"))
        
        pred_hyb, _ = build_predecessors(act_hyb, [], True)
        states_hyb, _ = infer_activity_states_without_state_file(
            act_hyb, req_hyb, cap_hyb, pred_hyb, current_day, 60.0, 1
        )
        
        cfg = BaseSolveConfig(
            target_end_date=target_end_date, budget_limit=budget_limit,
            c_late=c_late, c_early=c_early, current_day=current_day,
            time_limit=60.0, num_workers=1, auto_fix_paint_trim_cycle=True,
            remove_edges=[]
        )
        
        res = build_model_and_solve_base(
            act_hyb, req_hyb, cap_hyb, pred_hyb, states_hyb, cfg, mode=mode
        )
        
        st.session_state.hyb_res = res
        st.session_state.hyb_act_data = act_hyb
        st.session_state.hyb_res_req = req_hyb
        st.session_state.hyb_res_cap = cap_hyb
        st.session_state.hyb_pred = pred_hyb
        st.session_state.optimizing = False
        st.rerun()
            
    elif model_choice == "Cobb-Douglas (MILP CP-SAT)":
        status_placeholder.info("Running Cobb-Douglas MILP Solver...")
        
        tasks_input = uploaded_tasks if uploaded_tasks is not None else os.path.join(base_dir, "implementasi-cobb/data_tasks.csv")
        prec_input = uploaded_precedence if uploaded_precedence is not None else os.path.join(base_dir, "implementasi-cobb/data_precedence.csv")
        assign_input = uploaded_assignments if uploaded_assignments is not None else os.path.join(base_dir, "implementasi-cobb/data_assignments.csv")
        
        tasks, prec, res_data, N, K_i = load_data_cobb(
            tasks_input, prec_input, assign_input
        )
        if uploaded_tasks is not None:
            uploaded_tasks.seek(0)
        if uploaded_precedence is not None:
            uploaded_precedence.seek(0)
        if uploaded_assignments is not None:
            uploaded_assignments.seek(0)
            
        with st_redirect(verbose_placeholder):
            milp_solution = solve_milp_cobb_douglas(
                tasks=tasks, precedence=prec, resources=res_data, N=N, K_i=K_i,
                alpha=alpha, beta=beta,
                T_max=target_end_date, current_day=current_day,
                mode=mode, budget_limit=budget_limit, c_late=c_late, c_early=c_early,
                time_limit=60.0
            )

        st.session_state.ga_solution = milp_solution
        
        class FakeProb:
            def __init__(self):
                # Calculate initial baseline
                s_baseline = np.zeros(N)
                D_base_i = np.zeros(N)
                D_base_ik = res_data["D_base_ik"].values
                for i in range(N):
                    for p in K_i.get(i, []):
                        D_base_i[i] = max(D_base_i[i], D_base_ik[p])
                        
                # Forward pass baseline
                prec_i = prec["i"].values.astype(int)
                prec_j = prec["j"].values.astype(int)
                prec_lag = prec["lag"].values.astype(float)
                prec_type = prec["type"].values
                for _ in range(N):
                    s_prev = s_baseline.copy()
                    for idx in range(len(prec_i)):
                        i, j = prec_i[idx], prec_j[idx]
                        lag, t = prec_lag[idx], prec_type[idx]
                        if t == "FS": cand = s_baseline[j] + D_base_i[j] + lag
                        elif t == "FF": cand = s_baseline[j] + D_base_i[j] + lag - D_base_i[i]
                        elif t == "SS": cand = s_baseline[j] + lag
                        else: continue
                        if cand > s_baseline[i]: s_baseline[i] = cand
                    if np.allclose(s_baseline, s_prev, atol=1e-8):
                        break
                self.s_baseline = s_baseline
                self.f_baseline = s_baseline + D_base_i
                
        st.session_state.ga_prob = FakeProb()
        st.session_state.ga_tasks = tasks
        st.session_state.ga_res_data = res_data
        st.session_state.optimizing = False
        st.rerun()

    elif model_choice == "Cobb-Douglas (NSGA-II Multi-Objective)":
        status_placeholder.info("Running NSGA-II Multi-Objective...")
        
        tasks_input = uploaded_tasks if uploaded_tasks is not None else os.path.join(base_dir, "implementasi-cobb/data_tasks.csv")
        prec_input = uploaded_precedence if uploaded_precedence is not None else os.path.join(base_dir, "implementasi-cobb/data_precedence.csv")
        assign_input = uploaded_assignments if uploaded_assignments is not None else os.path.join(base_dir, "implementasi-cobb/data_assignments.csv")
        
        tasks, prec, res_data, N, K_i = load_data_cobb(
            tasks_input, prec_input, assign_input
        )
        if uploaded_tasks is not None:
            uploaded_tasks.seek(0)
        if uploaded_precedence is not None:
            uploaded_precedence.seek(0)
        if uploaded_assignments is not None:
            uploaded_assignments.seek(0)
            
        problem_moo = ResourceBasedScheduling(
            tasks=tasks, precedence=prec, resources=res_data, N=N, K_i=K_i,
            alpha=alpha, beta=beta, x_min=1.0, tau_min=0.0, tau_max=4.0, D_min_ratio=0.5,
            T_max=target_end_date, current_day=current_day, overtime_mult=1.5, hours_per_day=8,
            mode="multiobjective",
        )
        with st_redirect(verbose_placeholder):
            res_moo = solve_cobb(problem_moo, pop_size=pop_size, seed=42, verbose=True, max_gen=n_gen)

        st.session_state.nsga_res = res_moo
        st.session_state.nsga_prob = problem_moo
        st.session_state.nsga_tasks = tasks
        st.session_state.nsga_res_data = res_data
        st.session_state.optimizing = False
        st.rerun()


if "base_res" in st.session_state:
    res = st.session_state.base_res
    st.success(f"Status: {res.get('status', 'Unknown')}")
    
    col1, col2 = st.columns(2)
    if "makespan" in res:
        col1.metric("Makespan", f"{res['makespan']} days")
    if "total_crash_cost" in res:
        col2.metric("Total Crash Cost", f"${res['total_crash_cost']}")
        
    if "schedule" in res:
        df = pd.DataFrame(res['schedule'])
        st.subheader("Schedule & Crashing Results")
        st.dataframe(df)
        
        # Fallbacks for old/existing session state
        act_data = st.session_state.get("base_act_data")
        if act_data is None:
            if uploaded_act is not None:
                act_data = json.load(uploaded_act)
                uploaded_act.seek(0)
            else:
                act_data = read_json(os.path.join(base_dir, "data/activity_data_v3.json"))
                
        res_req = st.session_state.get("base_res_req")
        if res_req is None:
            if uploaded_req is not None:
                res_req = json.load(uploaded_req)
                uploaded_req.seek(0)
            else:
                res_req = read_json(os.path.join(base_dir, "data/resource_requirements_v3.json"))
                
        res_cap = st.session_state.get("base_res_cap")
        if res_cap is None:
            if uploaded_cap is not None:
                res_cap = json.load(uploaded_cap)
                uploaded_cap.seek(0)
            else:
                res_cap = read_json(os.path.join(base_dir, "data/resource_capacity_v3.json"))
                
        pred = st.session_state.get("base_pred")
        if pred is None:
            pred, _ = build_predecessors(act_data, [], True)
            
        baseline = build_reference_no_crash_schedule(
            act_data, res_req, res_cap, pred, current_day, 60.0, 1
        )
        
        out_png = os.path.join(base_dir, "outputs/st_base_gantt.png")
        os.makedirs(os.path.dirname(out_png), exist_ok=True)
        base_gantt(baseline, res["schedule"], current_day, out_png)
        st.image(out_png, caption="Gantt Comparison")
        
        # Resource allocation plot
        res_png = os.path.join(base_dir, "outputs/st_base_resources.png")
        generate_resource_usage_plot(
            baseline, res["schedule"], res_req, res_cap, res_png
        )
        st.image(res_png, caption="Resource Allocation & Capacity Load")

if "hyb_res" in st.session_state:
    res = st.session_state.hyb_res
    st.success(f"Status: {res.get('status', 'Unknown')}")
    
    col1, col2 = st.columns(2)
    if "makespan" in res:
        col1.metric("Makespan", f"{res['makespan']} days")
    if "total_crash_cost" in res:
        col2.metric("Total Crash Cost", f"${res['total_crash_cost']}")
        
    if "schedule" in res:
        df = pd.DataFrame(res['schedule'])
        st.subheader("Schedule & Crashing Results")
        st.dataframe(df)
        
        # Fallbacks for old/existing session state
        act_data = st.session_state.get("hyb_act_data")
        if act_data is None:
            act_data = read_json(os.path.join(base_dir, "implementasi-hybrid/data/activity_data.json"))
                
        res_req = st.session_state.get("hyb_res_req")
        if res_req is None:
            res_req = read_json(os.path.join(base_dir, "implementasi-hybrid/data/resource_requirements.json"))
                
        res_cap = st.session_state.get("hyb_res_cap")
        if res_cap is None:
            res_cap = read_json(os.path.join(base_dir, "implementasi-hybrid/data/resource_capacity.json"))
                
        pred = st.session_state.get("hyb_pred")
        if pred is None:
            pred, _ = build_predecessors(act_data, [], True)
            
        baseline = build_reference_no_crash_schedule(
            act_data, res_req, res_cap, pred, current_day, 60.0, 1
        )
        out_png = os.path.join(base_dir, "outputs/st_hybrid_gantt.png")
        os.makedirs(os.path.dirname(out_png), exist_ok=True)
        base_gantt(baseline, res["schedule"], current_day, out_png)
        st.image(out_png, caption="Gantt Comparison")
        
        # Resource allocation plot
        res_png = os.path.join(base_dir, "outputs/st_hybrid_resources.png")
        generate_resource_usage_plot(
            baseline, res["schedule"], res_req, res_cap, res_png
        )
        st.image(res_png, caption="Resource Allocation & Capacity Load")

if "ga_solution" in st.session_state:
    ga_solution = st.session_state.ga_solution
    prob = st.session_state.ga_prob
    if ga_solution is not None:
        st.success("Optimization finished!")
        col1, col2 = st.columns(2)
        col1.metric("Makespan", f"{ga_solution['makespan']:.2f} days")
        if "total_cost" in ga_solution:
            col2.metric("Total Cost", f"${ga_solution['total_cost']:.2f}")

        df_var = pd.DataFrame({
            "Resource": st.session_state.ga_res_data["resource_name"],
            "x (Crowding)": ga_solution["x_ik"],
            "tau (Overtime)": ga_solution["tau_ik"],
            "Original Duration": st.session_state.ga_res_data["D_base_ik"],
            "Crashed Duration": ga_solution["D_ik"],
        })
        st.subheader("Cobb-Douglas Crashing Parameters")
        st.dataframe(df_var)

        out_png = os.path.join(base_dir, "outputs/st_cobb_ga_gantt.png")
        os.makedirs(os.path.dirname(out_png), exist_ok=True)
        cobb_gantt(
            st.session_state.ga_tasks, prob.s_baseline, prob.f_baseline,
            ga_solution["s"], ga_solution["f"], current_day, out_png,
        )
        st.image(out_png, caption="Gantt Comparison")
    else:
        st.error("No feasible solution found.")

if "nsga_res" in st.session_state:
    res_moo = st.session_state.nsga_res
    problem_moo = st.session_state.nsga_prob
    if res_moo is not None and res_moo.F is not None:
        st.success("Optimization finished!")
        F = res_moo.F
        sorted_indices = np.argsort(F[:, 0])
        F_sorted = F[sorted_indices]
        X_sorted = res_moo.X[sorted_indices]

        st.subheader("Pareto Front")
        fig, ax = plt.subplots(figsize=(8, 4))
        ax.plot(F_sorted[:, 0], F_sorted[:, 1], marker='o', linestyle='-')
        ax.set_xlabel('Makespan (days)')
        ax.set_ylabel('Labor Cost ($)')
        ax.grid(True)
        st.pyplot(fig)

        st.write("### Select a Point on the Pareto Front")
        point_idx = st.slider("Select Index of Solution", 0, len(F_sorted)-1, 0)

        selected = extract_solution(problem_moo, X_sorted[point_idx])

        col1, col2 = st.columns(2)
        col1.metric("Makespan", f"{selected['makespan']:.2f} days")
        col2.metric("Labor Cost", f"${selected['labor_cost']:.2f}")

        df_var = pd.DataFrame({
            "Resource": st.session_state.nsga_res_data["resource_name"],
            "x (Crowding)": selected["x_ik"],
            "tau (Overtime)": selected["tau_ik"],
            "Original Duration": st.session_state.nsga_res_data["D_base_ik"],
            "Crashed Duration": selected["D_ik"],
        })
        st.subheader("Crashing Parameters for Selected Point")
        st.dataframe(df_var)

        out_png = os.path.join(base_dir, "outputs/st_cobb_moo_gantt.png")
        os.makedirs(os.path.dirname(out_png), exist_ok=True)
        cobb_gantt(
            st.session_state.nsga_tasks, problem_moo.s_baseline, problem_moo.f_baseline,
            selected["s"], selected["f"], current_day, out_png,
        )
        st.image(out_png, caption="Gantt Comparison for Selected Solution")
    else:
        st.error("No feasible solutions found.")

