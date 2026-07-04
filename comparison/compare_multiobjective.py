"""
compare_multiobjective.py — Multi-Objective Time-Cost Pareto Front Comparison
=============================================================================

Compares three algorithmic paradigms for multi-objective project crashing:
  Scenario A : Continuous Cobb-Douglas  + NSGA-II  (Serial Schedule Generation Scheme)
  Scenario B : Discretized Cobb-Douglas + MILP     (CP-SAT integer, ε-constraint method)
  Scenario C : Linearized Preprocessing + CP-SAT   (linear crash cost, ε-constraint method)

All three scenarios use identical model parameters (alpha, beta, x_max, tau_max, …)
and identical CSV / JSON data sources, enforcing mathematical comparability.

Outputs written to:
  outputs/comparison/multi/multiobjective_pareto_data.json
  outputs/comparison/multi/multiobjective_pareto_comparison.png
  outputs/comparison/multi/multiobjective_pareto_A_ga_cobb.png
  outputs/comparison/multi/multiobjective_pareto_B_milp_cobb.png
  outputs/comparison/multi/multiobjective_pareto_C_cpsat.png
  outputs/comparison/multi/A_ga_cobb_pareto.json
  outputs/comparison/multi/B_milp_cobb_pareto.json
  outputs/comparison/multi/C_cpsat_pareto.json

Usage:
  python compare_multiobjective.py
"""

import os
import sys
if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
import time
import json
import warnings
warnings.filterwarnings("ignore")

# ── Path Setup ────────────────────────────────────────────────────────────────
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
ROOT_DIR   = os.path.dirname(SCRIPT_DIR)

COBB_DIR        = os.path.join(ROOT_DIR, "implementasi-cobb")
BASE_SOLVER_DIR = os.path.join(ROOT_DIR, "implementasi-base")
HYBRID_DIR      = os.path.join(ROOT_DIR, "implementasi-hybrid")
OUTPUTS_DIR     = os.path.join(ROOT_DIR, "outputs", "comparison", "multi")

# Insert paths at module level so child processes created by ProcessPoolExecutor
# (which fork/spawn from this process) also inherit the correct import paths.
for _d in [COBB_DIR, BASE_SOLVER_DIR, HYBRID_DIR]:
    if _d not in sys.path:
        sys.path.insert(0, _d)

os.makedirs(OUTPUTS_DIR, exist_ok=True)


# ════════════════════════════════════════════════════════════════════════════
# SETTINGS  ← edit here
# ════════════════════════════════════════════════════════════════════════════
PARALLEL_EXECUTION = True   # Run Scenarios A, B, C in parallel across CPU cores

# ε-constraint grid for Scenarios B & C (days, inclusive)
T_MIN_TARGET  = 210         # lowest deadline to attempt (captures physical minimum makespan)
T_MAX_TARGET  = 344         # baseline CPM makespan (upper bound: no crashing)
EPSILON_STEP  = 4           # step size in days (approx. 34 solver calls per scenario)

# Scenario A — NSGA-II hyperparameters
GA_POP_SIZE   = 1000
GA_MAX_GEN    = 500
GA_TOL        = 0.0005      # convergence: relative change in hypervolume indicator
GA_PERIOD     = 20          # consecutive gens under tol before stopping
GA_SEED       = 42

# Per-step time limit for ε-constraint (Scenarios B and C)
MILP_TIME_LIMIT  = 30.0     # seconds per deadline target (Scenario B)
CPSAT_TIME_LIMIT = 30.0     # seconds per deadline target (Scenario C)

# Cobb-Douglas / shared model parameters (identical to compare_scenarios.py)
ALPHA         = 0.7
BETA          = 0.7
X_MIN         = 1.0
X_MAX         = 2.0
TAU_MIN       = 0.0
TAU_MAX       = 4.0
D_MIN_RATIO   = 0.5
OVERTIME_MULT = 1.5
HOURS_PER_DAY = 8
CURRENT_DAY   = 0
# c_late / c_early unused in multi-objective but passed to constructors that require them
C_LATE        = 5000.0
C_EARLY       = 2000.0


