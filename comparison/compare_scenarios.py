"""
compare_scenarios.py
====================
Run and compare three project-crashing scenarios:

  A  — Scenario 2 : Original CSV data  +  GA (pymoo, Cobb-Douglas)
  B  — Scenario 2 : Discretized CSV data  +  MILP (OR-Tools CP-SAT integer)
  C  — Scenario 3 : Preprocessed JSON data  +  CP-SAT (OR-Tools, linear crash cost)

Usage
-----
    python compare_scenarios.py

All outputs are written to ./outputs/comparison/single/ next to this script.

Configuration
-------------
Edit the SETTINGS block below to change T_MAX, CURRENT_DAY, bonus/penalty,
GA population/generations, and solver time limits.
"""

import os
import sys
if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
import time
import json
import warnings
warnings.filterwarnings("ignore")

# ── path setup ──────────────────────────────────────────────────────────────
SCRIPT_DIR  = os.path.dirname(os.path.abspath(__file__))
ROOT_DIR    = os.path.dirname(SCRIPT_DIR)                        # PROJECT-CRASHING/

COBB_DIR    = os.path.join(ROOT_DIR, "implementasi-cobb")        # cobb_model.py, solver_milp.py, CSVs
BASE_DIR    = os.path.join(ROOT_DIR, "implementasi-base")        # solver_base.py
HYBRID_DIR  = os.path.join(ROOT_DIR, "implementasi-hybrid")      # preprocessing.py
HYBRID_DATA = os.path.join(HYBRID_DIR, "data")                  # activity_data.json etc.
OUTPUTS_DIR = os.path.join(ROOT_DIR, "outputs", "comparison", "single")
os.makedirs(OUTPUTS_DIR, exist_ok=True)

sys.path.insert(0, COBB_DIR)
sys.path.insert(0, BASE_DIR)
sys.path.insert(0, HYBRID_DIR)

# ════════════════════════════════════════════════════════════════════════════
# SETTINGS  ← edit here
# ════════════════════════════════════════════════════════════════════════════
PARALLEL_EXECUTION = False # Run Scenarios sequentially (A runs 10 seeds in parallel)
USE_CACHED_RESULTS = True  # Load deterministic B and C from cache to save time

T_MAX          = 250      # contractual deadline (baseline=344, physical floor≈210)
CURRENT_DAY    = 20       # project review day T_0 (tasks finishing ≤20 are locked)
C_LATE         = 5000.0   # USD penalty per late day
C_EARLY        = 2000.0   # USD bonus per early day

# Scenario A — GA
GA_POP_SIZE    = 1000      # population size
GA_MAX_GEN     = 500      # max generations
GA_TOL         = 0.0005   # convergence tolerance (relative change in objective)
GA_PERIOD      = 20       # number of consecutive generations under tol before stopping
GA_SEEDS       = [42, 43, 44, 45, 46, 47, 48, 49, 50, 51]  # 10 independent runs
GA_SEED        = 42

# Scenario B — MILP (CP-SAT discretized)
MILP_TIME_LIMIT  = 300.0  # seconds

# Scenario C — CP-SAT linear
CPSAT_TIME_LIMIT = 300.0  # seconds

