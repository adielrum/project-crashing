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
import numpy as np
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
USE_CACHED_RESULTS = False       # Set False to re-run Scenario A with pop=1000, gen=500
USE_CACHED_DETERMINISTIC = True  # Load exact saved JSON results for deterministic B & C to save 16m solve time

# ε-constraint grid for Scenarios B & C (days, inclusive)
T_MIN_TARGET  = 210         # lowest deadline to attempt (captures physical minimum makespan)
T_MAX_TARGET  = 344         # baseline CPM makespan (upper bound: no crashing)
EPSILON_STEP  = 4           # step size in days (approx. 34 solver calls per scenario)

# Scenario A — NSGA-II hyperparameters
GA_POP_SIZE   = 1000
GA_MAX_GEN    = 500
GA_TOL        = 0.0005      # convergence: relative change in hypervolume indicator
GA_PERIOD     = 20          # consecutive gens under tol before stopping
GA_SEEDS      = [42, 43, 44, 45, 46, 47, 48, 49, 50, 51]  # 10 independent runs for statistical rigor
GA_SEED       = 42          # default single seed fallback

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
CURRENT_DAY   = 20       # project review day T_0 (tasks finishing ≤20 are locked)
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


def compute_hypervolume(pareto_pts, t_min, t_max, c_min, c_max, ref_t=1.05, ref_c=1.05):
    """Compute normalized 2D Hypervolume bounded by reference point (ref_t, ref_c)."""
    if not pareto_pts:
        return 0.0, 0.0
    norm_pts = []
    for ms, cost in pareto_pts:
        nt = (ms - t_min) / max(1e-9, t_max - t_min)
        nc = (cost - c_min) / max(1e-9, c_max - c_min)
        if nt < ref_t and nc < ref_c:
            norm_pts.append((nt, nc))
    if not norm_pts:
        return 0.0, 0.0
    
    norm_pts.sort(key=lambda p: (p[0], p[1]))
    area = 0.0
    for i, (nt, nc) in enumerate(norm_pts):
        next_t = norm_pts[i+1][0] if i + 1 < len(norm_pts) else ref_t
        width = next_t - nt
        height = ref_c - nc
        if width > 0 and height > 0:
            area += width * height
            
    max_possible_area = ref_t * ref_c
    hv_ratio = (area / max_possible_area) * 100.0
    return round(float(area), 4), round(float(hv_ratio), 2)


# ════════════════════════════════════════════════════════════════════════════
# WORKER WRAPPERS
# ════════════════════════════════════════════════════════════════════════════

def _run_worker_with_arg(runner_func, arg):
    """Run runner_func(arg) in a child process, capturing all printed output."""
    import io
    buf = io.StringIO()
    old_out, old_err = sys.stdout, sys.stderr
    try:
        sys.stdout = buf
        sys.stderr = buf
        result = runner_func(arg) if arg is not None else runner_func()
        return result, buf.getvalue(), None
    except Exception:
        import traceback
        return None, buf.getvalue(), traceback.format_exc()
    finally:
        sys.stdout = old_out
        sys.stderr = old_err


def _run_worker(runner_func):
    return _run_worker_with_arg(runner_func, None)


# ════════════════════════════════════════════════════════════════════════════
# SCENARIO A  —  Continuous Cobb-Douglas + NSGA-II
# ════════════════════════════════════════════════════════════════════════════