# ════════════════════════════════════════════════════════════════════════════
# HELPERS
# ════════════════════════════════════════════════════════════════════════════

def _hline(char="─", width=72):
    print(char * width)


def _section(title):
    print()
    _hline("═")
    print(f"  {title}")
    _hline("═")


def _compute_cpm_baseline(act: dict, preds: dict) -> float:
    """Pure CPM forward pass (precedence-only, no resource constraints).

    Mirrors ``ResourceBasedScheduling._forward_pass_raw`` and
    ``compare_scenarios._compute_cpm_baseline`` so that Scenario C's baseline
    makespan is identical to Scenarios A & B (344 days, not the resource-
    constrained 345 days from build_reference_no_crash_schedule).

    Parameters
    ----------
    act   : activity_data dict  (keys = activity id strings)
    preds : predecessors dict produced by build_predecessors()
            maps activity_id → list of predecessor activity_ids
    """
    durations = {a: int(act[a].get("activity_normal_time", 0)) for a in act}
    finish    = {a: 0.0 for a in act}

    for _ in range(len(act) + 1):
        changed = False
        for a in act:
            earliest_start = max(
                (finish[p] for p in preds.get(a, [])),
                default=0.0,
            )
            new_finish = earliest_start + durations[a]
            if new_finish > finish[a] + 1e-9:
                finish[a] = new_finish
                changed = True
        if not changed:
            break

    return float(max(finish.values())) if finish else 0.0


def _filter_non_dominated(points):
    """Return the Pareto-efficient subset of (makespan, cost) pairs.

    For project crashing the trade-off is:
        shorter makespan  ↔  higher total cost
    So the Pareto front, when sorted by makespan ascending, must have
    strictly decreasing cost.  Any point that is not dominated (i.e. there
    exists no other point with BOTH lower makespan AND lower cost) is kept.

    Implementation: sort by (makespan ASC, cost ASC), then sweep left-to-right
    keeping a running minimum cost.  A point is non-dominated iff its cost is
    strictly below the minimum seen so far for all shorter makespans.
    """
    if not points:
        return []
    sorted_pts = sorted(points, key=lambda p: (p[0], p[1]))
    pareto = []
    min_cost = float("inf")
    for ms, cost in sorted_pts:
        if cost < min_cost - 1e-6:
            pareto.append([round(float(ms), 2), round(float(cost), 2)])
            min_cost = cost
    return pareto


# ════════════════════════════════════════════════════════════════════════════
# WORKER WRAPPER  (captures child-process stdout/stderr for parallel display)
# ════════════════════════════════════════════════════════════════════════════

def _run_worker(runner_func):
    """Run runner_func() in a child process, capturing all printed output.

    Returns (result, stdout_text, traceback_text_or_None).
    This pattern mirrors compare_scenarios.py so parallel output is
    collected and printed cleanly after each future completes.
    """
    import io
    buf = io.StringIO()
    old_out, old_err = sys.stdout, sys.stderr
    try:
        sys.stdout = buf
        sys.stderr = buf
        result = runner_func()
        return result, buf.getvalue(), None
    except Exception:
        import traceback
        return None, buf.getvalue(), traceback.format_exc()
    finally:
        sys.stdout = old_out
        sys.stderr = old_err


# ════════════════════════════════════════════════════════════════════════════
# SCENARIO A  —  Continuous Cobb-Douglas + NSGA-II
# ════════════════════════════════════════════════════════════════════════════