# Cobb-Douglas model parameters (used in A & B)
ALPHA         = 0.7
BETA          = 0.7
X_MIN         = 1.0
X_MAX         = 2.0
TAU_MIN       = 0.0
TAU_MAX       = 4.0
D_MIN_RATIO   = 0.5
OVERTIME_MULT = 1.5
HOURS_PER_DAY = 8

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

    Mirrors the logic of ``ResourceBasedScheduling._forward_pass_raw`` so that
    Scenario C reports the same baseline makespan as Scenarios A & B (344 days),
    instead of the resource-constrained CP-SAT baseline (345 days).

    Parameters
    ----------
    act   : activity_data dict  (keys = activity id strings)
    preds : predecessors dict produced by build_predecessors()

    Returns
    -------
    float – CPM makespan (max finish time across all activities)
    """
    durations = {a: int(act[a].get("activity_normal_time", 0)) for a in act}
    finish    = {a: 0.0 for a in act}

    # Topological relaxation: iterate until stable
    for _ in range(len(act) + 1):
        changed = False
        for a in act:
            earliest_start = 0.0
            for p in preds.get(a, []):
                earliest_start = max(earliest_start, finish[p])
            new_finish = earliest_start + durations[a]
            if new_finish > finish[a] + 1e-9:
                finish[a] = new_finish
                changed = True
        if not changed:
            break

    return float(max(finish.values())) if finish else 0.0

# ════════════════════════════════════════════════════════════════════════════
# SCENARIO A  —  Original CSV + GA (Cobb-Douglas, pymoo)
# ════════════════════════════════════════════════════════════════════════════

def _run_scenario_A_single_seed(seed):
    import time, os
    os.environ["PYMOO_THREADS"] = "1"
    from cobb_model import load_data, data_path, ResourceBasedScheduling, solve
    tasks, precedence, resources, N, K_i = load_data(
        path_tasks=data_path("data_tasks.csv"),
        path_precedence=data_path("data_precedence.csv"),
        path_assignments=data_path("data_assignments.csv"),
    )
    problem = ResourceBasedScheduling(
        tasks=tasks, precedence=precedence, resources=resources, N=N, K_i=K_i,
        alpha=ALPHA, beta=BETA, x_min=X_MIN, tau_min=TAU_MIN, tau_max=TAU_MAX,
        D_min_ratio=D_MIN_RATIO, T_max=T_MAX, current_day=CURRENT_DAY,
        overtime_mult=OVERTIME_MULT, hours_per_day=HOURS_PER_DAY,
        mode="bonus_penalty", c_late=C_LATE, c_early=C_EARLY,
    )
    t0 = time.perf_counter()
    sol = solve(
        problem,
        pop_size=GA_POP_SIZE,
        seed=seed,
        verbose=False,
        max_gen=GA_MAX_GEN,
        tol=GA_TOL,
        period=GA_PERIOD,
    )
    elapsed = time.perf_counter() - t0
    if sol is None:
        return None
    sol.pop("pymoo_result", None)
    sol.pop("callback", None)
    sol["solve_time_s"] = elapsed
    sol["seed"] = seed
    return sol


def run_scenario_A():
    _section(f"SCENARIO A  |  Original CSV  +  GA  (Cobb-Douglas, {len(GA_SEEDS)}-Run Avg)")

    import concurrent.futures
    import numpy as np
    from cobb_model import (
        load_data, data_path, ResourceBasedScheduling,
        save_solution_json, generate_gantt_comparison_plot,
        generate_interactive_gantt_html,
    )

    tasks, precedence, resources, N, K_i = load_data(
        path_tasks=data_path("data_tasks.csv"),
        path_precedence=data_path("data_precedence.csv"),
        path_assignments=data_path("data_assignments.csv"),
    )
    problem = ResourceBasedScheduling(
        tasks=tasks, precedence=precedence, resources=resources, N=N, K_i=K_i,
        alpha=ALPHA, beta=BETA, x_min=X_MIN, tau_min=TAU_MIN, tau_max=TAU_MAX,
        D_min_ratio=D_MIN_RATIO, T_max=T_MAX, current_day=CURRENT_DAY,
        overtime_mult=OVERTIME_MULT, hours_per_day=HOURS_PER_DAY,
        mode="bonus_penalty", c_late=C_LATE, c_early=C_EARLY,
    )
    baseline_makespan = float(np.max(problem.f_baseline))
    print(f"  Baseline makespan : {baseline_makespan:.1f} days")
    print(f"  Active tasks      : {N - len(problem.completed_tasks)}")
    print(f"  GA params         : pop={GA_POP_SIZE}  max_gen={GA_MAX_GEN}  "
          f"tol={GA_TOL}  period={GA_PERIOD}  seeds={GA_SEEDS}")
    print(f"  ⚡ Running {len(GA_SEEDS)} independent GA runs in parallel across CPU cores …\n")

    runs = []
    t0_all = time.perf_counter()
    with concurrent.futures.ProcessPoolExecutor(max_workers=min(10, os.cpu_count() or 4)) as executor:
        future_to_seed = {executor.submit(_run_scenario_A_single_seed, s): s for s in GA_SEEDS}
        for future in concurrent.futures.as_completed(future_to_seed):
            s = future_to_seed[future]
            try:
                sol = future.result()
                if sol is not None:
                    runs.append(sol)
                    print(f"  ✓  [Seed {s:2d}] makespan={sol['makespan']:.2f}d  "
                          f"cost=${sol['total_cost']:,.2f}  time={sol['solve_time_s']:.1f}s")
                else:
                    print(f"  ✗  [Seed {s:2d}] no solution found")
            except Exception as ex:
                print(f"  ✗  [Seed {s:2d}] raised exception: {ex}")

    if not runs:
        print("  ✗  All GA runs failed.")
        return None

    runs.sort(key=lambda x: x["seed"])

    makespans    = [r["makespan"] for r in runs]
    labor_costs  = [r["labor_cost"] for r in runs]
    penalties    = [r["penalty"] for r in runs]
    bonuses      = [r["bonus"] for r in runs]
    total_costs  = [r["total_cost"] for r in runs]
    solve_times  = [r["solve_time_s"] for r in runs]
    rescue_margins = [baseline_makespan - m for m in makespans]
    target_margins = [T_MAX - m for m in makespans]

    mean_makespan   = float(np.mean(makespans))
    std_makespan    = float(np.std(makespans))
    mean_labor_cost = float(np.mean(labor_costs))
    std_labor_cost  = float(np.std(labor_costs))
    mean_penalty    = float(np.mean(penalties))
    std_penalty     = float(np.std(penalties))
    mean_bonus      = float(np.mean(bonuses))
    std_bonus       = float(np.std(bonuses))
    mean_total_cost = float(np.mean(total_costs))
    std_total_cost  = float(np.std(total_costs))
    mean_solve_time = float(np.mean(solve_times))
    std_solve_time  = float(np.std(solve_times))
    mean_rescue_margin = float(np.mean(rescue_margins))
    std_rescue_margin  = float(np.std(rescue_margins))
    mean_target_margin = float(np.mean(target_margins))
    std_target_margin  = float(np.std(target_margins))

    print("\n  ── Scenario A (10-Run Average Summary) ──")
    print(f"  Makespan        : {mean_makespan:.2f} ± {std_makespan:.2f} d")
    print(f"  Rescue margin   : {mean_rescue_margin:.2f} ± {std_rescue_margin:.2f} d")
    print(f"  Target margin   : {mean_target_margin:.2f} ± {std_target_margin:.2f} d")
    print(f"  Labor cost      : ${mean_labor_cost:,.2f} ± ${std_labor_cost:,.2f}")
    print(f"  Penalty         : ${mean_penalty:,.2f} ± ${std_penalty:,.2f}")
    print(f"  Bonus           : ${mean_bonus:,.2f} ± ${std_bonus:,.2f}")
    print(f"  Total cost      : ${mean_total_cost:,.2f} ± ${std_total_cost:,.2f}")
    print(f"  Solve time (avg): {mean_solve_time:.1f} ± {std_solve_time:.1f} s")

    best_idx = int(np.argmin([abs(tc - mean_total_cost) for tc in total_costs]))
    rep_run = runs[best_idx]
    print(f"  Representative schedule for Gantt: Seed {rep_run['seed']} (cost=${rep_run['total_cost']:,.2f}, makespan={rep_run['makespan']:.2f}d)")

    out_json  = os.path.join(OUTPUTS_DIR, "A_ga_cobb.json")
    out_gantt = os.path.join(OUTPUTS_DIR, "A_ga_cobb_gantt.png")
    out_html  = os.path.join(OUTPUTS_DIR, "A_ga_cobb_gantt.html")

    save_solution_json(
        tasks, resources, precedence, problem,
        None,
        rep_run["x_ik"], rep_run["tau_ik"],
        rep_run["D_ik"], rep_run["D_i"],
        rep_run["s"], rep_run["f"],
        CURRENT_DAY, T_MAX, mean_makespan, mean_labor_cost, mean_total_cost, out_json,
    )
    try:
        generate_gantt_comparison_plot(
            tasks, problem.s_baseline, problem.f_baseline,
            rep_run["s"], rep_run["f"], CURRENT_DAY, out_gantt,
        )
    except Exception as ex:
        print(f"  [warn] Gantt PNG: {ex}")
    try:
        generate_interactive_gantt_html(
            tasks, resources,
            problem.s_baseline, problem.f_baseline,
            rep_run["s"], rep_run["f"],
            rep_run["x_ik"], rep_run["tau_ik"],
            rep_run["D_ik"], rep_run["D_i"],
            CURRENT_DAY, T_MAX, out_html,
        )
    except Exception as ex:
        print(f"  [warn] Gantt HTML: {ex}")

    return {
        "scenario": "A",
        "method": f"GA (Cobb-Douglas, {len(runs)}-Run Avg)",
        "baseline_makespan": baseline_makespan,
        "makespan": mean_makespan,
        "makespan_std": std_makespan,
        "makespan_reduction": round(mean_rescue_margin, 2),
        "makespan_reduction_std": std_rescue_margin,
        "rescue_margin": mean_rescue_margin,
        "rescue_margin_std": std_rescue_margin,
        "target_margin": mean_target_margin,
        "target_margin_std": std_target_margin,
        "labor_cost": mean_labor_cost,
        "labor_cost_std": std_labor_cost,
        "penalty": mean_penalty,
        "penalty_std": std_penalty,
        "bonus": mean_bonus,
        "bonus_std": std_bonus,
        "total_cost": mean_total_cost,
        "total_cost_std": std_total_cost,
        "solve_time_s": round(mean_solve_time, 2),
        "solve_time_std": std_solve_time,
        "all_runs": [
            {
                "seed": r["seed"],
                "makespan": r["makespan"],
                "labor_cost": r["labor_cost"],
                "penalty": r["penalty"],
                "bonus": r["bonus"],
                "total_cost": r["total_cost"],
                "solve_time_s": r["solve_time_s"]
            } for r in runs
        ],
        "output_json": out_json,
        "output_gantt_png": out_gantt,
        "output_gantt_html": out_html,
    }


# ════════════════════════════════════════════════════════════════════════════
# SCENARIO B  —  Discretized CSV + MILP (CP-SAT integer)
# ════════════════════════════════════════════════════════════════════════════

def run_scenario_B():
    _section("SCENARIO B  |  Discretized CSV  +  MILP  (CP-SAT integer)")

    summary_path = os.path.join(OUTPUTS_DIR, "comparison_summary.json")
    if USE_CACHED_RESULTS and os.path.exists(summary_path):
        try:
            with open(summary_path, "r") as fh:
                data = json.load(fh)
                for r in data.get("results", []):
                    if r.get("scenario") == "B":
                        print("  ✓ [Cache] Loaded deterministic Scenario B results from comparison_summary.json")
                        return r
        except Exception as ex:
            print(f"  [warn] Cache read failed: {ex}")

    from cobb_model import load_data, data_path, ResourceBasedScheduling
    from solver_milp import solve_milp_cobb_douglas
    import numpy as np, shutil

    tasks, precedence, resources, N, K_i = load_data(
        path_tasks=data_path("data_tasks.csv"),
        path_precedence=data_path("data_precedence.csv"),
        path_assignments=data_path("data_assignments.csv"),
    )

    # Baseline only for display
    _prob = ResourceBasedScheduling(
        tasks=tasks, precedence=precedence, resources=resources, N=N, K_i=K_i,
        alpha=ALPHA, beta=BETA, x_min=X_MIN, tau_min=TAU_MIN, tau_max=TAU_MAX,
        D_min_ratio=D_MIN_RATIO, T_max=T_MAX, current_day=CURRENT_DAY,
        overtime_mult=OVERTIME_MULT, hours_per_day=HOURS_PER_DAY,
        mode="bonus_penalty", c_late=C_LATE, c_early=C_EARLY,
    )
    baseline_makespan = float(np.max(_prob.f_baseline))
    print(f"  Baseline makespan : {baseline_makespan:.1f} days")
    print(f"  MILP time limit   : {MILP_TIME_LIMIT} s")
    print("  Solving …")

    t0 = time.perf_counter()
    result = solve_milp_cobb_douglas(
        tasks, precedence, resources, N, K_i,
        alpha=ALPHA, beta=BETA, x_min=X_MIN, x_max=X_MAX,
        tau_min=TAU_MIN, tau_max=TAU_MAX, D_min_ratio=D_MIN_RATIO,
        T_max=T_MAX, current_day=CURRENT_DAY,
        overtime_mult=OVERTIME_MULT, hours_per_day=HOURS_PER_DAY,
        mode="bonus_penalty",
        c_late=C_LATE, c_early=C_EARLY,
        time_limit=MILP_TIME_LIMIT,
        time_scale=100, dx=0.1, dtau=0.1,
    )
    elapsed = time.perf_counter() - t0

    if result is None:
        print("  ✗  MILP found no feasible solution.")
        return None

    makespan   = result["makespan"]
    labor_cost = result["labor_cost"]
    total_cost = result["total_cost"]
    penalty    = C_LATE  * max(0, makespan - T_MAX)
    bonus      = C_EARLY * max(0, T_MAX - makespan)

    out_json  = os.path.join(OUTPUTS_DIR, "B_milp_cobb.json")
    out_gantt = os.path.join(OUTPUTS_DIR, "B_milp_cobb_gantt.png")
    out_html  = os.path.join(OUTPUTS_DIR, "B_milp_cobb_gantt.html")

    # solver_milp writes its own JSON to COBB_DIR/../outputs/mode-based — copy to our outputs dir
    default_path = os.path.join(COBB_DIR, "../outputs/mode-based/milp_cobb_bonus_penalty.json")
    try:
        if os.path.exists(default_path):
            shutil.copy(default_path, out_json)
        else:
            with open(out_json, "w") as fh:
                json.dump(result, fh, indent=2, default=str)
    except Exception as ex:
        print(f"  [warn] JSON copy: {ex}")

    # Generate Gantt for B using cobb_model's plotting functions
    try:
        from cobb_model import generate_gantt_comparison_plot
        generate_gantt_comparison_plot(
            tasks, _prob.s_baseline, _prob.f_baseline,
            result["s"], result["f"], CURRENT_DAY, out_gantt,
        )
    except Exception as ex:
        print(f"  [warn] Gantt PNG B: {ex}")

    try:
        from cobb_model import generate_interactive_gantt_html
        generate_interactive_gantt_html(
            tasks, resources,
            _prob.s_baseline, _prob.f_baseline,
            result["s"], result["f"],
            result["x_ik"], result["tau_ik"],
            result["D_ik"], result["D_i"],
            CURRENT_DAY, T_MAX, out_html,
        )
    except Exception as ex:
        print(f"  [warn] Gantt HTML B: {ex}")

    print(f"  ✓  Makespan        : {makespan:.2f} days  (saved {baseline_makespan - makespan:.1f} d)")
    print(f"     Labor cost      : ${labor_cost:,.2f}")
    print(f"     Penalty         : ${penalty:,.2f}  |  Bonus : ${bonus:,.2f}")
    print(f"     Total cost      : ${total_cost:,.2f}")
    print(f"     Solve time      : {elapsed:.1f} s")

    return {
        "scenario": "B",
        "method": "MILP / CP-SAT (discretized Cobb-Douglas)",
        "baseline_makespan": baseline_makespan,
        "makespan": float(makespan),
        "makespan_reduction": round(baseline_makespan - makespan, 2),
        "labor_cost": labor_cost,
        "penalty": penalty,
        "bonus": bonus,
        "total_cost": total_cost,
        "solve_time_s": round(elapsed, 2),
        "output_json": out_json,
        "output_gantt_png": out_gantt,
        "output_gantt_html": out_html,
    }


# ════════════════════════════════════════════════════════════════════════════
# SCENARIO C  —  Preprocessed JSON + CP-SAT (linear crash cost)
# ════════════════════════════════════════════════════════════════════════════

def run_scenario_C():
    _section("SCENARIO C  |  Preprocessed JSON  +  CP-SAT  (linear crash cost)")

    summary_path = os.path.join(OUTPUTS_DIR, "comparison_summary.json")
    if USE_CACHED_RESULTS and os.path.exists(summary_path):
        try:
            with open(summary_path, "r") as fh:
                data = json.load(fh)
                for r in data.get("results", []):
                    if r.get("scenario") == "C":
                        print("  ✓ [Cache] Loaded deterministic Scenario C results from comparison_summary.json")
                        return r
        except Exception as ex:
            print(f"  [warn] Cache read failed: {ex}")

    from solver_base import (
        read_json, build_predecessors,
        infer_activity_states_without_state_file,
        SolveConfig, build_model_and_solve,
        build_reference_no_crash_schedule,
        generate_gantt_comparison_plot,
        generate_interactive_gantt_html,
        write_json, write_schedule_csv,
    )
    from preprocessing import preprocess

    # ── Fix 1: dynamically preprocess from the same CSVs using live parameters ──
    # This ensures Scenario C's linear crash-cost slopes are always computed from
    # the identical x_max, tau_max, alpha, beta, overtime_mult as Scenarios A & B,
    # rather than whatever was frozen in the static JSON files on disk.
    print("  Running preprocessing with live model parameters …")
    act, rr, rc = preprocess(
        alpha=ALPHA, beta=BETA,
        x_max=X_MAX, tau_max=TAU_MAX,
        overtime_mult=OVERTIME_MULT, hours_per_day=HOURS_PER_DAY,
    )

    preds, cycle_logs = build_predecessors(act, [], True)
    for log in cycle_logs:
        print(f"  [preprocess] {log}")

    states, state_logs = infer_activity_states_without_state_file(
        act, rr, rc, preds, CURRENT_DAY, CPSAT_TIME_LIMIT, 1,
    )
    for log in state_logs:
        print(f"  [state] {log[:100]}")

    # ── Fix 2: use CPM-only baseline makespan (precedence-only, same as A & B) ──
    # build_reference_no_crash_schedule applies resource constraints too, giving
    # 345 days vs the CPM-only 344 days from Scenarios A & B.  We compute the
    # pure CPM baseline directly from activity_normal_time to align the table.
    cpm_makespan = _compute_cpm_baseline(act, preds)

    baseline_sched    = build_reference_no_crash_schedule(act, rr, rc, preds, CURRENT_DAY, CPSAT_TIME_LIMIT, 1)
    baseline_makespan = cpm_makespan   # ← use CPM value for consistent display
    print(f"  Baseline makespan : {baseline_makespan:.1f} days  (CPM, same method as A & B)")
    print(f"  CP-SAT time limit : {CPSAT_TIME_LIMIT} s")
    print("  Solving …")

    cfg = SolveConfig(
        target_end_date=T_MAX, current_day=CURRENT_DAY,
        time_limit=CPSAT_TIME_LIMIT, num_workers=1,
        auto_fix_paint_trim_cycle=True, remove_edges=[],
        c_late=C_LATE, c_early=C_EARLY,
    )

    t0 = time.perf_counter()
    result = build_model_and_solve(act, rr, rc, preds, states, cfg, mode="bonus_penalty")
    elapsed = time.perf_counter() - t0

    status = result.get("status", "UNKNOWN")
    if status not in ("OPTIMAL", "FEASIBLE"):
        print(f"  ✗  CP-SAT returned: {status}")
        return None

    makespan   = result["makespan"]

    # ── Cost calculation (matches run_bonus_penalty.py 77-line version) ──
    # total_crash_cost = incremental crashing cost (additional above normal)
    # total_normal_cost = Sum W_i,k * r_k  (baseline labor cost for all activities)
    # total_comparable_cost = total_normal_cost + total_crash_cost
    # total_cost = total_comparable_cost + penalty - bonus
    crash_cost        = result["total_crash_cost"]
    total_normal_cost = sum(
        float(a.get("activity_base_cost", 0.0)) for a in act.values()
    )
    total_comparable_cost = total_normal_cost + crash_cost
    penalty    = C_LATE  * max(0, makespan - T_MAX)
    bonus      = C_EARLY * max(0, T_MAX - makespan)
    total_cost = total_comparable_cost + penalty - bonus

    # Enrich result with computed cost fields before saving
    result["total_normal_cost"]      = total_normal_cost
    result["total_comparable_cost"]  = total_comparable_cost
    result["penalty"]                = penalty
    result["bonus"]                  = bonus
    result["total_cost"]             = total_cost

    out_json  = os.path.join(OUTPUTS_DIR, "C_cpsat.json")
    out_gantt = os.path.join(OUTPUTS_DIR, "C_cpsat_gantt.png")
    out_html  = os.path.join(OUTPUTS_DIR, "C_cpsat_gantt.html")

    write_json(out_json, result)
    try:
        generate_gantt_comparison_plot(
            baseline_schedule=baseline_sched,
            optimized_schedule=result.get("schedule", []),
            current_day=CURRENT_DAY,
            output_path=out_gantt,
        )
        generate_interactive_gantt_html(
            baseline_schedule=baseline_sched,
            optimized_schedule=result.get("schedule", []),
            current_day=CURRENT_DAY,
            target_end_date=T_MAX,
            output_path=out_html,
            activity_data=act,
        )
    except Exception as ex:
        print(f"  [warn] Gantt plots: {ex}")

    print(f"  ✓  Status          : {status}")
    print(f"     Makespan        : {makespan} days  (saved {baseline_makespan - makespan} d)")
    print(f"     Crash cost      : ${crash_cost:,.2f}")
    print(f"     Normal cost     : ${total_normal_cost:,.2f}  (Sum W_i,k * r_k)")
    print(f"     Comparable cost : ${total_comparable_cost:,.2f}")
    print(f"     Penalty         : ${penalty:,.2f}  |  Bonus : ${bonus:,.2f}")
    print(f"     Total cost      : ${total_cost:,.2f}")
    print(f"     Solve time      : {elapsed:.1f} s")

    return {
        "scenario": "C",
        "method": "CP-SAT (linear crash cost)",
        "baseline_makespan": float(baseline_makespan),
        "makespan": float(makespan),
        "makespan_reduction": float(baseline_makespan - makespan),
        # labor_cost stores total_comparable_cost so the comparison table is apples-to-apples
        "labor_cost": total_comparable_cost,
        "crash_cost": crash_cost,
        "normal_cost": total_normal_cost,
        "penalty": penalty,
        "bonus": bonus,
        "total_cost": total_cost,
        "solve_time_s": round(elapsed, 2),
        "output_json": out_json,
        "output_gantt_png": out_gantt,
        "output_gantt_html": out_html,
    }


# ════════════════════════════════════════════════════════════════════════════
# COMPARISON TABLE  +  BAR CHART
# ════════════════════════════════════════════════════════════════════════════

def print_comparison(results):
    _section("COMPARISON SUMMARY")

    valid = [r for r in results if r is not None]
    if not valid:
        print("  No results to compare.")
        return

    col_w = 32
    val_w = 28

    header = f"  {'Metric':<{col_w}}"
    for r in valid:
        lbl = f"{r['scenario']} – {r['method']}"
        header += f"  {lbl[:val_w]:<{val_w}}"
    print(header)
    _hline()

    metrics = [
        ("Baseline makespan (days)",        "baseline_makespan",     "{:.1f}"),
        ("Optimized makespan (days)",        "makespan",              "{:.2f}"),
        ("Makespan reduction (days)",        "makespan_reduction",    "{:.2f}"),
        ("On-time vs T_MAX",                 "__ontime__",            None),
        ("Labor / Comparable cost (USD)",    "labor_cost",            "${:,.2f}"),
        ("Late penalty (USD)",               "penalty",               "${:,.2f}"),
        ("Early bonus (USD)",                "bonus",                 "${:,.2f}"),
        ("Total cost (USD)",                 "total_cost",            "${:,.2f}"),
        ("Solve time (s)",                   "solve_time_s",          "{:.2f}"),
    ]

    for label, key, fmt in metrics:
        line = f"  {label:<{col_w}}"
        for r in valid:
            if key == "__ontime__":
                diff = r["makespan"] - T_MAX
                tag  = ("✓ ON TIME" if diff <= 0 else "✗ LATE") + f"  ({diff:+.1f}d)"
                line += f"  {tag:<{val_w}}"
            else:
                val = r.get(key, "N/A")
                std_val = r.get(f"{key}_std")
                if std_val is not None and isinstance(std_val, (int, float)) and std_val > 0.0001:
                    val_str = fmt.format(val) if fmt and isinstance(val, (int, float)) else str(val)
                    if fmt and fmt.startswith("$"):
                        std_str = f"${std_val:,.2f}"
                    elif fmt and "f" in fmt:
                        std_str = f"{std_val:.2f}"
                    else:
                        std_str = f"{std_val:.2f}"
                    cell = f"{val_str} ± {std_str}"
                else:
                    cell = fmt.format(val) if fmt and isinstance(val, (int, float)) else str(val)
                line += f"  {cell:<{val_w}}"
        print(line)

    _hline()

    # Extra breakdown row for Scenario C crash vs normal split
    c_results = [r for r in valid if r["scenario"] == "C"]
    if c_results:
        print()
        print("  Scenario C cost breakdown:")
        for r in c_results:
            print(f"    Crash cost      : ${r.get('crash_cost', 0):,.2f}")
            print(f"    Normal cost     : ${r.get('normal_cost', 0):,.2f}  (Sum W_i,k * r_k)")
            print(f"    Comparable cost : ${r['labor_cost']:,.2f}  (crash + normal)")

    # save JSON summary
    out_compare = os.path.join(OUTPUTS_DIR, "comparison_summary.json")
    with open(out_compare, "w") as fh:
        json.dump({"settings": {"T_MAX": T_MAX, "CURRENT_DAY": CURRENT_DAY,
                                "C_LATE": C_LATE, "C_EARLY": C_EARLY},
                   "results": valid}, fh, indent=2)
    print(f"\n  Comparison JSON saved → {out_compare}")

    # bar chart
    _make_comparison_chart(valid)

    # file index
    print("\n  OUTPUT FILES")
    _hline("-")
    for r in valid:
        print(f"  [{r['scenario']}] {r['method']}")
        for k, v in r.items():
            if k.startswith("output_"):
                lbl = k.replace("output_", "").replace("_", " ").upper()
                print(f"       {lbl:<14}: {v}")


def _make_comparison_chart(results):
    try:
        import matplotlib.pyplot as plt
        import numpy as np

        scenarios = [r["scenario"] for r in results]
        n = len(scenarios)
        x = np.arange(n)
        w = 0.22

        fig, axes = plt.subplots(1, 3, figsize=(16, 5))
        fig.suptitle(
            f"Scenario Comparison  (T_MAX={T_MAX}d, c_late=${C_LATE:,.0f}, c_early=${C_EARLY:,.0f})",
            fontsize=13, weight="bold",
        )

        colors = ["#3b82f6", "#f59e0b", "#10b981"]

        # ── Left: makespan ──
        ax = axes[0]
        bl  = [r["baseline_makespan"] for r in results]
        opt = [r["makespan"] for r in results]
        opt_err = [r.get("makespan_std", 0.0) for r in results]
        bars1 = ax.bar(x - w/2, bl,  w, label="Baseline",  color="#94a3b8")
        bars2 = ax.bar(x + w/2, opt, w, yerr=opt_err, capsize=4, label="Optimized", color=colors[:n])
        ax.axhline(T_MAX, color="red", linestyle="--", linewidth=1.2, label=f"T_MAX={T_MAX}")
        ax.set_xticks(x); ax.set_xticklabels(scenarios)
        ax.set_title("Makespan (days)"); ax.legend(fontsize=8)
        ax.set_ylabel("Days")
        for b in bars2:
            ax.text(b.get_x() + b.get_width()/2, b.get_height() + 1,
                    f"{b.get_height():.0f}", ha="center", va="bottom", fontsize=8)

        # ── Middle: cost breakdown ──
        ax = axes[1]
        # For Scenario C, split crash vs normal cost in the stacked bar
        labor_base = []
        crash_extra = []
        for r in results:
            if r["scenario"] == "C":
                labor_base.append(r.get("normal_cost", r["labor_cost"]))
                crash_extra.append(r.get("crash_cost", 0.0))
            else:
                labor_base.append(r["labor_cost"])
                crash_extra.append(0.0)

        penalty_vals = [r["penalty"] for r in results]
        bonus_vals   = [-r["bonus"]  for r in results]   # negative = savings

        ax.bar(x, labor_base,   label="Labor/Normal cost", color="#3b82f6")
        ax.bar(x, crash_extra,  bottom=labor_base,         label="Crash cost (extra)", color="#f59e0b")
        ax.bar(x, penalty_vals, bottom=[a+b for a,b in zip(labor_base, crash_extra)],
               label="Late penalty", color="#ef4444")
        ax.bar(x, bonus_vals,   bottom=[a+b for a,b in zip(labor_base, crash_extra)],
               label="Early bonus (−)", color="#10b981")
        ax.set_xticks(x); ax.set_xticklabels(scenarios)
        ax.set_title("Cost Breakdown (USD)"); ax.legend(fontsize=8)
        ax.set_ylabel("USD")

        # ── Right: total cost ──
        ax = axes[2]
        totals = [r["total_cost"] for r in results]
        total_err = [r.get("total_cost_std", 0.0) for r in results]
        bars = ax.bar(x, totals, yerr=total_err, capsize=4, color=colors[:n], edgecolor="black", linewidth=0.5)
        ax.set_xticks(x); ax.set_xticklabels(scenarios)
        ax.set_title("Total Cost (USD)")
        ax.set_ylabel("USD")
        for b, v in zip(bars, totals):
            ax.text(b.get_x() + b.get_width()/2, b.get_height() + max(abs(v)*0.01, 500),
                    f"${v:,.0f}", ha="center", va="bottom", fontsize=8)

        plt.tight_layout()
        out = os.path.join(OUTPUTS_DIR, "comparison_chart.png")
        plt.savefig(out, dpi=150, bbox_inches="tight")
        plt.close()
        print(f"\n  Comparison chart   → {out}")
    except Exception as ex:
        print(f"  [warn] Chart generation failed: {ex}")


# ════════════════════════════════════════════════════════════════════════════
# MAIN
# ════════════════════════════════════════════════════════════════════════════

def _run_worker(runner_func):
    import io, sys
    buf = io.StringIO()
    old_out, old_err = sys.stdout, sys.stderr
    try:
        sys.stdout = buf
        sys.stderr = buf
        res = runner_func()
        return res, buf.getvalue(), None
    except Exception as ex:
        import traceback
        return None, buf.getvalue(), traceback.format_exc()
    finally:
        sys.stdout = old_out
        sys.stderr = old_err


def main():
    print()
    print("╔══════════════════════════════════════════════════════════════════════╗")
    print("║          PROJECT CRASHING  —  SCENARIO COMPARISON RUNNER            ║")
    print("╠══════════════════════════════════════════════════════════════════════╣")
    print(f"║  T_MAX={T_MAX}  CURRENT_DAY={CURRENT_DAY}  "
          f"c_late=${C_LATE:,.0f}  c_early=${C_EARLY:,.0f}        ║")
    print("╚══════════════════════════════════════════════════════════════════════╝")

    scenarios = [("A", run_scenario_A), ("B", run_scenario_B), ("C", run_scenario_C)]
    results = [None, None, None]

    if PARALLEL_EXECUTION:
        import concurrent.futures
        print("\n  ⚡ [PARALLEL MODE] Launching Scenarios A, B, and C simultaneously across CPU cores...")
        t_start = time.perf_counter()
        with concurrent.futures.ProcessPoolExecutor(max_workers=3) as executor:
            futures = [executor.submit(_run_worker, runner) for label, runner in scenarios]
            for idx, (label, runner) in enumerate(scenarios):
                res, out_text, err_text = futures[idx].result()
                print(out_text)
                if err_text:
                    print(f"\n  ✗  Scenario {label} failed:\n{err_text}")
                results[idx] = res
        print(f"  ⚡ All 3 scenarios finished solving in {time.perf_counter() - t_start:.1f}s wall-clock time!")
    else:
        for idx, (label, runner) in enumerate(scenarios):
            try:
                results[idx] = runner()
            except Exception as ex:
                import traceback
                print(f"\n  ✗  Scenario {label} failed: {ex}")
                traceback.print_exc()

    print_comparison(results)
    print()


if __name__ == "__main__":
    main()