import os
import sys
import json
import time
import numpy as np
import pandas as pd
import streamlit as st
import matplotlib.pyplot as plt

# ==============================================================================
# 1. Path & Module Configuration
# ==============================================================================
base_dir = os.path.abspath(os.path.dirname(__file__))
if base_dir == "":
    base_dir = os.path.abspath(".")

for folder in ["implementasi-base", "implementasi-resource", "implementasi-mode", "implementasi-time"]:
    fpath = os.path.join(base_dir, folder)
    if fpath not in sys.path:
        sys.path.append(fpath)

# Import Solvers
from solver_base import (
    read_json, build_predecessors, infer_activity_states_without_state_file,
    SolveConfig as BaseSolveConfig, build_model_and_solve as build_model_and_solve_base, 
    write_schedule_csv as write_schedule_csv_base, generate_gantt_comparison_plot as generate_gantt_base
)
from cobb_model import (
    load_data as load_data_cobb, ResourceBasedScheduling, solve as solve_cobb,
    save_solution_json as save_solution_json_cobb
)
from solver_milp import solve_milp_cobb_douglas

# ==============================================================================
# 2. Page Configuration & Custom CSS
# ==============================================================================
st.set_page_config(
    page_title="Project Crashing Optimization (IDSC Dataset)",
    page_icon="🚀",
    layout="wide",
    initial_sidebar_state="expanded"
)

st.markdown("""
<style>
    .metric-card {
        background-color: #f8f9fa;
        border: 1px solid #dee2e6;
        border-radius: 8px;
        padding: 15px;
        margin-bottom: 10px;
    }
    .stTabs [data-baseweb="tab-list"] {
        gap: 20px;
    }
    .stTabs [data-baseweb="tab"] {
        height: 50px;
        white-space: pre-wrap;
        background-color: #f1f3f5;
        border-radius: 6px 6px 0 0;
        padding: 10px 20px;
        font-weight: 600;
    }
    .stTabs [aria-selected="true"] {
        background-color: #007bff;
        color: white;
    }
</style>
""", unsafe_allow_html=True)

# ==============================================================================
# 3. Helper Classes & Redirectors
# ==============================================================================
class st_redirect:
    """Redirects stdout/stderr to a Streamlit container for live solver logs."""
    def __init__(self, placeholder):
        self.placeholder = placeholder
        self.buffer = []
    def write(self, text):
        if text.strip():
            self.buffer.append(text.strip())
            if len(self.buffer) > 25:
                self.buffer = self.buffer[-25:]
            self.placeholder.code("\n".join(self.buffer), language="text")
    def flush(self):
        pass
    def __enter__(self):
        self.old_stdout = sys.stdout
        sys.stdout = self
        return self
    def __exit__(self, exc_type, exc_val, exc_tb):
        sys.stdout = self.old_stdout

# ==============================================================================
# 4. Sidebar Configuration
# ==============================================================================
st.sidebar.title("🚀 Model & Mode Selection")
st.sidebar.markdown("Reproduce comparative analysis results from the manuscript on the IDSC commercial project dataset.")

model_choice = st.sidebar.selectbox(
    "Select Model & Optimization Scheme:",
    [
        "1. Resource-Based Model (Single-Objective GA)",
        "2. Resource-Based Model (Multi-Objective NSGA-II)",
        "3. Mode-Based Model (Single-Objective MILP CP-SAT)",
        "4. Mode-Based Model (Multi-Objective MILP ε-constraint)",
        "5. Time-Based Model (Single-Objective Linear CP-SAT)",
        "6. Time-Based Model (Multi-Objective Linear ε-constraint)",
        "7. Base Model (Toy Data Benchmark)"
    ]
)

st.sidebar.header("⚙️ Optimization Parameters")

is_single = "Single-Objective" in model_choice or "Base Model" in model_choice
is_multi = "Multi-Objective" in model_choice

lock_paper = st.sidebar.checkbox("🔒 Lock to Paper Benchmark Parameters", value=True, help="Locks target end date T_max=250, c_early=$2000, c_late=$5000, alpha=beta=0.7 as reported in Section 3.1.2.")

if lock_paper and is_single and "Base" not in model_choice:
    target_end_date = 250
    c_early = 2000.0
    c_late = 5000.0
    alpha = 0.7
    beta = 0.7
    mode = "bonus_penalty"
    budget_limit = 500000.0
    st.sidebar.info("Using exact parameters: **T_max = 250 days, Bonus = $2,000/day, Penalty = $5,000/day, α = β = 0.7**")