def run_scenario_A_moo():
    _section("SCENARIO A  |  Continuous Cobb-Douglas  +  NSGA-II")

    import numpy as np
    from cobb_model import load_data, data_path, ResourceBasedScheduling, solve

    tasks, precedence, resources, N, K_i = load_data(
        path_tasks=data_path("data_tasks.csv"),
        path_precedence=data_path("data_precedence.csv"),
        path_assignments=data_path("data_assignments.csv"),
    )

    problem = ResourceBasedScheduling(
        tasks=tasks, precedence=precedence, resources=resources, N=N, K_i=K_i,
        alpha=ALPHA, beta=BETA, x_min=X_MIN, x_max=X_MAX,
        tau_min=TAU_MIN, tau_max=TAU_MAX,
        D_min_ratio=D_MIN_RATIO, T_max=T_MAX_TARGET, current_day=CURRENT_DAY,
        overtime_mult=OVERTIME_MULT, hours_per_day=HOURS_PER_DAY,
        mode="multiobjective",
        c_late=C_LATE, c_early=C_EARLY,   # accepted by constructor; unused in MOO _evaluate
    )

    baseline_makespan = float(np.max(problem.f_baseline))
    print(f"  [A] Baseline makespan : {baseline_makespan:.1f} days")
    print(f"  [A] Decision vars     : {problem.P} (x,τ) pairs + {N} priority vars = {2*problem.P + N} total")
    print(f"  [A] NSGA-II           : pop={GA_POP_SIZE}  max_gen={GA_MAX_GEN}  "
          f"tol={GA_TOL}  period={GA_PERIOD}  seed={GA_SEED}")
    print("  [A] Solving Pareto front …")

    t0 = time.perf_counter()
    res = solve(
        problem,
        pop_size=GA_POP_SIZE,
        seed=GA_SEED,
        verbose=False,
        max_gen=GA_MAX_GEN,
        tol=GA_TOL,
        period=GA_PERIOD,
    )
    elapsed = time.perf_counter() - t0

    # solve() returns the raw pymoo Result object when mode == "multiobjective"
    if res is None or res.F is None or len(res.F) == 0:
        print("  ✗  [A] NSGA-II found no feasible Pareto solutions.")
        return None

    # res.F shape: (n_solutions, 2) — columns are [makespan, labor_cost]
    raw_points = [(float(row[0]), float(row[1])) for row in res.F]
    pareto_points = _filter_non_dominated(raw_points)

    print(f"  ✓  [A] Solve time   : {elapsed:.1f} s")
    print(f"  ✓  [A] Raw NSGA-II solutions  : {len(raw_points)}")
    print(f"  ✓  [A] Non-dominated Pareto   : {len(pareto_points)}")
    if pareto_points:
        print(f"     Min Makespan pt : {pareto_points[0][0]:.1f} d  @ ${pareto_points[0][1]:,.0f}")
        print(f"     Min Cost pt     : {pareto_points[-1][0]:.1f} d  @ ${pareto_points[-1][1]:,.0f}")

    return {
        "scenario": "A",
        "method": "NSGA-II (Continuous Cobb-Douglas)",
        "baseline_makespan": baseline_makespan,
        "pareto_points": pareto_points,   # [[makespan, cost], …] sorted by makespan asc
        "raw_points": raw_points,         # All evaluated candidate points in final gen
        "num_raw": len(raw_points),
        "num_points": len(pareto_points),
        "min_makespan_pt": pareto_points[0]  if pareto_points else None,
        "min_cost_pt":     pareto_points[-1] if pareto_points else None,
        "solve_time_s": round(elapsed, 2),
    }


# ════════════════════════════════════════════════════════════════════════════
# SCENARIO B  —  Discretized Cobb-Douglas + MILP (ε-Constraint)
# ════════════════════════════════════════════════════════════════════════════

