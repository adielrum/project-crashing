import os
import sys
import time
import numpy as np
import pandas as pd
import streamlit as st
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches

# ==============================================================================
# 1. Path & Module Configuration
# ==============================================================================
base_dir = os.path.abspath(os.path.dirname(__file__)) if "__file__" in dir() else os.path.abspath(".")

for folder in ["implementasi-base", "implementasi-resource", "implementasi-mode", "implementasi-time"]:
    fpath = os.path.join(base_dir, folder)
    if fpath not in sys.path:
        sys.path.insert(0, fpath)

from solver_base import (
    read_json, build_predecessors, infer_activity_states_without_state_file,
    SolveConfig, build_model_and_solve,
)
from cobb_model import (
    load_data as load_data_cobb, ResourceBasedScheduling, solve as solve_cobb,
)
from solver_milp import solve_milp_cobb_douglas

# ==============================================================================
# 2. Page Configuration
# ==============================================================================
st.set_page_config(
    page_title="Project Crashing Optimization — IDSC Dataset",
    page_icon="🏗️",
    layout="wide",
    initial_sidebar_state="expanded"
)

st.markdown("""
<style>
/* ── Global font ── */
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap');
html, body, [class*="css"] { font-family: 'Inter', sans-serif; }

/* ── Sidebar ── */
[data-testid="stSidebar"] {
    background: linear-gradient(160deg, #0f172a 0%, #1e293b 100%);
    color: #f1f5f9;
}
[data-testid="stSidebar"] * { color: #f1f5f9 !important; }
[data-testid="stSidebar"] .stSelectbox label,
[data-testid="stSidebar"] .stSlider label,
[data-testid="stSidebar"] .stNumberInput label,
[data-testid="stSidebar"] .stCheckbox label { color: #cbd5e1 !important; font-size: 0.85rem; }

/* ── Tab headers — always visible ── */
.stTabs [data-baseweb="tab-list"] {
    background: #1e293b;
    border-radius: 10px;
    padding: 6px;
    gap: 6px;
}
.stTabs [data-baseweb="tab"] {
    background: #334155;
    color: #f1f5f9 !important;
    border-radius: 8px;
    padding: 10px 22px;
    font-weight: 600;
    font-size: 0.9rem;
    border: none;
}
.stTabs [data-baseweb="tab"]:hover {
    background: #475569;
    color: #ffffff !important;
}
.stTabs [aria-selected="true"] {
    background: linear-gradient(135deg, #3b82f6, #6366f1) !important;
    color: #ffffff !important;
    box-shadow: 0 2px 8px rgba(99,102,241,0.4);
}
.stTabs [data-baseweb="tab-panel"] { padding-top: 24px; }

/* ── Metric cards ── */
[data-testid="stMetric"] {
    background: #1e293b;
    border: 1px solid #334155;
    border-radius: 10px;
    padding: 14px 18px;
}
[data-testid="stMetricLabel"] { color: #94a3b8 !important; font-size: 0.78rem; font-weight: 600; letter-spacing: 0.04em; text-transform: uppercase; }
[data-testid="stMetricValue"] { color: #f1f5f9 !important; font-size: 1.35rem; font-weight: 700; }
[data-testid="stMetricDelta"] { font-size: 0.8rem; }

/* ── Dataframe ── */
.stDataFrame { border-radius: 8px; overflow: hidden; }

/* ── Info / success boxes ── */
.stAlert { border-radius: 8px; }

/* ── Section headers ── */
h2, h3 { color: #f1f5f9 !important; }
h4 { color: #94a3b8 !important; }

/* ── Button ── */
.stButton > button[kind="primary"] {
    background: linear-gradient(135deg, #3b82f6, #6366f1);
    color: white;
    border: none;
    border-radius: 8px;
    font-weight: 700;
    letter-spacing: 0.03em;
    padding: 12px 0;
    width: 100%;
    transition: opacity 0.2s;
}
.stButton > button[kind="primary"]:hover { opacity: 0.88; }

/* ── Expander ── */
[data-testid="stExpander"] {
    background: #1e293b;
    border: 1px solid #334155;
    border-radius: 10px;
}
</style>
""", unsafe_allow_html=True)


