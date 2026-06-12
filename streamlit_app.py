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
    build_reference_no_crash_schedule, generate_gantt_comparison_plot as base_gantt
)
import preprocessing

from cobb_model import load_data as load_data_cobb, ResourceBasedScheduling, generate_gantt_comparison_plot as cobb_gantt

from pymoo.algorithms.soo.nonconvex.ga import GA
from pymoo.algorithms.moo.nsga2 import NSGA2
from pymoo.operators.crossover.sbx import SBX
from pymoo.operators.mutation.pm import PM
from pymoo.termination import get_termination
from pymoo.optimize import minimize
from pymoo.core.termination import Termination
from pymoo.termination.ftol import MultiObjectiveSpaceTermination
from pymoo.termination.robust import RobustTermination

class CombinedTermination(Termination):
    def __init__(self, t1, t2):
        super().__init__()
        self.t1 = t1
        self.t2 = t2
    def _update(self, algorithm):
        return max(self.t1.update(algorithm), self.t2.update(algorithm))

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

model_choice = st.sidebar.selectbox("Select Model", ["Base (Linear CP-SAT)", "Cobb-Douglas (GA)", "Cobb-Douglas (NSGA-II Multi-Objective)", "Hybrid (Preproc + CP-SAT)"])

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
        activity_data = read_json(os.path.join(base_dir, "data/activity_data_v3.json"))
        resource_capacity = read_json(os.path.join(base_dir, "data/resource_capacity_v3.json"))
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
        preprocessing.preprocess()
        
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
            
    elif model_choice == "Cobb-Douglas (GA)":
        status_placeholder.info("Running Genetic Algorithm...")
        tasks, prec, res_data, N, K_i = load_data_cobb(
            path_tasks=os.path.join(base_dir, "implementasi-cobb/data_tasks.csv"),
            path_precedence=os.path.join(base_dir, "implementasi-cobb/data_precedence.csv"),
            path_assignments=os.path.join(base_dir, "implementasi-cobb/data_assignments.csv"),
        )
        prob = ResourceBasedScheduling(
            tasks=tasks, precedence=prec, resources=res_data, N=N, K_i=K_i,
            T_max=target_end_date, mode=mode, budget_limit=budget_limit, c_late=c_late, c_early=c_early,
            current_day=current_day
        )
        algorithm = GA(pop_size=pop_size, crossover=SBX(prob=0.9, eta=15), mutation=PM(eta=20))
        termination = get_termination("n_gen", n_gen)
        
        with st_redirect(verbose_placeholder):
            res_ga = minimize(prob, algorithm, termination, seed=42, verbose=True)
            
        st.session_state.ga_res = res_ga
        st.session_state.ga_prob = prob
        st.session_state.ga_tasks = tasks
        st.session_state.ga_res_data = res_data
        st.session_state.optimizing = False
        st.rerun()

    elif model_choice == "Cobb-Douglas (NSGA-II Multi-Objective)":
        status_placeholder.info("Running NSGA-II Multi-Objective...")
        tasks, prec, res_data, N, K_i = load_data_cobb(
            path_tasks=os.path.join(base_dir, "implementasi-cobb/data_tasks.csv"),
            path_precedence=os.path.join(base_dir, "implementasi-cobb/data_precedence.csv"),
            path_assignments=os.path.join(base_dir, "implementasi-cobb/data_assignments.csv"),
        )
        problem_moo = ResourceBasedScheduling(
            tasks=tasks, precedence=prec, resources=res_data, N=N, K_i=K_i,
            alpha=0.7, beta=0.7, x_min=1.0, tau_min=0.0, tau_max=4.0, D_min_ratio=0.5,
            T_max=target_end_date, current_day=current_day, overtime_mult=1.5, hours_per_day=8,
            mode="multiobjective"
        )
        algorithm_moo = NSGA2(
            pop_size=pop_size, crossover=SBX(prob=0.9, eta=15), mutation=PM(eta=20),
            eliminate_duplicates=True,
        )
        t_robust = RobustTermination(MultiObjectiveSpaceTermination(tol=0.002, n_skip=5), period=30)
        t_max_gen = get_termination("n_gen", n_gen)
        termination_moo = CombinedTermination(t_robust, t_max_gen)
        
        with st_redirect(verbose_placeholder):
            res_moo = minimize(problem_moo, algorithm_moo, termination_moo, seed=42, verbose=True)
            
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
        
        baseline = build_reference_no_crash_schedule(
            st.session_state.base_act_data, st.session_state.base_res_req, 
            st.session_state.base_res_cap, st.session_state.base_pred, current_day, 60.0, 1
        )
        out_png = os.path.join(base_dir, "outputs/st_base_gantt.png")
        os.makedirs(os.path.dirname(out_png), exist_ok=True)
        base_gantt(baseline, res["schedule"], current_day, out_png)
        st.image(out_png, caption="Gantt Comparison")

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
        
        baseline = build_reference_no_crash_schedule(
            st.session_state.hyb_act_data, st.session_state.hyb_res_req, 
            st.session_state.hyb_res_cap, st.session_state.hyb_pred, current_day, 60.0, 1
        )
        out_png = os.path.join(base_dir, "outputs/st_hybrid_gantt.png")
        os.makedirs(os.path.dirname(out_png), exist_ok=True)
        base_gantt(baseline, res["schedule"], current_day, out_png)
        st.image(out_png, caption="Gantt Comparison")