def run_scenario_B_moo():
    _section("SCENARIO B  |  Discretized Cobb-Douglas  +  MILP  (ε-Constraint)")

    import numpy as np
    from cobb_model import load_data, data_path, ResourceBasedScheduling
    from solver_milp import solve_milp_cobb_douglas

    tasks, precedence, resources, N, K_i = load_data(
        path_tasks=data_path("data_tasks.csv"),
        path_precedence=data_path("data_precedence.csv"),
        path_assignments=data_path("data_assignments.csv"),
    )

    # Instantiate a lightweight problem object purely to read the CPM baseline makespan.
    # Use mode="bonus_penalty" (a valid single-objective mode) to avoid triggering
    # n_obj=2 in pymoo Problem, since we only need f_baseline here.
    _prob = ResourceBasedScheduling(
        tasks=tasks, precedence=precedence, resources=resources, N=N, K_i=K_i,
        alpha=ALPHA, beta=BETA, x_min=X_MIN, x_max=X_MAX,
        tau_min=TAU_MIN, tau_max=TAU_MAX,
        D_min_ratio=D_MIN_RATIO, T_max=T_MAX_TARGET, current_day=CURRENT_DAY,
        overtime_mult=OVERTIME_MULT, hours_per_day=HOURS_PER_DAY,
        mode="bonus_penalty", c_late=C_LATE, c_early=C_EARLY,
    )
    baseline_makespan = float(np.max(_prob.f_baseline))
    print(f"  [B] Baseline makespan : {baseline_makespan:.1f} days")

    # Build ε grid: integers from T_MIN_TARGET to T_MAX_TARGET (inclusive) in EPSILON_STEP steps.
    # Always include T_MAX_TARGET so we get the no-crash reference point.
    targets = sorted(set(range(T_MIN_TARGET, T_MAX_TARGET + 1, EPSILON_STEP)) | {T_MAX_TARGET})
    print(f"  [B] ε-constraint grid : {len(targets)} targets  "
          f"({targets[0]}d … {targets[-1]}d, step={EPSILON_STEP}d)")
    print(f"  [B] Time limit        : {MILP_TIME_LIMIT}s per step")
    print("  [B] Solving …")

    raw_points = []
    t0 = time.perf_counter()

    for eps in targets:
        res = solve_milp_cobb_douglas(
            tasks, precedence, resources, N, K_i,
            alpha=ALPHA, beta=BETA, x_min=X_MIN, x_max=X_MAX,
            tau_min=TAU_MIN, tau_max=TAU_MAX, D_min_ratio=D_MIN_RATIO,
            T_max=eps, current_day=CURRENT_DAY,
            overtime_mult=OVERTIME_MULT, hours_per_day=HOURS_PER_DAY,
            mode="cost_with_deadline",
            # c_late / c_early not used in cost_with_deadline mode
            c_late=C_LATE, c_early=C_EARLY,
            time_limit=MILP_TIME_LIMIT,
            time_scale=100, dx=0.1, dtau=0.1,
        )
        if res is not None and res.get("makespan") is not None:
            ms   = float(res["makespan"])
            cost = float(res["labor_cost"])
            # Sanity check: feasibility guarantee — achieved makespan must be ≤ ε
            if ms <= eps + 1e-5:
                raw_points.append((ms, cost))
                print(f"     [B ε={eps:3d}d] → {ms:6.2f}d  | ${cost:12,.2f}")
            else:
                print(f"     [B ε={eps:3d}d] ✗ infeasible (achieved {ms:.2f}d > {eps}d)")
        else:
            print(f"     [B ε={eps:3d}d] ✗ no solution")

    elapsed = time.perf_counter() - t0
    pareto_points = _filter_non_dominated(raw_points)

    print(f"  ✓  [B] Solve time   : {elapsed:.1f} s")
    print(f"  ✓  [B] Feasible pts : {len(raw_points)}  →  Non-dominated Pareto: {len(pareto_points)}")
    if pareto_points:
        print(f"     Min Makespan pt : {pareto_points[0][0]:.1f} d  @ ${pareto_points[0][1]:,.0f}")
        print(f"     Min Cost pt     : {pareto_points[-1][0]:.1f} d  @ ${pareto_points[-1][1]:,.0f}")

    return {
        "scenario": "B",
        "method": "MILP (Discretized ε-constraint)",
        "baseline_makespan": baseline_makespan,
        "pareto_points": pareto_points,
        "raw_points": raw_points,
        "num_raw": len(raw_points),
        "num_points": len(pareto_points),
        "min_makespan_pt": pareto_points[0]  if pareto_points else None,
        "min_cost_pt":     pareto_points[-1] if pareto_points else None,
        "solve_time_s": round(elapsed, 2),
    }


# ════════════════════════════════════════════════════════════════════════════
# SCENARIO C  —  Linearized CP-SAT (ε-Constraint)
# ════════════════════════════════════════════════════════════════════════════