else:
    if "Base" in model_choice:
        mode = st.sidebar.selectbox("Objective Mode", ["cost_with_deadline", "time_with_budget", "bonus_penalty"])
        target_end_date = st.sidebar.number_input("Target End Date (T_max)", min_value=1, value=243)
        budget_limit = st.sidebar.number_input("Budget Limit ($)", min_value=0.0, value=5000.0)
    elif is_single:
        mode = st.sidebar.selectbox("Objective Mode", ["bonus_penalty", "cost_with_deadline", "time_with_budget"])
        target_end_date = st.sidebar.number_input("Target End Date (T_max)", min_value=1, value=250)
        budget_limit = st.sidebar.number_input("Budget Limit ($)", min_value=0.0, value=500000.0)
    else:
        mode = "multiobjective"
        target_end_date = 344
        budget_limit = 1000000.0

    c_early = st.sidebar.number_input("Bonus per Day Early ($)", min_value=0.0, value=2000.0)
    c_late = st.sidebar.number_input("Penalty per Day Late ($)", min_value=0.0, value=5000.0)
    
    st.sidebar.subheader("Cobb-Douglas Elasticities")
    alpha = st.sidebar.slider("Alpha (Overcrowding Elasticity)", min_value=0.0, max_value=2.0, value=0.7, step=0.05)
    beta = st.sidebar.slider("Beta (Overtime Elasticity)", min_value=0.0, max_value=2.0, value=0.7, step=0.05)

current_day = st.sidebar.number_input("Current Review Day (T_0)", min_value=0, value=20 if "Base" not in model_choice else 0)

# Algorithmic Controls
st.sidebar.subheader("🎛️ Execution Controls")
if "GA" in model_choice or "NSGA" in model_choice:
    fast_demo = st.sidebar.checkbox("⚡ Fast Interactive Web Mode", value=True, help="Runs GA with 100 population and 50 generations (~15s) instead of 1000 pop / 500 gen (~14 min).")
    if fast_demo:
        pop_size = 100
        n_gen = 50
        st.sidebar.caption("Run settings: **Pop=100, Gen=50** (~15 sec)")
    else:
        pop_size = st.sidebar.number_input("Population Size", min_value=10, value=1000)
        n_gen = st.sidebar.number_input("Generations", min_value=10, value=500)
elif "ε-constraint" in model_choice:
    eps_step = st.sidebar.select_slider("ε-Constraint Step Size (Days)", options=[2, 4, 6, 8, 10], value=6 if "Mode" in model_choice else 4, help="Smaller step size generates denser Pareto fronts but takes proportionally longer.")
    time_lim_eps = st.sidebar.number_input("CP-SAT Time Limit per ε-Step (s)", min_value=1.0, value=15.0 if "Mode" in model_choice else 2.0)
else:
    time_lim = st.sidebar.number_input("CP-SAT Solver Time Limit (s)", min_value=1.0, value=60.0)

# Run Button
st.sidebar.markdown("---")
run_btn = st.sidebar.button("▶️ Run Live Optimization", type="primary", use_container_width=True)

# ==============================================================================
# 5. Main Page UI & Tab Navigation
# ==============================================================================
st.title("🏗️ Dynamic Resource-Constrained Project Crashing Dashboard")
st.markdown("""
Interactive evaluation suite for the **Cobb-Douglas Resource-Based Metaheuristic (Model A)**, **Mode-Based MILP CP-SAT (Model B)**, and **Time-Based Linear CP-SAT (Model C)** on the commercial project construction dataset ($N=110$ tasks, $P=8$ resources, $T_{\text{base}}=344$ days).
""")

tab_run, tab_compare = st.tabs(["🚀 Live Optimization & Schedule", "📊 Thesis Comparative Analysis Benchmark (Paper Tables)"])