if "ga_res" in st.session_state:
    res_ga = st.session_state.ga_res
    prob = st.session_state.ga_prob
    if res_ga.X is not None:
        st.success("Optimization finished!")
        P = prob.P
        x_opt = res_ga.X
        x_ik_opt = x_opt[0:P]
        tau_ik_opt = x_opt[P:2*P]
        D_ik_opt, D_i_opt = prob.compute_durations(x_opt)
        s_opt, f_opt = prob.forward_pass(D_i_opt)
        
        st.metric("Makespan", f"{np.max(f_opt):.2f} days")
        
        df_var = pd.DataFrame({
            "Resource": st.session_state.ga_res_data["resource_name"],
            "x (Crowding)": x_ik_opt,
            "tau (Overtime)": tau_ik_opt,
            "Original Duration": st.session_state.ga_res_data["D_base_ik"],
            "Crashed Duration": D_ik_opt
        })
        st.subheader("Cobb-Douglas Crashing Parameters")
        st.dataframe(df_var)
        
        out_png = os.path.join(base_dir, "outputs/st_cobb_ga_gantt.png")
        os.makedirs(os.path.dirname(out_png), exist_ok=True)
        cobb_gantt(st.session_state.ga_tasks, prob.s_baseline, prob.f_baseline, s_opt, f_opt, current_day, out_png)
        st.image(out_png, caption="Gantt Comparison")
    else:
        st.error("No feasible solution found.")

if "nsga_res" in st.session_state:
    res_moo = st.session_state.nsga_res
    problem_moo = st.session_state.nsga_prob
    if res_moo.F is not None:
        st.success("Optimization finished!")
        F = res_moo.F
        sorted_indices = np.argsort(F[:, 0])
        F_sorted = F[sorted_indices]
        X_sorted = res_moo.X[sorted_indices]
        
        df_pareto = pd.DataFrame({
            "Makespan (days)": F_sorted[:, 0],
            "Labor Cost ($)": F_sorted[:, 1]
        })
        
        st.subheader("Pareto Front")
        
        fig, ax = plt.subplots(figsize=(8, 4))
        ax.plot(F_sorted[:, 0], F_sorted[:, 1], marker='o', linestyle='-')
        ax.set_xlabel('Makespan (days)')
        ax.set_ylabel('Labor Cost ($)')
        ax.grid(True)
        st.pyplot(fig)
        
        st.write("### Select a Point on the Pareto Front")
        point_idx = st.slider("Select Index of Solution", 0, len(F_sorted)-1, 0)
        
        selected_X = X_sorted[point_idx]
        P = problem_moo.P
        x_ik_opt = selected_X[0:P]
        tau_ik_opt = selected_X[P:2*P]
        D_ik_opt, D_i_opt = problem_moo.compute_durations(selected_X)
        s_opt, f_opt = problem_moo.forward_pass(D_i_opt)
        
        col1, col2 = st.columns(2)
        col1.metric("Makespan", f"{F_sorted[point_idx, 0]:.2f} days")
        col2.metric("Labor Cost", f"${F_sorted[point_idx, 1]:.2f}")
        
        df_var = pd.DataFrame({
            "Resource": st.session_state.nsga_res_data["resource_name"],
            "x (Crowding)": x_ik_opt,
            "tau (Overtime)": tau_ik_opt,
            "Original Duration": st.session_state.nsga_res_data["D_base_ik"],
            "Crashed Duration": D_ik_opt
        })
        st.subheader("Crashing Parameters for Selected Point")
        st.dataframe(df_var)
        
        out_png = os.path.join(base_dir, "outputs/st_cobb_moo_gantt.png")
        os.makedirs(os.path.dirname(out_png), exist_ok=True)
        cobb_gantt(st.session_state.nsga_tasks, problem_moo.s_baseline, problem_moo.f_baseline, s_opt, f_opt, current_day, out_png)
        st.image(out_png, caption="Gantt Comparison for Selected Solution")
    else:
        st.error("No feasible solutions found.")