# ==============================================================================
# 3. Helpers
# ==============================================================================
class _StdoutCapture:
    """Redirects stdout to a Streamlit code block for live solver logs."""
    def __init__(self, placeholder):
        self.placeholder = placeholder
        self.lines = []
    def write(self, text):
        stripped = text.strip()
        if stripped:
            self.lines.append(stripped)
            if len(self.lines) > 30:
                self.lines = self.lines[-30:]
            self.placeholder.code("\n".join(self.lines), language="text")
    def flush(self): pass
    def __enter__(self):
        self._old = sys.stdout
        sys.stdout = self
        return self
    def __exit__(self, *_):
        sys.stdout = self._old


def _data_paths():
    return (
        os.path.join(base_dir, "data/data_tasks.csv"),
        os.path.join(base_dir, "data/data_precedence.csv"),
        os.path.join(base_dir, "data/data_assignments.csv"),
    )


def _load_cobb():
    p_tasks, p_prec, p_assign = _data_paths()
    return load_data_cobb(p_tasks, p_prec, p_assign)


def _load_base_json():
    act  = read_json(os.path.join(base_dir, "data/activity_data.json"))
    cap  = read_json(os.path.join(base_dir, "data/resource_capacity.json"))
    req  = read_json(os.path.join(base_dir, "data/resource_requirements.json"))
    return act, cap, req


# ==============================================================================
# 4. Sidebar
# ==============================================================================
st.sidebar.title("🏗️ Project Crashing Suite")
st.sidebar.caption(r"IDSC Commercial Dataset — $N=110$ tasks, $T_{\text{base}}=344$ days")
st.sidebar.markdown("---")

MODELS = [
    "1 · Resource-Based — Single-Objective (GA + SSS)",
    "2 · Resource-Based — Multi-Objective (NSGA-II + SSS)",
    "3 · Mode-Based — Single-Objective (MILP CP-SAT)",
    "4 · Mode-Based — Multi-Objective (ε-constraint)",
    "5 · Time-Based — Single-Objective (Linear CP-SAT)",
    "6 · Time-Based — Multi-Objective (ε-constraint)",
]
model_choice = st.sidebar.selectbox("Select Model & Scheme", MODELS)

is_single = "Single" in model_choice
is_multi  = "Multi"  in model_choice
is_cobb   = "Resource" in model_choice
is_milp   = "Mode"     in model_choice
is_linear = "Time"     in model_choice

st.sidebar.markdown("### ⚙️ Parameters")

lock_paper = st.sidebar.checkbox(
    "🔒 Lock to Paper Parameters",
    value=True,
    help="Uses T_max=250, c_early=2000, c_late=5000, alpha=beta=0.7 as reported in Section 3.1.2"
)

if lock_paper and is_single:
    T_max     = 250
    c_early   = 2000.0
    c_late    = 5000.0
    alpha     = 0.7
    beta      = 0.7
    mode      = "bonus_penalty"
    budget    = 600000.0
    cur_day   = 20
    st.sidebar.markdown(r"$T_{\max}=250$ d · $c_{\text{early}}=$ \$2,000/d · $c_{\text{late}}=$ \$5,000/d · $\alpha=\beta=0.7$")
elif lock_paper and is_multi:
    T_max   = 344
    c_early = 0.0
    c_late  = 0.0
    alpha   = 0.7
    beta    = 0.7
    mode    = "cost_with_deadline"
    budget  = 700000.0
    cur_day = 20
    st.sidebar.markdown(r"$\varepsilon$ swept $210 \to 344$ d · $\Delta\varepsilon=4$ d · $\alpha=\beta=0.7$ · cost-min per step")