def run_scenario_A_moo(seed=GA_SEED):
    _section(f"SCENARIO A  |  Continuous Cobb-Douglas  +  NSGA-II (seed={seed})")

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
        c_late=C_LATE, c_early=C_EARLY,
    )

    baseline_makespan = float(np.max(problem.f_baseline))
    print(f"  [A seed={seed}] Baseline makespan : {baseline_makespan:.1f} days")
    print(f"  [A seed={seed}] NSGA-II           : pop={GA_POP_SIZE}  max_gen={GA_MAX_GEN}  seed={seed}")
    print(f"  [A seed={seed}] Solving Pareto front …")

    t0 = time.perf_counter()
    res = solve(
        problem,
        pop_size=GA_POP_SIZE,
        seed=seed,
        verbose=False,
        max_gen=GA_MAX_GEN,
        tol=GA_TOL,
        period=GA_PERIOD,
    )
    elapsed = time.perf_counter() - t0

    if res is None or res.F is None or len(res.F) == 0:
        print(f"  ✗  [A seed={seed}] NSGA-II found no feasible Pareto solutions.")
        return None

    raw_points = [(float(row[0]), float(row[1])) for row in res.F]
    pareto_points = _filter_non_dominated(raw_points)

    print(f"  ✓  [A seed={seed}] Solve time   : {elapsed:.1f} s")
    print(f"  ✓  [A seed={seed}] Non-dominated Pareto   : {len(pareto_points)}")
    if pareto_points:
        print(f"     Min Makespan pt : {pareto_points[0][0]:.1f} d  @ ${pareto_points[0][1]:,.0f}")
        print(f"     Min Cost pt     : {pareto_points[-1][0]:.1f} d  @ ${pareto_points[-1][1]:,.0f}")

    return {
        "scenario": "A",
        "seed": seed,
        "method": "NSGA-II (Continuous Cobb-Douglas)",
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
# SCENARIO B  —  Discretized Cobb-Douglas + MILP (ε-Constraint)
# ════════════════════════════════════════════════════════════════════════════

def run_scenario_B_moo():
    _section("SCENARIO B  |  Discretized Cobb-Douglas  +  MILP  (ε-Constraint)")

    cache_path = os.path.join(OUTPUTS_DIR, "B_milp_cobb_pareto.json")
    if USE_CACHED_DETERMINISTIC and os.path.exists(cache_path):
        print(f"  [B] Loading cached deterministic MILP results from {cache_path} …")
        with open(cache_path, "r", encoding="utf-8") as fh:
            return json.load(fh)

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

    cache_path = os.path.join(OUTPUTS_DIR, "C_cpsat_pareto.json")
    if USE_CACHED_DETERMINISTIC and os.path.exists(cache_path):
        print(f"  [C] Loading cached deterministic CP-SAT results from {cache_path} …")
        with open(cache_path, "r", encoding="utf-8") as fh:
            return json.load(fh)

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
        label = {"A": "NSGA-II (10-Run Avg)", "B": "MILP (ε-cstr)", "C": "CP-SAT (ε-cstr)"}.get(scen, scen)
        hdr += f"  {scen}: {label:<24}"
    print(hdr)
    _hline()

    def row(label, vals):
        s = f"  {label:<{col_w}}"
        for v in vals:
            s += f"  {v:<28}"
        print(s)

    row("Baseline Makespan (days)",
        [f"{r['baseline_makespan']:.1f}" for r in valid])

    row("Non-Dominated Pareto Points",
        [str(r['num_points']) for r in valid])

    row("Combined NDS Contribution",
        [r.get('nds_str', '—') for r in valid])

    row("Normalized Hypervolume (Area / %)",
        [r.get('hv_str', '—') for r in valid])

    row("Min Makespan Achieved",
        [r.get('min_ms_str', '—') for r in valid])

    row("Min Cost Point (No Crash)",
        [r.get('min_cost_str', '—') for r in valid])

    row("Total Solve Time (s)",
        [r.get('time_str', '—') for r in valid])

    _hline()
    print("  * Y-axis definitions:")
    print("    A  : Total Labor Cost  Z = Σ D_ik · x_ik · U_ik · (8r_k + τ_ik·r'_k)  [exact]")
    print("    B  : Total Labor Cost  Z  (same formula, discretized on 0.1-step grid)")
    print("    C  : Comparable Cost   Z^(0) + Σ C_i·c_i  [Z^(0)=normal labor, C_i=crash slope]")


import matplotlib.ticker as ticker

class OrderOfMagnitudeFormatter(ticker.ScalarFormatter):
    """Custom formatter to force 1e6 scale with exactly 2 decimal places."""
    def __init__(self, order=0, **kwargs):
        super().__init__(**kwargs)
        self.order = order
    def _set_order_of_magnitude(self):
        self.orderOfMagnitude = self.order
    def __call__(self, x, pos=None):
        try:
            xp = (x - getattr(self, 'offset', 0)) / (10 ** self.orderOfMagnitude)
            if abs(xp) < 1e-8:
                xp = 0.0
            return f"{xp:.2f}"
        except Exception:
            return super().__call__(x, pos)


# ════════════════════════════════════════════════════════════════════════════
# PARETO PLOTTING (Combined & Individual)
# ════════════════════════════════════════════════════════════════════════════

def plot_pareto_fronts(results, output_dir):
    """Generate overlaid comparison chart AND individual Pareto charts."""
    import numpy as np
    import matplotlib.pyplot as plt

    plt.rcParams.update({
        "font.family": "serif",
        "font.serif": ["New Computer Modern", "Computer Modern", "CMU Serif", "Times New Roman", "DejaVu Serif"],
        "font.size": 9,
        "axes.labelsize": 9,
        "axes.titlesize": 9,
        "legend.fontsize": 9,
        "xtick.labelsize": 9,
        "ytick.labelsize": 9,
        "mathtext.fontset": "cm"
    })

    valid = [r for r in results if r is not None and r.get("pareto_points")]
    if not valid:
        print("  [warn] No Pareto points to plot.")
        return

    styles = {
        "A": dict(color="#1f77b4", raw_color="#93c5fd", marker="o", linestyle="-",
                  label="Resource-Based Model", fname="multiobjective_pareto_A_ga_cobb"),
        "B": dict(color="#d62728", raw_color="#fca5a5", marker="s", linestyle="--",
                  label="Mode-Based Model", fname="multiobjective_pareto_B_milp_cobb"),
        "C": dict(color="#2ca02c", raw_color="#86efac", marker="^", linestyle="-.",
                  label="Time-Based Model", fname="multiobjective_pareto_C_cpsat"),
    }

    # ── 1. Combined Overlaid Chart ──────────────────────────────────────────
    # We set figsize=(4.14, 2.76) (66% of A4 width) so 9pt font scales to exactly 9pt when imported at width=66%!
    fig, ax = plt.subplots(figsize=(4.14, 2.76), dpi=600)
    ax.yaxis.set_major_formatter(OrderOfMagnitudeFormatter(order=6, useMathText=False))

    for r in valid:
        scen = r["scenario"]
        pts  = np.array(r["pareto_points"])   # shape (n, 2): [[makespan, cost], …]
        st   = styles.get(scen, dict(color="black", marker="x", linestyle=":", label=f"Scenario {scen}"))
        
        # Thin out Scenario A (NSGA-II) so consecutive points are at least 1.5 days apart to prevent solid blue 'tumor'
        if scen == "A" and len(pts) > 0:
            thinned_pts = []
            last_ms = -999.0
            for pt in pts:
                if abs(pt[0] - last_ms) >= 1.5:
                    thinned_pts.append(pt)
                    last_ms = pt[0]
            if not thinned_pts or thinned_pts[-1][0] != pts[-1][0]:
                thinned_pts.append(pts[-1])
            pts_to_plot = np.array(thinned_pts)
        else:
            pts_to_plot = pts

        # Add confidence shading for Scenario A across all 10 independent runs (hidden from legend)
        if scen == "A" and r.get("all_runs_pareto"):
            x_grid = np.linspace(210.0, 344.0, 200)
            c_low, c_high = [], []
            for x in x_grid:
                costs_at_x = []
                for run_pts in r["all_runs_pareto"]:
                    valid_c = [pt[1] for pt in run_pts if pt[0] <= x + 1e-5]
                    if valid_c:
                        costs_at_x.append(min(valid_c))
                if len(costs_at_x) >= 3:
                    c_low.append(min(costs_at_x))
                    c_high.append(max(costs_at_x))
                else:
                    c_low.append(np.nan)
                    c_high.append(np.nan)
            ax.fill_between(x_grid, c_low, c_high, color=st["color"], alpha=0.18, label="_nolegend_", zorder=1)

        ax.plot(
            pts_to_plot[:, 0], pts_to_plot[:, 1],
            color=st["color"], marker=st["marker"], linestyle=st["linestyle"],
            linewidth=1.2, markersize=2.3, label=st["label"], alpha=0.85, zorder=3
        )

    # Removed title per user request
    ax.set_xlabel("Time (days)", fontsize=9, labelpad=6)
    ax.set_ylabel("Labor Cost ($)", fontsize=9, labelpad=6)
    ax.grid(True, linestyle=":", alpha=0.55)
    ax.legend(fontsize=9, frameon=True, facecolor="white", edgecolor="none")
    fig.tight_layout()
    ax.set_position([0.15, 0.16, 0.82, 0.78])

    out_combined_png = os.path.join(output_dir, "multiobjective_pareto_comparison.png")
    out_combined_svg = os.path.join(output_dir, "multiobjective_pareto_comparison.svg")
    fig.savefig(out_combined_png, dpi=600)
    fig.savefig(out_combined_svg)
    plt.close(fig)
    print(f"  ✓  Saved combined Pareto chart   → {out_combined_png} & .svg")

    # ── 2. Individual Charts per Scenario ───────────────────────────────────
    for r in valid:
        scen = r["scenario"]
        st = styles.get(scen)
        if not st:
            continue

        fig, ax = plt.subplots(figsize=(4.14, 2.76), dpi=600)
        ax.yaxis.set_major_formatter(OrderOfMagnitudeFormatter(order=6, useMathText=False))
        
        # Plot raw candidate points if available
        if r.get("raw_points"):
            raw_pts = np.array(r["raw_points"])
            ax.scatter(
                raw_pts[:, 0], raw_pts[:, 1],
                color=st["raw_color"], marker=st["marker"], s=5, alpha=0.4,
                label="Raw Evaluated / Feasible Solutions", zorder=2
            )

        # Plot Pareto efficient front
        pts = np.array(r["pareto_points"])
        if scen == "A" and len(pts) > 0:
            thinned_pts = []
            last_ms = -999.0
            for pt in pts:
                if abs(pt[0] - last_ms) >= 1.5:
                    thinned_pts.append(pt)
                    last_ms = pt[0]
            if not thinned_pts or thinned_pts[-1][0] != pts[-1][0]:
                thinned_pts.append(pts[-1])
            pts_to_plot = np.array(thinned_pts)
        else:
            pts_to_plot = pts

        if scen == "A" and r.get("all_runs_pareto"):
            x_grid = np.linspace(210.0, 344.0, 200)
            c_low, c_high = [], []
            for x in x_grid:
                costs_at_x = []
                for run_pts in r["all_runs_pareto"]:
                    valid_c = [pt[1] for pt in run_pts if pt[0] <= x + 1e-5]
                    if valid_c:
                        costs_at_x.append(min(valid_c))
                if len(costs_at_x) >= 3:
                    c_low.append(min(costs_at_x))
                    c_high.append(max(costs_at_x))
                else:
                    c_low.append(np.nan)
                    c_high.append(np.nan)
            ax.fill_between(x_grid, c_low, c_high, color=st["color"], alpha=0.22, label="_nolegend_", zorder=1)

        ax.plot(
            pts_to_plot[:, 0], pts_to_plot[:, 1],
            color=st["color"], marker=st["marker"], linestyle=st["linestyle"],
            linewidth=1.2, markersize=2.3, label="Non-Dominated Pareto Front", zorder=3
        )

        # Removed title per user request
        ax.set_xlabel("Time (days)", fontsize=9, labelpad=6)
        ax.set_ylabel("Labor Cost ($)", fontsize=9, labelpad=6)
        ax.grid(True, linestyle=":", alpha=0.55)
        ax.legend(fontsize=9, frameon=True, facecolor="white", edgecolor="none")
        fig.tight_layout()
        ax.set_position([0.15, 0.16, 0.82, 0.78])

        out_ind_png = os.path.join(output_dir, f"{st['fname']}.png")
        out_ind_svg = os.path.join(output_dir, f"{st['fname']}.svg")
        fig.savefig(out_ind_png, dpi=600)
        fig.savefig(out_ind_svg)
        plt.close(fig)
        print(f"  ✓  Saved Scenario {scen} Pareto chart → {out_ind_png} & .svg")


def plot_totalcost_pareto_fronts(results, output_dir):
    """Generate overlaid comparison AND individual charts for Total Project Cost (Labor + Penalty - Bonus)."""
    import numpy as np
    import matplotlib.pyplot as plt

    plt.rcParams.update({
        "font.family": "serif",
        "font.serif": ["New Computer Modern", "Computer Modern", "CMU Serif", "Times New Roman", "DejaVu Serif"],
        "font.size": 9,
        "axes.labelsize": 9,
        "axes.titlesize": 9,
        "legend.fontsize": 9,
        "xtick.labelsize": 9,
        "ytick.labelsize": 9,
        "mathtext.fontset": "cm"
    })

    valid = [r for r in results if r is not None and r.get("pareto_points")]
    if not valid:
        print("  [warn] No Pareto points to plot for Total Cost.")
        return

    def _to_total_cost(pts):
        if not len(pts): return np.array([])
        pts_arr = np.array(pts)
        tc = []
        for pt in pts_arr:
            t, z = pt[0], pt[1]
            if t > 250.0:
                pen = 5000.0 * (t - 250.0)
                bon = 0.0
            else:
                pen = 0.0
                bon = 2000.0 * (250.0 - t)
            tc.append([t, z + pen - bon])
        return np.array(tc)

    styles = {
        "A": dict(color="#1f77b4", raw_color="#93c5fd", marker="o", linestyle="-",
                  label="Resource-Based Model", fname="multiobjective_totalcost_A_ga_cobb"),
        "B": dict(color="#d62728", raw_color="#fca5a5", marker="s", linestyle="--",
                  label="Mode-Based Model", fname="multiobjective_totalcost_B_milp_cobb"),
        "C": dict(color="#2ca02c", raw_color="#86efac", marker="^", linestyle="-.",
                  label="Time-Based Model", fname="multiobjective_totalcost_C_cpsat"),
    }

    # ── 1. Combined Overlaid Total Cost Chart ───────────────────────────────
    fig, ax = plt.subplots(figsize=(4.14, 2.76), dpi=600)
    ax.yaxis.set_major_formatter(OrderOfMagnitudeFormatter(order=6, useMathText=False))

    for r in valid:
        scen = r["scenario"]
        pts  = _to_total_cost(r["pareto_points"])
        st   = styles.get(scen, dict(color="black", marker="x", linestyle=":", label=f"Scenario {scen}"))
        
        if scen == "A" and len(pts) > 0:
            thinned_pts = []
            last_ms = -999.0
            for pt in pts:
                if abs(pt[0] - last_ms) >= 1.5:
                    thinned_pts.append(pt)
                    last_ms = pt[0]
            if not thinned_pts or thinned_pts[-1][0] != pts[-1][0]:
                thinned_pts.append(pts[-1])
            pts_to_plot = np.array(thinned_pts)
        else:
            pts_to_plot = pts

        if scen == "A" and r.get("all_runs_pareto"):
            x_grid = np.linspace(210.0, 344.0, 200)
            c_low, c_high = [], []
            for x in x_grid:
                costs_at_x = []
                for run_pts in r["all_runs_pareto"]:
                    run_tc = _to_total_cost(run_pts)
                    run_tc = run_tc[np.argsort(run_tc[:, 0])]
                    if run_tc[0, 0] <= x <= run_tc[-1, 0]:
                        val = np.interp(x, run_tc[:, 0], run_tc[:, 1])
                        costs_at_x.append(val)
                    elif x > run_tc[-1, 0]:
                        costs_at_x.append(run_tc[-1, 1] + 5000.0 * (x - max(250.0, run_tc[-1, 0])) if x > 250.0 else run_tc[-1, 1])
                    elif x < run_tc[0, 0]:
                        costs_at_x.append(run_tc[0, 1])
                if len(costs_at_x) >= 3:
                    c_low.append(min(costs_at_x))
                    c_high.append(max(costs_at_x))
                else:
                    c_low.append(np.nan)
                    c_high.append(np.nan)
            ax.fill_between(x_grid, c_low, c_high, color=st["color"], alpha=0.18, label="_nolegend_", zorder=1)

        ax.plot(
            pts_to_plot[:, 0], pts_to_plot[:, 1],
            color=st["color"], marker=st["marker"], linestyle=st["linestyle"],
            linewidth=1.2, markersize=2.3, label=st["label"], alpha=0.85, zorder=3
        )

    ax.set_xlabel("Time (days)", fontsize=9, labelpad=6)
    ax.set_ylabel("Total Project Cost ($)", fontsize=9, labelpad=6)
    ax.grid(True, linestyle=":", alpha=0.55)
    ax.legend(fontsize=9, frameon=True, facecolor="white", edgecolor="none")
    fig.tight_layout()
    ax.set_position([0.15, 0.16, 0.82, 0.78])

    out_combined_png = os.path.join(output_dir, "multiobjective_totalcost_comparison.png")
    out_combined_svg = os.path.join(output_dir, "multiobjective_totalcost_comparison.svg")
    fig.savefig(out_combined_png, dpi=600)
    fig.savefig(out_combined_svg)
    plt.close(fig)
    print(f"  ✓  Saved combined Total Cost chart → {out_combined_png} & .svg")

    # ── 2. Individual Total Cost Charts per Scenario ────────────────────────
    for r in valid:
        scen = r["scenario"]
        st = styles.get(scen)
        if not st:
            continue

        fig, ax = plt.subplots(figsize=(4.14, 2.76), dpi=600)
        ax.yaxis.set_major_formatter(OrderOfMagnitudeFormatter(order=6, useMathText=False))
        
        if r.get("raw_points"):
            raw_pts = _to_total_cost(r["raw_points"])
            ax.scatter(
                raw_pts[:, 0], raw_pts[:, 1],
                color=st["raw_color"], marker=st["marker"], s=5, alpha=0.4,
                label="Raw Evaluated / Feasible Solutions", zorder=2
            )

        pts = _to_total_cost(r["pareto_points"])
        if scen == "A" and len(pts) > 0:
            thinned_pts = []
            last_ms = -999.0
            for pt in pts:
                if abs(pt[0] - last_ms) >= 1.5:
                    thinned_pts.append(pt)
                    last_ms = pt[0]
            if not thinned_pts or thinned_pts[-1][0] != pts[-1][0]:
                thinned_pts.append(pts[-1])
            pts_to_plot = np.array(thinned_pts)
        else:
            pts_to_plot = pts

        if scen == "A" and r.get("all_runs_pareto"):
            x_grid = np.linspace(210.0, 344.0, 200)
            c_low, c_high = [], []
            for x in x_grid:
                costs_at_x = []
                for run_pts in r["all_runs_pareto"]:
                    run_tc = _to_total_cost(run_pts)
                    run_tc = run_tc[np.argsort(run_tc[:, 0])]
                    if run_tc[0, 0] <= x <= run_tc[-1, 0]:
                        val = np.interp(x, run_tc[:, 0], run_tc[:, 1])
                        costs_at_x.append(val)
                    elif x > run_tc[-1, 0]:
                        costs_at_x.append(run_tc[-1, 1] + 5000.0 * (x - max(250.0, run_tc[-1, 0])) if x > 250.0 else run_tc[-1, 1])
                    elif x < run_tc[0, 0]:
                        costs_at_x.append(run_tc[0, 1])
                if len(costs_at_x) >= 3:
                    c_low.append(min(costs_at_x))
                    c_high.append(max(costs_at_x))
                else:
                    c_low.append(np.nan)
                    c_high.append(np.nan)
            ax.fill_between(x_grid, c_low, c_high, color=st["color"], alpha=0.22, label="_nolegend_", zorder=1)

        ax.plot(
            pts_to_plot[:, 0], pts_to_plot[:, 1],
            color=st["color"], marker=st["marker"], linestyle=st["linestyle"],
            linewidth=1.2, markersize=2.3, label="Total Cost Trade-off Curve", zorder=3
        )

        ax.set_xlabel("Time (days)", fontsize=9, labelpad=6)
        ax.set_ylabel("Total Project Cost ($)", fontsize=9, labelpad=6)
        ax.grid(True, linestyle=":", alpha=0.55)
        ax.legend(fontsize=9, frameon=True, facecolor="white", edgecolor="none")
        fig.tight_layout()
        ax.set_position([0.15, 0.16, 0.82, 0.78])

        out_ind_png = os.path.join(output_dir, f"{st['fname']}.png")
        out_ind_svg = os.path.join(output_dir, f"{st['fname']}.svg")
        fig.savefig(out_ind_png, dpi=600)
        fig.savefig(out_ind_svg)
        plt.close(fig)
        print(f"  ✓  Saved Scenario {scen} Total Cost chart → {out_ind_png} & .svg")


# ════════════════════════════════════════════════════════════════════════════
# MAIN
# ════════════════════════════════════════════════════════════════════════════

def main():
    print()
    print("╔══════════════════════════════════════════════════════════════════════╗")
    print("║     MULTI-OBJECTIVE PROJECT CRASHING  —  3-SCENARIO BENCHMARK       ║")
    print("╠══════════════════════════════════════════════════════════════════════╣")
    print(f"║  ε-grid: {T_MIN_TARGET}–{T_MAX_TARGET}d (step={EPSILON_STEP}d)  |  "
          f"NSGA-II: pop={GA_POP_SIZE} gen={GA_MAX_GEN} (10 runs) ║")
    print("╚══════════════════════════════════════════════════════════════════════╝")

    t_global = time.perf_counter()

    if USE_CACHED_RESULTS and all(os.path.exists(os.path.join(OUTPUTS_DIR, f)) for f in ["A_ga_cobb_pareto.json", "B_milp_cobb_pareto.json", "C_cpsat_pareto.json"]):
        print("\n  [Cache] Loading existing Pareto JSON results from disk (skipping solver runs) …")
        with open(os.path.join(OUTPUTS_DIR, "A_ga_cobb_pareto.json"), "r", encoding="utf-8") as fh:
            results_A = json.load(fh)
        with open(os.path.join(OUTPUTS_DIR, "B_milp_cobb_pareto.json"), "r", encoding="utf-8") as fh:
            results_B = json.load(fh)
        with open(os.path.join(OUTPUTS_DIR, "C_cpsat_pareto.json"), "r", encoding="utf-8") as fh:
            results_C = json.load(fh)
        results = [results_A, results_B, results_C]
        plot_pareto_fronts(results, OUTPUTS_DIR)
        plot_totalcost_pareto_fronts(results, OUTPUTS_DIR)
        print_comparison(results)
        print(f"\n  Total benchmark time : {time.perf_counter() - t_global:.2f} s (from cache)")
        _hline("═")
        print()
        return

    results_B = None
    results_C = None
    results_A_list = []

    if PARALLEL_EXECUTION:
        import concurrent.futures
        print(f"\n  ⚡ [PARALLEL] Launching Scenarios B, C, and {len(GA_SEEDS)} independent runs of Scenario A simultaneously …\n")
        with concurrent.futures.ProcessPoolExecutor(max_workers=6) as executor:
            future_map = {}
            future_map[executor.submit(_run_worker_with_arg, run_scenario_B_moo, None)] = ("B", None)
            future_map[executor.submit(_run_worker_with_arg, run_scenario_C_moo, None)] = ("C", None)
            for s in GA_SEEDS:
                future_map[executor.submit(_run_worker_with_arg, run_scenario_A_moo, s)] = ("A", s)
                
            for future in concurrent.futures.as_completed(future_map):
                label, seed = future_map[future]
                res, out_text, err_text = future.result()
                print(out_text, end="")
                if err_text:
                    print(f"\n  ✗  Scenario {label} (seed={seed}) raised an exception:\n{err_text}")
                if label == "B":
                    results_B = res
                elif label == "C":
                    results_C = res
                elif label == "A" and res is not None:
                    results_A_list.append(res)
        print(f"  ⚡ All tasks finished in {time.perf_counter() - t_global:.1f}s wall-clock time.")
    else:
        results_B = run_scenario_B_moo()
        results_C = run_scenario_C_moo()
        for s in GA_SEEDS:
            res = run_scenario_A_moo(s)
            if res:
                results_A_list.append(res)

    # ── Aggregate Scenario A (10 runs) ────────────────────────────────────────
    if not results_A_list:
        print("  ✗  No valid Scenario A runs completed.")
        results_A = None
    else:
        solve_times = [r["solve_time_s"] for r in results_A_list]
        min_mss = [r["min_makespan_pt"][0] for r in results_A_list if r["min_makespan_pt"]]
        min_ms_costs = [r["min_makespan_pt"][1] for r in results_A_list if r["min_makespan_pt"]]
        min_costs = [r["min_cost_pt"][1] for r in results_A_list if r["min_cost_pt"]]
        min_cost_mss = [r["min_cost_pt"][0] for r in results_A_list if r["min_cost_pt"]]

        results_A = {
            "scenario": "A",
            "method": f"NSGA-II (Continuous Cobb-Douglas, {len(results_A_list)}-Run Avg)",
            "baseline_makespan": results_A_list[0]["baseline_makespan"],
            "pareto_points": results_A_list[0]["pareto_points"], # will update to median HV run below
            "raw_points": results_A_list[0]["raw_points"],
            "num_raw": int(np.mean([r["num_raw"] for r in results_A_list])),
            "num_points": int(np.mean([r["num_points"] for r in results_A_list])),
            "min_makespan_pt": [round(np.mean(min_mss), 1), round(np.mean(min_ms_costs), 1)],
            "min_cost_pt": [round(np.mean(min_cost_mss), 1), round(np.mean(min_costs), 1)],
            "solve_time_s": round(np.mean(solve_times), 1),
            "solve_time_sd": round(np.std(solve_times), 1),
            "min_ms_str": f"{np.mean(min_mss):.1f}±{np.std(min_mss):.1f}d (${np.mean(min_ms_costs)/1e3:.1f}k)",
            "min_cost_str": f"{np.mean(min_cost_mss):.1f}d (${np.mean(min_costs)/1e3:.1f}±{np.std(min_costs)/1e3:.1f}k)",
            "time_str": f"{np.mean(solve_times):.1f} ± {np.std(solve_times):.1f}",
            "all_runs_pareto": [r["pareto_points"] for r in results_A_list],
            "all_runs_data": results_A_list,
        }

    for r in [results_B, results_C]:
        if r is not None:
            r["min_ms_str"] = f"{r['min_makespan_pt'][0]:.1f}d (${r['min_makespan_pt'][1]/1e3:.1f}k)" if r['min_makespan_pt'] else "N/A"
            r["min_cost_str"] = f"{r['min_cost_pt'][0]:.1f}d (${r['min_cost_pt'][1]/1e3:.1f}k)" if r['min_cost_pt'] else "N/A"
            r["time_str"] = f"{r['solve_time_s']:.1f}"

    # ── Compute Hypervolume across all runs ───────────────────────────────────
    all_pts_for_bounds = []
    for r in results_A_list + [results_B, results_C]:
        if r is not None:
            all_pts_for_bounds.extend(r["pareto_points"])
            
    if all_pts_for_bounds:
        t_min = min(pt[0] for pt in all_pts_for_bounds)
        t_max = max(pt[0] for pt in all_pts_for_bounds)
        c_min = min(pt[1] for pt in all_pts_for_bounds)
        c_max = max(pt[1] for pt in all_pts_for_bounds)
        print(f"\n  [HV Normalization Bounds] Time: {t_min:.1f}–{t_max:.1f}d  |  Cost: ${c_min:,.0f}–${c_max:,.0f}")

        for r in results_A_list + [results_B, results_C]:
            if r is not None:
                area, ratio = compute_hypervolume(r["pareto_points"], t_min, t_max, c_min, c_max)
                r["hv_area"] = area
                r["hv_ratio"] = ratio
                if r in [results_B, results_C]:
                    r["hv_str"] = f"{area:.4f} ({ratio:.1f}%)"

        if results_A is not None:
            hv_areas = [r["hv_area"] for r in results_A_list]
            hv_ratios = [r["hv_ratio"] for r in results_A_list]
            hv_mean = np.mean(hv_ratios)
            results_A["hv_area"] = round(np.mean(hv_areas), 4)
            results_A["hv_ratio"] = round(hv_mean, 1)
            results_A["hv_str"] = f"{np.mean(hv_areas):.4f}±{np.std(hv_areas):.4f} ({hv_mean:.1f}%±{np.std(hv_ratios):.1f}%)"
            
            # Select median HV run as representative Pareto front for Scenario A
            best_ga = min(results_A_list, key=lambda r: abs(r["hv_ratio"] - hv_mean))
            results_A["pareto_points"] = best_ga["pareto_points"]
            results_A["raw_points"] = best_ga["raw_points"]

    # ── Combined NDS Count across representative fronts ───────────────────────
    results = [results_A, results_B, results_C]
    valid_results = [r for r in results if r is not None]
    
    if valid_results:
        master_pool = []
        for r in valid_results:
            master_pool.extend(r["pareto_points"])
        master_front = _filter_non_dominated(master_pool)
        
        for r in valid_results:
            if r["scenario"] == "A":
                # Average NDS count across all 10 GA runs
                counts = [sum(1 for pt in run_r["pareto_points"] if any(abs(pt[0]-mf[0])<1e-4 and abs(pt[1]-mf[1])<1e-2 for mf in master_front)) for run_r in results_A_list]
                c_mean = np.mean(counts)
                r_mean = (c_mean / max(1, len(master_front))) * 100.0
                r["nds_str"] = f"{c_mean:.1f}±{np.std(counts):.1f} ({r_mean:.1f}%)"
            else:
                count = sum(1 for pt in r["pareto_points"] if any(abs(pt[0]-mf[0])<1e-4 and abs(pt[1]-mf[1])<1e-2 for mf in master_front))
                ratio = (count / max(1, len(master_front))) * 100.0
                r["nds_str"] = f"{count} ({ratio:.1f}%)"

    # ── Persist individual & combined Pareto JSON data ────────────────────────
    for r in valid_results:
        scen = r["scenario"]
        fname_map = {"A": "A_ga_cobb_pareto.json", "B": "B_milp_cobb_pareto.json", "C": "C_cpsat_pareto.json"}
        out_scen = os.path.join(OUTPUTS_DIR, fname_map.get(scen, f"{scen}_pareto.json"))
        save_dict = {k: v for k, v in r.items() if k != "all_runs_data"}
        with open(out_scen, "w", encoding="utf-8") as fh:
            json.dump(save_dict, fh, indent=2)
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
                    "GA_SEEDS": GA_SEEDS,
                    "MILP_TIME_LIMIT": MILP_TIME_LIMIT,
                    "CPSAT_TIME_LIMIT": CPSAT_TIME_LIMIT,
                    "ALPHA": ALPHA, "BETA": BETA,
                    "CURRENT_DAY": CURRENT_DAY,
                },
                "scenarios": [{k: v for k, v in r.items() if k != "all_runs_data"} for r in valid_results],
            },
            fh, indent=2,
        )
    print(f"  ✓  Saved combined Pareto data → {out_json}")

    # ── Pareto charts (combined & individual) ────────────────────────────────
    plot_pareto_fronts(results, OUTPUTS_DIR)
    plot_totalcost_pareto_fronts(results, OUTPUTS_DIR)

    # ── Console comparison table ──────────────────────────────────────────────
    print_comparison(results)

    total_elapsed = time.perf_counter() - t_global
    print()
    print(f"  Total benchmark time : {total_elapsed:.1f} s")
    _hline("═")
    print()


if __name__ == "__main__":
    main()