# ==============================================================================
# TAB 1: Live Optimization & Schedule Execution
# ==============================================================================
with tab_run:
    # Optional Custom Data Upload Expander
    with st.expander("📁 Custom Dataset Upload (Override Default IDSC Project Data)", expanded=False):
        if "Base" in model_choice:
            col1, col2, col3 = st.columns(3)
            up_act = col1.file_uploader("activity_data.json", type=["json"])
            up_cap = col2.file_uploader("resource_capacity.json", type=["json"])
            up_req = col3.file_uploader("resource_requirements.json", type=["json"])
        elif "Time-Based" in model_choice:
            col1, col2, col3 = st.columns(3)
            up_act = col1.file_uploader("activity_data.json (Preprocessed)", type=["json"])
            up_cap = col2.file_uploader("resource_capacity.json", type=["json"])
            up_req = col3.file_uploader("resource_requirements.json", type=["json"])
        else:
            col1, col2, col3 = st.columns(3)
            up_tasks = col1.file_uploader("data_tasks.csv", type=["csv"])
            up_prec = col2.file_uploader("data_precedence.csv", type=["csv"])
            up_assign = col3.file_uploader("data_assignments.csv", type=["csv"])

    if run_btn:
        st.session_state.active_run = True
        st.session_state.active_model = model_choice

    if st.session_state.get("active_run", False) and st.session_state.get("active_model") == model_choice:
        status_box = st.empty()
        log_box = st.empty()
        
        # ----------------------------------------------------------------------
        # Option 1: Resource-Based Model (Single-Objective GA)
        # ----------------------------------------------------------------------
        if "1. Resource-Based Model (Single-Objective GA)" in model_choice:
            status_box.info(f"⏳ Running Cobb-Douglas GA (Model A) | Mode: {mode} | Pop={pop_size}, Gen={n_gen}...")
            t0 = time.time()
            
            p_tasks = os.path.join(base_dir, "data/data_tasks.csv")
            p_prec = os.path.join(base_dir, "data/data_precedence.csv")
            p_assign = os.path.join(base_dir, "data/data_assignments.csv")
            
            tasks, prec, res_data, N, K_i = load_data_cobb(p_tasks, p_prec, p_assign)
            
            prob = ResourceBasedScheduling(
                tasks=tasks, precedence=prec, resources=res_data, N=N, K_i=K_i,
                alpha=alpha, beta=beta, x_min=1.0, tau_min=0.0, tau_max=4.0, D_min_ratio=0.5,
                T_max=target_end_date, current_day=current_day, overtime_mult=1.5, hours_per_day=8,
                mode=mode, budget_limit=budget_limit, c_late=c_late, c_early=c_early,
                completion_fraction=None, enforce_resource_capacity=True, num_workers=4
            )
            
            with st_redirect(log_box):
                res_ga = solve_cobb(prob, pop_size=pop_size, seed=42, verbose=True, max_gen=n_gen)
            
            solve_time = time.time() - t0
            status_box.success(f"✅ Resource-Based GA Optimization Complete in {solve_time:.2f} seconds!")
            
            if res_ga:
                st.session_state.last_res = {
                    "makespan": res_ga["makespan"],
                    "labor_cost": res_ga["labor_cost"],
                    "total_cost": res_ga.get("total_project_cost", res_ga["labor_cost"]),
                    "bonus": c_early * max(0, target_end_date - res_ga["makespan"]),
                    "penalty": c_late * max(0, res_ga["makespan"] - target_end_date),
                    "solve_time": solve_time,
                    "x_ik": res_ga["x_ik"],
                    "tau_ik": res_ga["tau_ik"],
                    "D_ik": res_ga["D_ik"],
                    "s": res_ga["s"],
                    "f": res_ga["f"],
                    "tasks": tasks,
                    "res_data": res_data
                }
                st.session_state.active_run = False
                st.rerun()

        # ----------------------------------------------------------------------
        # Option 2: Resource-Based Model (Multi-Objective NSGA-II)
        # ----------------------------------------------------------------------
        elif "2. Resource-Based Model (Multi-Objective NSGA-II)" in model_choice:
            status_box.info(f"⏳ Running Cobb-Douglas NSGA-II (Model A) | Pop={pop_size}, Gen={n_gen}...")
            t0 = time.time()
            
            p_tasks = os.path.join(base_dir, "data/data_tasks.csv")
            p_prec = os.path.join(base_dir, "data/data_precedence.csv")
            p_assign = os.path.join(base_dir, "data/data_assignments.csv")
            
            tasks, prec, res_data, N, K_i = load_data_cobb(p_tasks, p_prec, p_assign)
            
            prob_moo = ResourceBasedScheduling(
                tasks=tasks, precedence=prec, resources=res_data, N=N, K_i=K_i,
                alpha=alpha, beta=beta, x_min=1.0, tau_min=0.0, tau_max=4.0, D_min_ratio=0.5,
                T_max=target_end_date, current_day=current_day, overtime_mult=1.5, hours_per_day=8,
                mode="multiobjective", num_workers=4
            )
            
            with st_redirect(log_box):
                res_moo = solve_cobb(prob_moo, pop_size=pop_size, seed=42, verbose=True, max_gen=n_gen)
            
            solve_time = time.time() - t0
            status_box.success(f"✅ NSGA-II Pareto Optimization Complete in {solve_time:.2f} seconds!")
            
            if res_moo and "pareto_front" in res_moo:
                st.session_state.moo_res = {
                    "pareto": res_moo["pareto_front"],
                    "solve_time": solve_time,
                    "model": "Resource-Based (NSGA-II)"
                }
                st.session_state.active_run = False
                st.rerun()

        # ----------------------------------------------------------------------
        # Option 3: Mode-Based Model (Single-Objective MILP CP-SAT)
        # ----------------------------------------------------------------------
        elif "3. Mode-Based Model (Single-Objective MILP CP-SAT)" in model_choice:
            status_box.info(f"⏳ Running Mode-Based MILP CP-SAT (Model B) | Mode: {mode} | Time Limit: {time_lim}s...")
            t0 = time.time()
            
            p_tasks = os.path.join(base_dir, "data/data_tasks.csv")
            p_prec = os.path.join(base_dir, "data/data_precedence.csv")
            p_assign = os.path.join(base_dir, "data/data_assignments.csv")
            
            tasks, prec, res_data, N, K_i = load_data_cobb(p_tasks, p_prec, p_assign)
            
            with st_redirect(log_box):
                milp_sol = solve_milp_cobb_douglas(
                    tasks=tasks, precedence=prec, resources=res_data, N=N, K_i=K_i,
                    alpha=alpha, beta=beta, dx=0.1, dtau=0.1,
                    T_max=target_end_date, current_day=current_day,
                    mode=mode, budget_limit=budget_limit, c_late=c_late, c_early=c_early,
                    time_limit=time_lim
                )
            
            solve_time = time.time() - t0
            status_box.success(f"✅ Mode-Based MILP Optimization Complete in {solve_time:.2f} seconds!")
            
            if milp_sol and isinstance(milp_sol, dict) and "makespan" in milp_sol:
                st.session_state.last_res = {
                    "makespan": milp_sol["makespan"],
                    "labor_cost": milp_sol["labor_cost"],
                    "total_cost": milp_sol["total_cost"],
                    "bonus": c_early * max(0, target_end_date - milp_sol["makespan"]),
                    "penalty": c_late * max(0, milp_sol["makespan"] - target_end_date),
                    "solve_time": solve_time,
                    "x_ik": milp_sol["x_ik"],
                    "tau_ik": milp_sol["tau_ik"],
                    "D_ik": milp_sol["D_ik"],
                    "s": milp_sol["s"],
                    "f": milp_sol["f"],
                    "tasks": tasks,
                    "res_data": res_data
                }
                st.session_state.active_run = False
                st.rerun()

        # ----------------------------------------------------------------------
        # Option 4: Mode-Based Model (Multi-Objective MILP ε-constraint)
        # ----------------------------------------------------------------------
        elif "4. Mode-Based Model (Multi-Objective MILP ε-constraint)" in model_choice:
            status_box.info(f"⏳ Running Mode-Based MILP ε-constraint Suite | Step: {eps_step} days | Time Limit/Step: {time_lim_eps}s...")
            t0 = time.time()
            
            p_tasks = os.path.join(base_dir, "data/data_tasks.csv")
            p_prec = os.path.join(base_dir, "data/data_precedence.csv")
            p_assign = os.path.join(base_dir, "data/data_assignments.csv")
            tasks, prec, res_data, N, K_i = load_data_cobb(p_tasks, p_prec, p_assign)
            
            pareto_pts = []
            eps_range = np.arange(210, 345, eps_step)
            for i, eps in enumerate(eps_range):
                status_box.info(f"⏳ Solving Mode-Based MILP ε-constraint [{i+1}/{len(eps_range)}]: T_max ≤ {eps} days...")
                with st_redirect(log_box):
                    sol_eps = solve_milp_cobb_douglas(
                        tasks=tasks, precedence=prec, resources=res_data, N=N, K_i=K_i,
                        alpha=alpha, beta=beta, dx=0.1, dtau=0.1,
                        T_max=int(eps), current_day=current_day,
                        mode="cost_with_deadline", time_limit=time_lim_eps
                    )
                if sol_eps and isinstance(sol_eps, dict) and "makespan" in sol_eps:
                    pareto_pts.append((sol_eps["makespan"], sol_eps["labor_cost"]))
            
            solve_time = time.time() - t0
            status_box.success(f"✅ Mode-Based MILP ε-constraint Suite Complete in {solve_time:.2f} seconds ({len(pareto_pts)} points found)!")
            if pareto_pts:
                st.session_state.moo_res = {
                    "pareto": np.array(pareto_pts),
                    "solve_time": solve_time,
                    "model": "Mode-Based MILP (ε-constraint)"
                }
                st.session_state.active_run = False
                st.rerun()

        # ----------------------------------------------------------------------
        # Option 5: Time-Based Model (Single-Objective Linear CP-SAT)
        # ----------------------------------------------------------------------
        elif "5. Time-Based Model (Single-Objective Linear CP-SAT)" in model_choice:
            status_box.info("⏳ Running Time-Based Linear CP-SAT (Model C) | Mode: bonus_penalty...")
            t0 = time.time()
            
            act_data = read_json(os.path.join(base_dir, "data/activity_data.json"))
            cap_data = read_json(os.path.join(base_dir, "data/resource_capacity.json"))
            req_data = read_json(os.path.join(base_dir, "data/resource_requirements.json"))
            
            predecessors, _ = build_predecessors(act_data, [], True)
            states, _ = infer_activity_states_without_state_file(act_data, req_data, cap_data, predecessors, current_day, 60.0, 1)
            
            cfg = BaseSolveConfig(
                target_end_date=target_end_date, current_day=current_day, time_limit=time_lim,
                num_workers=1, auto_fix_paint_trim_cycle=True, remove_edges=[], budget_limit=budget_limit
            )
            
            with st_redirect(log_box):
                result = build_model_and_solve(
                    act_data, req_data, cap_data, predecessors, states, cfg,
                    mode="bonus_penalty", c_late=c_late, c_early=c_early
                )
            
            solve_time = time.time() - t0
            status_box.success(f"✅ Time-Based Linear CP-SAT Complete in {solve_time:.2f} seconds!")
            
            if result and result.get("status") in ["OPTIMAL", "FEASIBLE"]:
                st.session_state.last_res_time = {
                    "makespan": result["makespan"],
                    "labor_cost": result["total_crash_cost"],
                    "total_cost": result.get("total_project_cost", result["total_crash_cost"]),
                    "bonus": c_early * max(0, target_end_date - result["makespan"]),
                    "penalty": c_late * max(0, result["makespan"] - target_end_date),
                    "solve_time": solve_time,
                    "schedule": result["schedule"],
                    "resource_usage": result["resource_usage"]
                }
                st.session_state.active_run = False
                st.rerun()

        # ----------------------------------------------------------------------
        # Option 6: Time-Based Model (Multi-Objective Linear ε-constraint)
        # ----------------------------------------------------------------------
        elif "6. Time-Based Model (Multi-Objective Linear ε-constraint)" in model_choice:
            status_box.info(f"⏳ Running Time-Based Linear CP-SAT ε-constraint Suite | Step: {eps_step} days...")
            t0 = time.time()
            
            act_data = read_json(os.path.join(base_dir, "data/activity_data.json"))
            cap_data = read_json(os.path.join(base_dir, "data/resource_capacity.json"))
            req_data = read_json(os.path.join(base_dir, "data/resource_requirements.json"))
            predecessors, _ = build_predecessors(act_data, [], True)
            states, _ = infer_activity_states_without_state_file(act_data, req_data, cap_data, predecessors, current_day, 60.0, 1)
            
            pareto_pts = []
            eps_range = np.arange(210, 345, eps_step)
            for i, eps in enumerate(eps_range):
                status_box.info(f"⏳ Solving Time-Based Linear CP-SAT [{i+1}/{len(eps_range)}]: T_max ≤ {eps} days...")
                cfg = BaseSolveConfig(target_end_date=int(eps), current_day=current_day, time_limit=time_lim_eps, num_workers=1, auto_fix_paint_trim_cycle=True, remove_edges=[], budget_limit=None)
                with st_redirect(log_box):
                    res_eps = build_model_and_solve(act_data, req_data, cap_data, predecessors, states, cfg, mode="cost_with_deadline")
                if res_eps and res_eps.get("status") in ["OPTIMAL", "FEASIBLE"]:
                    pareto_pts.append((res_eps["makespan"], res_eps["total_crash_cost"]))
            
            solve_time = time.time() - t0
            status_box.success(f"✅ Time-Based ε-constraint Suite Complete in {solve_time:.2f} seconds ({len(pareto_pts)} points found)!")
            if pareto_pts:
                st.session_state.moo_res = {
                    "pareto": np.array(pareto_pts),
                    "solve_time": solve_time,
                    "model": "Time-Based Linear CP-SAT (ε-constraint)"
                }
                st.session_state.active_run = False
                st.rerun()

        # ----------------------------------------------------------------------
        # Option 7: Base Model (Toy Data Benchmark)
        # ----------------------------------------------------------------------
        elif "7. Base Model" in model_choice:
            status_box.info("⏳ Solving Base Model on Toy Dataset (`activity_data_v3.json`)....")
            t0 = time.time()
            act_data = read_json(os.path.join(base_dir, "data/activity_data_v3.json"))
            cap_data = read_json(os.path.join(base_dir, "data/resource_capacity_v3.json"))
            req_data = read_json(os.path.join(base_dir, "data/resource_requirements_v3.json"))
            predecessors, _ = build_predecessors(act_data, [], True)
            states, _ = infer_activity_states_without_state_file(act_data, req_data, cap_data, predecessors, 0, 60.0, 1)
            cfg = BaseSolveConfig(target_end_date=target_end_date, current_day=0, time_limit=60.0, num_workers=1, auto_fix_paint_trim_cycle=True, remove_edges=[], budget_limit=budget_limit)
            with st_redirect(log_box):
                result = build_model_and_solve(act_data, req_data, cap_data, predecessors, states, cfg, mode=mode, c_late=c_late, c_early=c_early)
            solve_time = time.time() - t0
            status_box.success(f"✅ Base Model Complete in {solve_time:.2f} seconds!")
            if result and result.get("status") in ["OPTIMAL", "FEASIBLE"]:
                st.session_state.last_res_time = {
                    "makespan": result["makespan"],
                    "labor_cost": result["total_crash_cost"],
                    "total_cost": result.get("total_project_cost", result["total_crash_cost"]),
                    "bonus": 0, "penalty": 0, "solve_time": solve_time,
                    "schedule": result["schedule"], "resource_usage": result["resource_usage"]
                }
                st.session_state.active_run = False
                st.rerun()

    # --------------------------------------------------------------------------
    # DISPLAY SINGLE-OBJECTIVE RESULTS (RESOURCE & MODE BASED)
    # --------------------------------------------------------------------------
    if "last_res" in st.session_state and ("Resource" in model_choice or "Mode" in model_choice):
        res = st.session_state.last_res
        st.subheader(f"📈 Results for {model_choice.split('(')[0].strip()}")
        
        c1, c2, c3, c4, c5, c6 = st.columns(6)
        c1.metric("Optimal Makespan", f"{res['makespan']} days", f"{344 - res['makespan']}d crashed")
        c2.metric("Target Margin", f"{250 - res['makespan']} days" if res['makespan'] <= 250 else f"-{res['makespan']-250} days")
        c3.metric("Labor Cost", f"${res['labor_cost']:,.2f}")
        c4.metric("Early Bonus ($2k/d)", f"${res['bonus']:,.2f}")
        c5.metric("Total Project Cost", f"${res['total_cost']:,.2f}")
        c6.metric("Solve Time", f"{res['solve_time']:.2f} s")
        
        st.markdown("### 📋 Crashing Activity Summary Table")
        tasks_df = res["tasks"]
        res_df = res["res_data"]
        
        # Build readable table
        s_arr = res["s"]
        f_arr = res["f"]
        D_ik = res["D_ik"]
        x_ik = res["x_ik"]
        tau_ik = res["tau_ik"]
        
        summary_rows = []
        for i in range(len(tasks_df)):
            task_name = tasks_df.loc[i, "activity_name"]
            base_dur = 0
            opt_dur = f_arr[i] - s_arr[i]
            # check resources
            allocs = []
            crashed = False
            for r_idx in range(len(res_df)):
                # check if assigned
                if D_ik[i, r_idx] > 0 or x_ik[i, r_idx] > 1.01 or tau_ik[i, r_idx] > 0.01:
                    base_d = res_df.loc[r_idx, "D_base_ik"]
                    base_dur = max(base_dur, base_d)
                    rname = res_df.loc[r_idx, "resource_name"]
                    x_val = x_ik[i, r_idx]
                    t_val = tau_ik[i, r_idx]
                    if x_val > 1.05 or t_val > 0.05 or base_dur - opt_dur > 0.05:
                        crashed = True
                    allocs.append(f"{rname}: α={x_val:.2f}x, τ=+{t_val:.1f}h")
            if crashed:
                summary_rows.append({
                    "Activity ID": tasks_df.loc[i, "activity_id"],
                    "Activity Name": task_name,
                    "Start Day": round(s_arr[i], 1),
                    "Finish Day": round(f_arr[i], 1),
                    "Base Duration": round(base_dur, 1),
                    "Optimized Duration": round(opt_dur, 1),
                    "Days Saved": round(base_dur - opt_dur, 1),
                    "Resource Adjustments": " | ".join(allocs)
                })
        
        if summary_rows:
            st.dataframe(pd.DataFrame(summary_rows), use_container_width=True)
        else:
            st.info("No activities were crashed beyond baseline duration.")

    # --------------------------------------------------------------------------
    # DISPLAY SINGLE-OBJECTIVE RESULTS (TIME-BASED & BASE)
    # --------------------------------------------------------------------------
    elif "last_res_time" in st.session_state and ("Time" in model_choice or "Base" in model_choice):
        res = st.session_state.last_res_time
        st.subheader(f"📈 Results for {model_choice.split('(')[0].strip()}")
        
        c1, c2, c3, c4, c5, c6 = st.columns(6)
        c1.metric("Optimal Makespan", f"{res['makespan']} days")
        c2.metric("Target Margin", f"{target_end_date - res['makespan']} days")
        c3.metric("Labor / Crash Cost", f"${res['labor_cost']:,.2f}")
        c4.metric("Early Bonus", f"${res['bonus']:,.2f}")
        c5.metric("Total Project Cost", f"${res['total_cost']:,.2f}")
        c6.metric("Solve Time", f"{res['solve_time']:.2f} s")
        
        st.markdown("### 📋 Activity Schedule Table")
        sched_df = pd.DataFrame(res["schedule"])
        st.dataframe(sched_df, use_container_width=True)

    # --------------------------------------------------------------------------
    # DISPLAY MULTI-OBJECTIVE RESULTS (PARETO FRONT)
    # --------------------------------------------------------------------------
    elif "moo_res" in st.session_state and is_multi:
        moo = st.session_state.moo_res
        st.subheader(f"🌐 Multi-Objective Pareto Trade-off: {moo['model']}")
        st.caption(f"Completed in {moo['solve_time']:.2f} seconds.")
        
        pts = moo["pareto"]
        if isinstance(pts, list):
            pts = np.array(pts)
        if pts.ndim == 2 and len(pts) > 0:
            # Sort by makespan
            pts = pts[pts[:, 0].argsort()]
            
            fig, ax = plt.subplots(figsize=(10, 5))
            ax.plot(pts[:, 0], pts[:, 1], "o-", color="#1f77b4", linewidth=2, markersize=6, label=moo["model"])
            ax.set_xlabel("Makespan (Days)", fontsize=11, fontweight="bold")
            ax.set_ylabel("Labor Cost ($)", fontsize=11, fontweight="bold")
            ax.set_title("Time-Cost Trade-off Pareto Front", fontsize=13, fontweight="bold")
            ax.grid(True, linestyle="--", alpha=0.6)
            ax.legend(frameon=True)
            st.pyplot(fig)
            
            st.markdown("### 📋 Pareto Candidates Table")
            df_pareto = pd.DataFrame({
                "Makespan (Days)": np.round(pts[:, 0], 2),
                "Labor Cost ($)": np.round(pts[:, 1], 2),
                "Total Cost w/ Bonus ($2k/d early) ($)": np.round(pts[:, 1] - 2000.0 * np.maximum(0, 250.0 - pts[:, 0]), 2)
            })
            st.dataframe(df_pareto, use_container_width=True)