def run_scenario_C_moo():
    _section("SCENARIO C  |  Linearized CP-SAT  +  ε-Constraint")

    from solver_base import (
        build_predecessors,
        infer_activity_states_without_state_file,
        SolveConfig, build_model_and_solve,
    )
    from preprocessing import preprocess

    # ── Fairness Fix 1: dynamic preprocessing ──────────────────────────────
    # Crash-cost slopes are derived from x_max, tau_max, alpha, beta, overtime_mult.
    # By calling preprocess() here with the same live constants as A & B we
    # guarantee the linear approximation uses the same Cobb-Douglas parameters,
    # not whatever was frozen in the static JSON files on disk.
    print("  [C] Running preprocessing with live model parameters …")
    act, rr, rc = preprocess(
        alpha=ALPHA, beta=BETA,
        x_max=X_MAX, tau_max=TAU_MAX,
        overtime_mult=OVERTIME_MULT, hours_per_day=HOURS_PER_DAY,
    )

    preds, cycle_logs = build_predecessors(act, [], True)
    for log in cycle_logs:
        print(f"  [C preprocess] {log}")

    states, state_logs = infer_activity_states_without_state_file(
        act, rr, rc, preds, CURRENT_DAY, CPSAT_TIME_LIMIT, 1,
    )
    for log in state_logs:
        print(f"  [C state] {log[:100]}")

    # ── Fairness Fix 2: CPM baseline (same as A & B) ────────────────────────
    # build_reference_no_crash_schedule applies resource constraints → 345 days.
    # The CPM-only forward pass gives 344 days, matching A & B (and laporan.typ).
    baseline_makespan = _compute_cpm_baseline(act, preds)

    # Total normal labor cost (sum of W_{i,k}*r_k across all tasks).
    # This is the base cost from which the linear crash cost is measured.
    total_normal_cost = sum(
        float(a.get("activity_base_cost", 0.0)) for a in act.values()
    )

    print(f"  [C] Baseline makespan : {baseline_makespan:.1f} days  (CPM, same as A & B)")
    print(f"  [C] Total normal cost : ${total_normal_cost:,.2f}  (Σ W_ik * r_k, baseline x=1 τ=0)")

    targets = sorted(set(range(T_MIN_TARGET, T_MAX_TARGET + 1, EPSILON_STEP)) | {T_MAX_TARGET})
    print(f"  [C] ε-constraint grid : {len(targets)} targets  "
          f"({targets[0]}d … {targets[-1]}d, step={EPSILON_STEP}d)")
    print(f"  [C] Time limit        : {CPSAT_TIME_LIMIT}s per step")
    print("  [C] Solving …")

    raw_points = []
    t0 = time.perf_counter()

    for eps in targets:
        cfg = SolveConfig(
            target_end_date=eps, current_day=CURRENT_DAY,
            time_limit=CPSAT_TIME_LIMIT, num_workers=1,
            auto_fix_paint_trim_cycle=True, remove_edges=[],
            # c_late / c_early unused in cost_with_deadline mode
            c_late=C_LATE, c_early=C_EARLY,
        )
        res = build_model_and_solve(act, rr, rc, preds, states, cfg, mode="cost_with_deadline")
        status = res.get("status", "UNKNOWN")

        if status in ("OPTIMAL", "FEASIBLE"):
            ms          = float(res["makespan"])
            crash_cost  = float(res["total_crash_cost"])
            # Comparable cost = normal baseline labor + incremental crash cost.
            # This is what laporan.typ's Model C minimises and what makes the
            # comparison with A (total labor cost) apples-to-apples.
            comp_cost   = total_normal_cost + crash_cost

            if ms <= eps + 1e-5:
                raw_points.append((ms, comp_cost))
                print(f"     [C ε={eps:3d}d] → {ms:6.1f}d  | ${comp_cost:12,.2f}  "
                      f"(crash: ${crash_cost:,.2f})")
            else:
                print(f"     [C ε={eps:3d}d] ✗ infeasible (achieved {ms:.1f}d > {eps}d)")
        else:
            print(f"     [C ε={eps:3d}d] ✗ {status}")

    elapsed = time.perf_counter() - t0
    pareto_points = _filter_non_dominated(raw_points)

    print(f"  ✓  [C] Solve time   : {elapsed:.1f} s")
    print(f"  ✓  [C] Feasible pts : {len(raw_points)}  →  Non-dominated Pareto: {len(pareto_points)}")
    if pareto_points:
        print(f"     Min Makespan pt : {pareto_points[0][0]:.1f} d  @ ${pareto_points[0][1]:,.0f}")
        print(f"     Min Cost pt     : {pareto_points[-1][0]:.1f} d  @ ${pareto_points[-1][1]:,.0f}")

    return {
        "scenario": "C",
        "method": "CP-SAT (Linear ε-constraint)",
        "baseline_makespan": baseline_makespan,
        "total_normal_cost": total_normal_cost,
        "pareto_points": pareto_points,
        "raw_points": raw_points,
        "num_raw": len(raw_points),
        "num_points": len(pareto_points),
        "min_makespan_pt": pareto_points[0]  if pareto_points else None,
        "min_cost_pt":     pareto_points[-1] if pareto_points else None,
        "solve_time_s": round(elapsed, 2),
    }