else:
    mode    = st.sidebar.selectbox("Objective Mode", ["bonus_penalty", "cost_with_deadline", "time_with_budget"])
    T_max   = st.sidebar.number_input(r"$T_{\max}$ (days)", min_value=210, max_value=344, value=250)
    c_early = st.sidebar.number_input(r"$c_{\text{early}}$ — Bonus ($/day early)", min_value=0.0, value=2000.0)
    c_late  = st.sidebar.number_input(r"$c_{\text{late}}$ — Penalty ($/day late)",  min_value=0.0, value=5000.0)
    alpha   = st.sidebar.slider(r"$\alpha$ — Overcrowding Elasticity", 0.0, 2.0, 0.7, 0.05)
    beta    = st.sidebar.slider(r"$\beta$ — Overtime Elasticity",      0.0, 2.0, 0.7, 0.05)
    budget  = st.sidebar.number_input("Budget Limit ($)", min_value=0.0, value=600000.0)
    cur_day = st.sidebar.number_input(r"Review Day $T_0$", min_value=0, value=20)

st.sidebar.markdown("### 🎛️ Solver Controls")

if is_cobb:
    fast = st.sidebar.checkbox(
        "⚡ Fast Web Mode",
        value=True,
        help="Pop=100, Gen=50 (~15s). Uncheck for full paper benchmark (Pop=1000, Gen=500, ~14 min)."
    )
    if fast:
        pop_size, n_gen = 100, 50
        st.sidebar.caption("Pop=100 · Gen=50 — quick demo (~15 s)")
    else:
        pop_size = st.sidebar.number_input("Population Size", 10, 5000, 1000)
        n_gen    = st.sidebar.number_input("Max Generations",  10, 2000, 500)
    time_lim = 120.0
elif is_milp and is_single:
    time_lim = st.sidebar.number_input("CP-SAT Time Limit (s)", 10.0, 600.0, 300.0)
elif is_milp and is_multi:
    eps_step  = st.sidebar.select_slider("ε Step Size (days)", [2, 4, 6, 8, 10], value=4)
    time_lim  = st.sidebar.number_input("CP-SAT Limit per ε-step (s)", 5.0, 120.0, 30.0)
elif is_linear and is_single:
    time_lim = st.sidebar.number_input("CP-SAT Time Limit (s)", 5.0, 300.0, 60.0)
elif is_linear and is_multi:
    eps_step = st.sidebar.select_slider("ε Step Size (days)", [2, 4, 6, 8, 10], value=4)
    time_lim = st.sidebar.number_input("CP-SAT Limit per ε-step (s)", 1.0, 30.0, 3.0)

st.sidebar.markdown("---")
run_btn = st.sidebar.button("▶  Run Optimization", type="primary", use_container_width=True)

# ==============================================================================
# 5. Main Page
# ==============================================================================
st.title("🏗️ Dynamic Project Crashing Dashboard")
st.markdown(
    r"Interactive reproduction of comparative analysis results from **Sections 3.1.1–3.1.2** of the thesis manuscript "
    r"on the IDSC commercial construction project ($N=110$ tasks, $T_{\text{base}}=344$ days, $\alpha=\beta=0.7$, $T_0=20$)."
)

tab_live, tab_bench = st.tabs([
    "🚀  Live Optimization & Schedule",
    "📊  Thesis Benchmark Tables (Paper Results)",
])

# ── Session state init ─────────────────────────────────────────────────────────
for key in ["single_res", "multi_res", "active_model"]:
    if key not in st.session_state:
        st.session_state[key] = None