# ==============================================================================
# TAB 2: Thesis Comparative Analysis Benchmark (Paper Tables)
# ==============================================================================
with tab_compare:
    st.markdown("### 🏆 Empirical Benchmark Results from Manuscript (Section 3.1.2)")
    st.markdown("""
    The tables below display the exact theoretical benchmarks reported in the thesis manuscript tested on the commercial project construction dataset ($N=110$ tasks, $T_{\text{base}}=344$ days, $alpha=beta=0.7$, $T_0=20$).
    Users can compare the **Resource-Based (Model A)**, **Mode-Based (Model B)**, and **Time-Based (Model C)** approaches across both single-objective and multi-objective paradigms.
    """)
    
    st.subheader("1️⃣ Single-Objective Optimization (Bonus-Penalty Scalarization)")
    st.caption("Standardized Parameters: T_max = 250 days, Bonus c_early = $2,000/day, Penalty c_late = $5,000/day, α = β = 0.7.")
    
    df_single_paper = pd.DataFrame({
        "Performance Metric": [
            "Optimal Makespan (s_{n+1})",
            "Rescue Margin (T_base - s_{n+1})",
            "Target Margin (T_max - s_{n+1})",
            "Labor Cost (Σ z_i)",
            "Penalty ($5,000/d late)",
            "Bonus ($2,000/d early)",
            "Total Project Cost",
            "Solver Execution Time"
        ],
        "Resource-Based Model (Cobb GA)": [
            "217.14 ± 0.65 days",
            "126.86 ± 0.65 days",
            "32.86 ± 0.65 days",
            "$561,967.72 ± $1,072.31",
            "$0.00",
            "$65,711.31 ± $1,298.80",
            "$496,256.41 ± $1,094.68",
            "1275.8 ± 6.9 s (~21.2 min)"
        ],
        "Mode-Based Model (Cobb MILP)": [
            "220.33 days",
            "123.67 days",
            "29.70 days",
            "$553,426.94 ⭐ (Best Labor Cost)",
            "$0.00",
            "$59,340.00",
            "$494,086.94 ⭐ (Best Total Cost)",
            "301.2 s (~5.0 min)"
        ],
        "Time-Based Model (Linear CP-SAT)": [
            "213.00 days ⭐ (Fastest Schedule)",
            "131.00 days",
            "37.00 days ⭐ (Best Margin)",
            "$584,970.19",
            "$0.00",
            "$74,000.00 ⭐ (Best Bonus)",
            "$510,970.19",
            "2.16 s ⭐ (Ultra-Fast Execution)"
        ]
    })
    st.dataframe(df_single_paper, use_container_width=True, hide_index=True)
    
    st.markdown("---")
    st.subheader("2️⃣ Multi-Objective Optimization (Time-Cost Trade-off Pareto Front)")
    st.caption("Pareto evaluation over makespans 210 to 344 days. Hypervolume calculated against Nadir (344d, $600k) and Ideal (210d, $490k).")
    
    df_multi_paper = pd.DataFrame({
        "Performance Metric": [
            "Pareto Contribution (Points / %)",
            "Hypervolume Coverage (Area / %)",
            "Minimum Achieved Makespan",
            "Minimum Achieved Labor Cost",
            "Solver Execution Time"
        ],
        "Resource-Based Model (NSGA-II)": [
            "20.4 ± 61.2 pts (8.6%)",
            "0.7922 ± 0.0048 (71.9% ± 0.4%)",
            "221.6 ± 1.6 days ($564.5k)",
            "$501.6 ± 1.6k (302.1 days)",
            "840.1 ± 64.2 s (~14.0 min)"
        ],
        "Mode-Based Model (MILP CP-SAT)": [
            "32 pts (13.5%) ⭐",
            "0.8444 (76.6%) ⭐ (Best Dominance)",
            "214.0 days ($566.5k)",
            "$491.5k (344.0 days) ⭐",
            "1006.3 s (~16.7 min)"
        ],
        "Time-Based Model (Linear CP-SAT)": [
            "1 pt (0.4%)",
            "0.6491 (58.9%)",
            "210.0 days ($591.4k) ⭐ (Shortest Time)",
            "$506.2k (344.0 days)",
            "11.3 s ⭐ (0.32 s per candidate)"
        ]
    })
    st.dataframe(df_multi_paper, use_container_width=True, hide_index=True)
    
    st.markdown("---")
    st.subheader("3️⃣ Visual Comparison of Pareto Curves & Schedules")
    
    # Load and show pre-generated comparison images if available
    img_pareto = os.path.join(base_dir, "outputs/comparison/multi/multiobjective_pareto_comparison.png")
    if not os.path.exists(img_pareto):
        img_pareto = os.path.join(base_dir, "outputs/comparison/multi/multiobjective_pareto_comparison.svg")
    
    if os.path.exists(img_pareto):
        st.image(img_pareto, caption="Pareto Fronts Comparison (Model A vs Model B vs Model C)", use_column_width=True)
    else:
        st.info("Comparison plot available in `outputs/comparison/multi/multiobjective_pareto_comparison.png` after running multi-objective benchmarks.")

# ==============================================================================
# 6. Footer
# ==============================================================================
st.markdown("---")
st.caption("🚀 Antigravity Advanced Agentic Coding | Project Crashing & Time-Cost Tradeoff Suite | Department of Mathematics, ITB")