# ════════════════════════════════════════════════════════════════════════════
# COMPARISON TABLE
# ════════════════════════════════════════════════════════════════════════════

def print_comparison(results):
    _section("MULTI-OBJECTIVE PARETO FRONT COMPARISON SUMMARY")

    valid = [r for r in results if r is not None]
    if not valid:
        print("  No results to compare.")
        return

    col_w = 34
    hdr = f"  {'Metric':<{col_w}}"
    for r in valid:
        scen = r["scenario"]
        label = {"A": "NSGA-II (Cts)", "B": "MILP (ε-cstr)", "C": "CP-SAT (ε-cstr)"}.get(scen, scen)
        hdr += f"  {scen}: {label:<16}"
    print(hdr)
    _hline()

    def row(label, vals):
        s = f"  {label:<{col_w}}"
        for v in vals:
            s += f"  {v:<22}"
        print(s)

    row("Baseline Makespan (days)",
        [f"{r['baseline_makespan']:.1f}" for r in valid])

    row("Non-Dominated Pareto Points",
        [str(r['num_points']) for r in valid])

    row("Raw Candidate Points",
        [str(r.get('num_raw', '—')) for r in valid])

    row("Min Makespan Achieved",
        [f"{r['min_makespan_pt'][0]:.1f}d (${r['min_makespan_pt'][1]/1e3:.1f}k)"
         if r['min_makespan_pt'] else "N/A"
         for r in valid])

    row("Min Cost Point",
        [f"{r['min_cost_pt'][0]:.1f}d (${r['min_cost_pt'][1]/1e3:.1f}k)"
         if r['min_cost_pt'] else "N/A"
         for r in valid])

    row("Total Solve Time (s)",
        [f"{r['solve_time_s']:.1f}" for r in valid])

    _hline()
    print("  * Y-axis definitions:")
    print("    A  : Total Labor Cost  Z = Σ D_ik · x_ik · U_ik · (8r_k + τ_ik·r'_k)  [exact]")
    print("    B  : Total Labor Cost  Z  (same formula, discretized on 0.1-step grid)")
    print("    C  : Comparable Cost   Z^(0) + Σ C_i·c_i  [Z^(0)=normal labor, C_i=crash slope]")


# ════════════════════════════════════════════════════════════════════════════
# PARETO PLOTTING (Combined & Individual)
# ════════════════════════════════════════════════════════════════════════════