# ==============================================================================
# TAB 1 — LIVE OPTIMIZATION
# ==============================================================================
with tab_live:

    if run_btn:
        # clear old results when model changes
        if st.session_state.active_model != model_choice:
            st.session_state.single_res = None
            st.session_state.multi_res  = None
        st.session_state.active_model = model_choice

        status_box = st.empty()
        log_box    = st.empty()

        # ──────────────────────────────────────────────────────────────────────
        # MODEL 1 — Resource-Based Single-Objective GA
        # ──────────────────────────────────────────────────────────────────────
        if "1 ·" in model_choice:
            status_box.info(f"Running GA + SSS — bonus_penalty mode (Pop={pop_size}, Gen={n_gen})…")
            t0 = time.time()
            tasks, prec, res_data, N, K_i = _load_cobb()
            prob = ResourceBasedScheduling(
                tasks=tasks, precedence=prec, resources=res_data, N=N, K_i=K_i,
                alpha=alpha, beta=beta, x_min=1.0, tau_min=0.0, tau_max=4.0,
                D_min_ratio=0.5, T_max=T_max, current_day=cur_day,
                overtime_mult=1.5, hours_per_day=8,
                mode="bonus_penalty", c_late=c_late, c_early=c_early,
            )
            with _StdoutCapture(log_box):
                sol = solve_cobb(prob, pop_size=pop_size, seed=42, verbose=True, max_gen=n_gen)
            elapsed = time.time() - t0
            status_box.success(f"Done in {elapsed:.1f} s")
            if sol:
                bonus   = c_early * max(0.0, T_max - sol["makespan"])
                penalty = c_late  * max(0.0, sol["makespan"] - T_max)
                st.session_state.single_res = dict(
                    model="Resource-Based (GA + SSS)",
                    makespan=sol["makespan"], labor_cost=sol["labor_cost"],
                    total_cost=sol["total_cost"], bonus=bonus, penalty=penalty,
                    solve_time=elapsed, tasks=tasks, res_data=res_data,
                    s=sol["s"], f=sol["f"],
                    x_ik=sol["x_ik"], tau_ik=sol["tau_ik"], D_ik=sol["D_ik"],
                )
                st.rerun()

        # ──────────────────────────────────────────────────────────────────────
        # MODEL 2 — Resource-Based Multi-Objective NSGA-II
        # ──────────────────────────────────────────────────────────────────────
        elif "2 ·" in model_choice:
            status_box.info(f"Running NSGA-II + SSS (Pop={pop_size}, Gen={n_gen})…")
            t0 = time.time()
            tasks, prec, res_data, N, K_i = _load_cobb()
            prob_moo = ResourceBasedScheduling(
                tasks=tasks, precedence=prec, resources=res_data, N=N, K_i=K_i,
                alpha=alpha, beta=beta, x_min=1.0, tau_min=0.0, tau_max=4.0,
                D_min_ratio=0.5, T_max=344, current_day=cur_day,
                overtime_mult=1.5, hours_per_day=8, mode="multiobjective",
            )
            with _StdoutCapture(log_box):
                sol_moo = solve_cobb(prob_moo, pop_size=pop_size, seed=42, verbose=True, max_gen=n_gen)
            elapsed = time.time() - t0
            status_box.success(f"Done in {elapsed:.1f} s")
            if sol_moo is not None and hasattr(sol_moo, 'F') and sol_moo.F is not None and len(sol_moo.F) > 0:
                pts = np.array(sol_moo.F)  # shape (n_solutions, 2): [makespan, labor_cost]
                st.session_state.multi_res = dict(
                    model="Resource-Based (NSGA-II + SSS)",
                    pts=pts, solve_time=elapsed,
                )
                st.rerun()

        # ──────────────────────────────────────────────────────────────────────
        # MODEL 3 — Mode-Based Single-Objective MILP CP-SAT
        # ──────────────────────────────────────────────────────────────────────
        elif "3 ·" in model_choice:
            status_box.info(f"Running Mode-Based MILP CP-SAT (T_max={T_max}, time_limit={time_lim}s)…")
            t0 = time.time()
            tasks, prec, res_data, N, K_i = _load_cobb()
            with _StdoutCapture(log_box):
                sol = solve_milp_cobb_douglas(
                    tasks=tasks, precedence=prec, resources=res_data, N=N, K_i=K_i,
                    alpha=alpha, beta=beta, dx=0.1, dtau=0.1,
                    T_max=T_max, current_day=cur_day,
                    mode="bonus_penalty", c_late=c_late, c_early=c_early,
                    time_limit=time_lim,
                )
            elapsed = time.time() - t0
            status_box.success(f"Done in {elapsed:.1f} s")
            if sol and isinstance(sol, dict) and "makespan" in sol:
                bonus   = c_early * max(0.0, T_max - sol["makespan"])
                penalty = c_late  * max(0.0, sol["makespan"] - T_max)
                st.session_state.single_res = dict(
                    model="Mode-Based (MILP CP-SAT)",
                    makespan=sol["makespan"], labor_cost=sol["labor_cost"],
                    total_cost=sol["total_cost"], bonus=bonus, penalty=penalty,
                    solve_time=elapsed, tasks=tasks, res_data=res_data,
                    s=sol["s"], f=sol["f"],
                    x_ik=sol["x_ik"], tau_ik=sol["tau_ik"], D_ik=sol["D_ik"],
                )
                st.rerun()

        # ──────────────────────────────────────────────────────────────────────
        # MODEL 4 — Mode-Based Multi-Objective MILP ε-constraint
        # ──────────────────────────────────────────────────────────────────────
        elif "4 ·" in model_choice:
            t0 = time.time()
            tasks, prec, res_data, N, K_i = _load_cobb()
            eps_vals = list(range(210, 345, eps_step))
            pts = []
            for idx, eps in enumerate(eps_vals):
                status_box.info(f"ε-constraint [{idx+1}/{len(eps_vals)}] — T_max={eps} days…")
                with _StdoutCapture(log_box):
                    s = solve_milp_cobb_douglas(
                        tasks=tasks, precedence=prec, resources=res_data, N=N, K_i=K_i,
                        alpha=alpha, beta=beta, dx=0.1, dtau=0.1,
                        T_max=eps, current_day=cur_day,
                        mode="cost_with_deadline", time_limit=time_lim,
                    )
                if s and isinstance(s, dict) and "makespan" in s:
                    pts.append((s["makespan"], s["labor_cost"]))
            elapsed = time.time() - t0
            status_box.success(f"Done — {len(pts)} Pareto points found")
            if pts:
                st.session_state.multi_res = dict(
                    model="Mode-Based MILP (ε-constraint)",
                    pts=np.array(pts), solve_time=elapsed,
                )
                st.rerun()

        # ──────────────────────────────────────────────────────────────────────
        # MODEL 5 — Time-Based Single-Objective Linear CP-SAT
        # ──────────────────────────────────────────────────────────────────────
        elif "5 ·" in model_choice:
            status_box.info(f"Running Time-Based Linear CP-SAT (T_max={T_max}, time_limit={time_lim}s)…")
            t0 = time.time()
            act, cap, req = _load_base_json()
            predecessors, _ = build_predecessors(act, [], True)
            states, _ = infer_activity_states_without_state_file(
                act, req, cap, predecessors, cur_day, 60.0, 1
            )
            cfg = SolveConfig(
                target_end_date=T_max, current_day=cur_day,
                time_limit=time_lim, num_workers=1,
                auto_fix_paint_trim_cycle=True, remove_edges=[],
                budget_limit=budget, c_late=c_late, c_early=c_early,
            )
            with _StdoutCapture(log_box):
                result = build_model_and_solve(act, req, cap, predecessors, states, cfg, mode="bonus_penalty")
            elapsed = time.time() - t0
            status_box.success(f"Done in {elapsed:.1f} s")
            if result and result.get("status") in ["OPTIMAL", "FEASIBLE"]:
                ms  = result["makespan"]
                lc  = result.get("total_crash_cost", 0.0)
                bon = c_early * max(0.0, T_max - ms)
                pen = c_late  * max(0.0, ms - T_max)
                st.session_state.single_res = dict(
                    model="Time-Based (Linear CP-SAT)",
                    makespan=ms, labor_cost=lc,
                    total_cost=lc - bon + pen,
                    bonus=bon, penalty=pen,
                    solve_time=elapsed,
                    schedule=result.get("schedule", []),
                )
                st.rerun()

        # ──────────────────────────────────────────────────────────────────────
        # MODEL 6 — Time-Based Multi-Objective Linear ε-constraint
        # ──────────────────────────────────────────────────────────────────────
        elif "6 ·" in model_choice:
            act, cap, req = _load_base_json()
            predecessors, _ = build_predecessors(act, [], True)
            states, _ = infer_activity_states_without_state_file(
                act, req, cap, predecessors, cur_day, 60.0, 1
            )
            eps_vals = list(range(210, 345, eps_step))
            pts = []
            t0 = time.time()
            for idx, eps in enumerate(eps_vals):
                status_box.info(f"ε-constraint [{idx+1}/{len(eps_vals)}] — T_max={eps} days…")
                cfg = SolveConfig(
                    target_end_date=eps, current_day=cur_day,
                    time_limit=time_lim, num_workers=1,
                    auto_fix_paint_trim_cycle=True, remove_edges=[],
                    budget_limit=None,
                )
                with _StdoutCapture(log_box):
                    r = build_model_and_solve(act, req, cap, predecessors, states, cfg, mode="cost_with_deadline")
                if r and r.get("status") in ["OPTIMAL", "FEASIBLE"]:
                    pts.append((r["makespan"], r["total_crash_cost"]))
            elapsed = time.time() - t0
            status_box.success(f"Done in {elapsed:.1f} s — {len(pts)} Pareto points found")
            if pts:
                st.session_state.multi_res = dict(
                    model="Time-Based Linear CP-SAT (ε-constraint)",
                    pts=np.array(pts), solve_time=elapsed,
                )
                st.rerun()

    # ──────────────────────────────────────────────────────────────────────────
    # DISPLAY — Single-Objective Results
    # ──────────────────────────────────────────────────────────────────────────
    res = st.session_state.single_res
    if res and is_single:
        st.markdown(f"### 📈 Results — {res['model']}")
        c1, c2, c3, c4, c5, c6 = st.columns(6)
        c1.metric("Makespan",    f"{res['makespan']:.2f} d",
                  delta=f"{344 - res['makespan']:.1f} d saved")
        c2.metric(r"$T_{\max} - s_{n+1}$ (Target Margin)", f"{T_max - res['makespan']:.2f} d")
        c3.metric("Labor Cost",    f"${res['labor_cost']:,.2f}")
        c4.metric("Bonus Earned",  f"${res['bonus']:,.2f}")
        c5.metric("Penalty",       f"${res['penalty']:,.2f}")
        c6.metric("Total Project Cost", f"${res['total_cost']:,.2f}")

        st.caption(f"Solve time: **{res['solve_time']:.2f} s**")

        # Activity summary (only for Cobb-based models that return s/f/x_ik)
        if "tasks" in res:
            st.markdown("### 📋 Crashed Activity Summary")
            tasks_df  = res["tasks"]
            res_df    = res["res_data"]
            s_arr     = np.array(res["s"])
            f_arr     = np.array(res["f"])
            x_ik      = np.array(res["x_ik"])
            tau_ik    = np.array(res["tau_ik"])
            D_ik      = np.array(res["D_ik"])

            rows = []
            for i in range(len(tasks_df)):
                name    = tasks_df.iloc[i]["task_name"]
                task_id = tasks_df.iloc[i]["task_id"]
                opt_dur = f_arr[i] - s_arr[i]
                base_dur = 0.0
                alloc_notes = []
                crashed = False
                for row_idx, r_row in res_df.iterrows():
                    ti = int(r_row["i"]) if "i" in r_row else -1
                    if ti != i:
                        continue
                    bd = float(r_row["D_base_ik"])
                    base_dur = max(base_dur, bd)
                    xi   = float(x_ik[i, row_idx]) if x_ik.ndim == 2 else 1.0
                    tau  = float(tau_ik[i, row_idx]) if tau_ik.ndim == 2 else 0.0
                    rname = r_row["resource_name"]
                    if xi > 1.05 or tau > 0.05:
                        crashed = True
                        alloc_notes.append(f"{rname}: x={xi:.2f}×, τ=+{tau:.1f}h")
                if crashed:
                    rows.append({
                        "Task ID":   task_id,
                        "Task Name": name,
                        "Start (d)": round(s_arr[i], 1),
                        "Finish (d)": round(f_arr[i], 1),
                        "Base Duration (d)": round(base_dur, 1),
                        "Opt Duration (d)":  round(opt_dur, 1),
                        "Days Saved": round(base_dur - opt_dur, 1),
                        "Resource Adjustments": " | ".join(alloc_notes),
                    })

            if rows:
                st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)
            else:
                st.info("No activities were crashed beyond baseline settings.")

        elif "schedule" in res:
            st.markdown("### 📋 Activity Schedule")
            st.dataframe(pd.DataFrame(res["schedule"]), use_container_width=True, hide_index=True)

    # ──────────────────────────────────────────────────────────────────────────
    # DISPLAY — Multi-Objective Results (Pareto Plot)
    # ──────────────────────────────────────────────────────────────────────────
    moo = st.session_state.multi_res
    if moo and is_multi:
        st.markdown(f"### 🌐 Pareto Front — {moo['model']}")
        st.caption(f"Completed in {moo['solve_time']:.1f} s")

        pts = np.array(moo["pts"])
        if pts.ndim == 2 and len(pts) > 0:
            pts = pts[pts[:, 0].argsort()]

            fig, ax = plt.subplots(figsize=(6, 3.2), facecolor="#0f172a")
            ax.set_facecolor("#1e293b")
            ax.plot(pts[:, 0], pts[:, 1] / 1e3, "o-", color="#60a5fa",
                    linewidth=2, markersize=5, markerfacecolor="#f1f5f9")
            ax.set_xlabel("Makespan (days)", color="#94a3b8", fontsize=9)
            ax.set_ylabel("Labor Cost ($k)", color="#94a3b8", fontsize=9)
            ax.set_title("Time–Cost Trade-off Pareto Front", color="#f1f5f9", fontsize=11, fontweight="bold")
            ax.tick_params(colors="#94a3b8", labelsize=8)
            for spine in ax.spines.values():
                spine.set_edgecolor("#334155")
            ax.grid(True, linestyle="--", alpha=0.3, color="#64748b")
            fig.tight_layout()
            col_plot, _ = st.columns([1, 1])
            with col_plot:
                st.pyplot(fig)

            df_pareto = pd.DataFrame({
                "Makespan (d)":   np.round(pts[:, 0], 2),
                "Labor Cost ($)": np.round(pts[:, 1], 2),
            })
            st.dataframe(df_pareto, use_container_width=True, hide_index=True)

    if not (res or moo):
        st.info("👈 Select a model from the sidebar and press **Run Optimization** to begin.")