def plot_pareto_fronts(results, output_dir):
    """Generate overlaid comparison chart AND individual Pareto charts."""
    import numpy as np
    import matplotlib.pyplot as plt

    valid = [r for r in results if r is not None and r.get("pareto_points")]
    if not valid:
        print("  [warn] No Pareto points to plot.")
        return

    styles = {
        "A": dict(color="#1f77b4", raw_color="#93c5fd", marker="o", linestyle="-",
                  title="Scenario A: NSGA-II Pareto Front (Continuous Cobb-Douglas)",
                  label="A: NSGA-II (Continuous Cobb-Douglas)", fname="multiobjective_pareto_A_ga_cobb.png"),
        "B": dict(color="#d62728", raw_color="#fca5a5", marker="s", linestyle="--",
                  title="Scenario B: MILP Pareto Front (Discretized ε-constraint)",
                  label="B: MILP (Discretized, ε-constraint)", fname="multiobjective_pareto_B_milp_cobb.png"),
        "C": dict(color="#2ca02c", raw_color="#86efac", marker="^", linestyle="-.",
                  title="Scenario C: CP-SAT Pareto Front (Linear approximation, ε-constraint)",
                  label="C: CP-SAT (Linear approx., ε-constraint)", fname="multiobjective_pareto_C_cpsat.png"),
    }

    # ── 1. Combined Overlaid Chart ──────────────────────────────────────────
    fig, ax = plt.subplots(figsize=(10, 6), dpi=150)

    for r in valid:
        scen = r["scenario"]
        pts  = np.array(r["pareto_points"])   # shape (n, 2): [[makespan, cost], …]
        st   = styles.get(scen, dict(color="black", marker="x", linestyle=":", label=f"Scenario {scen}"))
        ax.plot(
            pts[:, 0], pts[:, 1],
            color=st["color"], marker=st["marker"], linestyle=st["linestyle"],
            linewidth=2, markersize=6, label=st["label"], alpha=0.85,
        )

    ax.set_title("Multi-Objective Time-Cost Pareto Front Comparison\n"
                 "(Project Crashing: Cobb-Douglas vs. Discretized vs. Linear)",
                 fontsize=13, fontweight="bold", pad=12)
    ax.set_xlabel("Makespan (days)", fontsize=12, labelpad=8)
    ax.set_ylabel("Total Labor / Comparable Cost (USD)", fontsize=12, labelpad=8)
    ax.grid(True, linestyle=":", alpha=0.55)
    ax.legend(fontsize=10, frameon=True, facecolor="white", edgecolor="none")
    fig.tight_layout()

    out_combined = os.path.join(output_dir, "multiobjective_pareto_comparison.png")
    fig.savefig(out_combined)
    plt.close(fig)
    print(f"  ✓  Saved combined Pareto chart   → {out_combined}")

    # ── 2. Individual Charts per Scenario ───────────────────────────────────
    for r in valid:
        scen = r["scenario"]
        st = styles.get(scen)
        if not st:
            continue

        fig, ax = plt.subplots(figsize=(9, 5.5), dpi=150)
        
        # Plot raw candidate points if available
        if r.get("raw_points"):
            raw_pts = np.array(r["raw_points"])
            ax.scatter(
                raw_pts[:, 0], raw_pts[:, 1],
                color=st["raw_color"], marker=st["marker"], s=30, alpha=0.5,
                label="Raw Evaluated / Feasible Solutions", zorder=2
            )

        # Plot Pareto efficient front
        pts = np.array(r["pareto_points"])
        ax.plot(
            pts[:, 0], pts[:, 1],
            color=st["color"], marker=st["marker"], linestyle=st["linestyle"],
            linewidth=2.5, markersize=7, label="Non-Dominated Pareto Front", zorder=3
        )

        ax.set_title(st["title"], fontsize=12, fontweight="bold", pad=12)
        ax.set_xlabel("Makespan (days)", fontsize=11, labelpad=8)
        ax.set_ylabel("Total Labor / Comparable Cost (USD)", fontsize=11, labelpad=8)
        ax.grid(True, linestyle=":", alpha=0.55)
        ax.legend(fontsize=10, frameon=True, facecolor="white", edgecolor="none")
        fig.tight_layout()

        out_ind = os.path.join(output_dir, st["fname"])
        fig.savefig(out_ind)
        plt.close(fig)
        print(f"  ✓  Saved Scenario {scen} Pareto chart → {out_ind}")


# ════════════════════════════════════════════════════════════════════════════
# MAIN
# ════════════════════════════════════════════════════════════════════════════