# ==============================================================================
# TAB 2 — THESIS BENCHMARK TABLES
# ==============================================================================
with tab_bench:
    st.markdown("### 🏆 Empirical Benchmark Results from Manuscript (Section 3.1)")
    st.markdown(
        r"Exact figures on the IDSC commercial project dataset. "
        r"All runs: $\alpha=\beta=0.7$, $T_0=20$. "
        r"Multi-objective: $\varepsilon$ swept $210 \to 344$ days, $\Delta\varepsilon=4$ days (34 solver calls). "
        r"NSGA-II run **10 independent times** (Pop=1000, max Gen=500)."
    )

    # ── SINGLE-OBJECTIVE TABLE ─────────────────────────────────────────────────
    st.markdown("---")
    st.markdown("#### 1. Single-Objective Optimization — Bonus-Penalty Scalarization")
    st.markdown(
        r"Parameters: $T_{\max}=250$ days · $c_{\text{early}}=$ \$2,000/day · $c_{\text{late}}=$ \$5,000/day · $\alpha=\beta=0.7$ · $T_0=20$"
    )

    st.markdown(r"""
| Metric | Resource-Based (GA + SSS) | Mode-Based (MILP CP-SAT) | Time-Based (Linear CP-SAT) |
|:---|:---|:---|:---|
| Optimal Makespan $s_{n+1}$ | $217.14 \pm 0.65$ days | $220.33$ days | **$213.00$ days** |
| Rescue Margin $T_{\text{base}} - s_{n+1}$ | $126.86 \pm 0.65$ days | $123.67$ days | $131.00$ days |
| Target Margin $T_{\max} - s_{n+1}$ | $32.86 \pm 0.65$ days | $29.70$ days | **$37.00$ days** |
| Labor Cost $\sum z_i$ | \$561,967.72 $\pm$ \$1,072.31 | **\$553,426.94** | \$584,970.19 |
| Penalty $c_{\text{late}} \cdot \max\{0,\, s_{n+1} - T_{\max}\}$ | \$0.00 | \$0.00 | \$0.00 |
| Bonus $c_{\text{early}} \cdot \max\{0,\, T_{\max} - s_{n+1}\}$ | \$65,711.31 $\pm$ \$1,298.80 | \$59,340.00 | **\$74,000.00** |
| Total Project Cost | \$496,256.41 $\pm$ \$1,094.68 | **\$494,086.94** | \$510,970.19 |
| Solve Time | $1275.8 \pm 6.9$ s (~21.3 min) | $301.2$ s (~5.0 min) | **$2.16$ s** |
""")

    # ── MULTI-OBJECTIVE TABLE ──────────────────────────────────────────────────
    st.markdown("---")
    st.markdown("#### 2. Multi-Objective Optimization — Time–Cost Pareto Front")
    st.markdown(
        r"$\varepsilon$ swept $210 \to 344$ days with $\Delta\varepsilon=4$ days (34 solver calls). "
        r"Hypervolume bounding box: $\text{Area}_{\max} = 1.05 \times 1.05 = 1.1025$."
    )

    st.markdown(r"""
| Metric | Resource-Based (NSGA-II + SSS) | Mode-Based (MILP CP-SAT) | Time-Based (Linear CP-SAT) |
|:---|:---|:---|:---|
| Pareto Contribution $C_M$ (pts, avg/run) | $20.4 \pm 61.2$ | $32$ | $1$ |
| Normalized Contribution $C_M / (C_A+C_B+C_C)$ | $38.2\%$ | **$59.9\%$** | $1.9\%$ |
| Hypervolume Area (normalized, avg/run) | $0.7922 \pm 0.0048$ | **$0.8444$** | $0.6491$ |
| Hypervolume $\%$ ($\text{Area} / \text{Area}_{\max}$) | $71.9\% \pm 0.4\%$ | **$76.6\%$** | $58.9\%$ |
| Min Achieved Makespan | $221.6 \pm 1.6$ days (\$564.5k) | $214.0$ days (\$566.5k) | **$210.0$ days** (\$591.4k) |
| Min Achieved Labor Cost | \$501.6k $\pm$ \$1.6k (302.1 d) | **\$491.5k** (344.0 d) | \$506.2k (344.0 d) |
| Solve Time | $840.1 \pm 64.2$ s (~14.0 min) | $1006.3$ s (~16.8 min) | **$11.3$ s** (~0.33 s/pt) |
""")

    # ── PARETO VISUALIZATION ──────────────────────────────────────────────────
    st.markdown("---")
    st.markdown("#### 3. Pareto Front Visualization (Pre-Generated)")

    img_path = os.path.join(base_dir, "outputs/comparison/multi/multiobjective_pareto_comparison.png")
    if os.path.exists(img_path):
        col_img, _ = st.columns([2, 1])
        with col_img:
            st.image(
                img_path,
                caption=r"Pareto fronts: Resource-Based (NSGA-II + SSS) vs Mode-Based (MILP CP-SAT) vs Time-Based (Linear CP-SAT) | $\alpha=\beta=0.7$",
                use_column_width=True
            )
    else:
        st.info("Run `comparison/compare_multiobjective.py` to generate the Pareto comparison plot.")

# ==============================================================================
# 6. Footer
# ==============================================================================
st.markdown("---")
st.caption("Project Crashing & Time\u2013Cost Trade-off · Department of Mathematics, ITB · IDSC Singapore")