def main():
    print()
    print("╔══════════════════════════════════════════════════════════════════════╗")
    print("║     MULTI-OBJECTIVE PROJECT CRASHING  —  3-SCENARIO BENCHMARK       ║")
    print("╠══════════════════════════════════════════════════════════════════════╣")
    print(f"║  ε-grid: {T_MIN_TARGET}–{T_MAX_TARGET}d (step={EPSILON_STEP}d)  |  "
          f"NSGA-II: pop={GA_POP_SIZE} gen={GA_MAX_GEN}  |  "
          f"{'PARALLEL' if PARALLEL_EXECUTION else 'SEQUENTIAL'}  ║")
    print("╚══════════════════════════════════════════════════════════════════════╝")

    scenarios = [
        ("A", run_scenario_A_moo),
        ("B", run_scenario_B_moo),
        ("C", run_scenario_C_moo),
    ]
    results = [None, None, None]

    t_global = time.perf_counter()

    if PARALLEL_EXECUTION:
        import concurrent.futures
        print("\n  ⚡ [PARALLEL] Launching Scenarios A, B, C simultaneously …\n")
        with concurrent.futures.ProcessPoolExecutor(max_workers=3) as executor:
            futures = [executor.submit(_run_worker, runner) for _, runner in scenarios]
            for idx, (label, _) in enumerate(scenarios):
                res, out_text, err_text = futures[idx].result()
                print(out_text, end="")
                if err_text:
                    print(f"\n  ✗  Scenario {label} raised an exception:\n{err_text}")
                results[idx] = res
        print(f"  ⚡ All 3 scenarios finished in {time.perf_counter() - t_global:.1f}s wall-clock time.")
    else:
        for idx, (label, runner) in enumerate(scenarios):
            try:
                results[idx] = runner()
            except Exception:
                import traceback
                print(f"\n  ✗  Scenario {label} failed:")
                traceback.print_exc()

    # ── Persist individual & combined Pareto JSON data ────────────────────────
    for r in results:
        if r is not None:
            scen = r["scenario"]
            fname_map = {"A": "A_ga_cobb_pareto.json", "B": "B_milp_cobb_pareto.json", "C": "C_cpsat_pareto.json"}
            out_scen = os.path.join(OUTPUTS_DIR, fname_map.get(scen, f"{scen}_pareto.json"))
            with open(out_scen, "w", encoding="utf-8") as fh:
                json.dump(r, fh, indent=2)
            print(f"  ✓  Saved Scenario {scen} JSON       → {out_scen}")

    out_json = os.path.join(OUTPUTS_DIR, "multiobjective_pareto_data.json")
    with open(out_json, "w", encoding="utf-8") as fh:
        json.dump(
            {
                "generated_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                "total_execution_time_s": round(time.perf_counter() - t_global, 2),
                "settings": {
                    "T_MIN_TARGET": T_MIN_TARGET,
                    "T_MAX_TARGET": T_MAX_TARGET,
                    "EPSILON_STEP": EPSILON_STEP,
                    "GA_POP_SIZE": GA_POP_SIZE,
                    "GA_MAX_GEN": GA_MAX_GEN,
                    "GA_TOL": GA_TOL,
                    "MILP_TIME_LIMIT": MILP_TIME_LIMIT,
                    "CPSAT_TIME_LIMIT": CPSAT_TIME_LIMIT,
                    "ALPHA": ALPHA, "BETA": BETA,
                    "X_MIN": X_MIN, "X_MAX": X_MAX,
                    "TAU_MIN": TAU_MIN, "TAU_MAX": TAU_MAX,
                    "OVERTIME_MULT": OVERTIME_MULT,
                    "HOURS_PER_DAY": HOURS_PER_DAY,
                    "CURRENT_DAY": CURRENT_DAY,
                },
                "scenarios": [r for r in results if r is not None],
            },
            fh, indent=2,
        )
    print(f"  ✓  Saved combined Pareto data → {out_json}")

    # ── Pareto charts (combined & individual) ────────────────────────────────
    plot_pareto_fronts(results, OUTPUTS_DIR)

    # ── Console comparison table ──────────────────────────────────────────────
    print_comparison(results)

    total_elapsed = time.perf_counter() - t_global
    print()
    print(f"  Total benchmark time : {total_elapsed:.1f} s")
    _hline("═")
    print()


if __name__ == "__main__":
    main()
