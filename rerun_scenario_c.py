"""
rerun_scenario_c.py  -- re-run Scenario C only, update comparison_summary.json
Run from project root: python rerun_scenario_c.py
"""
import os, sys, time, json, warnings
warnings.filterwarnings("ignore")

ROOT_DIR    = os.path.dirname(os.path.abspath(__file__))
BASE_DIR    = os.path.join(ROOT_DIR, "implementasi-base")
HYBRID_DATA = os.path.join(ROOT_DIR, "implementasi-hybrid", "data")
OUTPUTS_DIR = os.path.join(ROOT_DIR, "outputs")
os.makedirs(OUTPUTS_DIR, exist_ok=True)

sys.path.insert(0, BASE_DIR)

T_MAX        = 310
CURRENT_DAY  = 0
C_LATE       = 5000.0
C_EARLY      = 2000.0
CPSAT_TIME   = 120.0

from solver_base import (
    read_json, build_predecessors,
    infer_activity_states_without_state_file,
    SolveConfig, build_model_and_solve,
    build_reference_no_crash_schedule,
    generate_gantt_comparison_plot,
    write_json, write_schedule_csv,
)

act = read_json(os.path.join(HYBRID_DATA, "activity_data.json"))
rc  = read_json(os.path.join(HYBRID_DATA, "resource_capacity.json"))
rr  = read_json(os.path.join(HYBRID_DATA, "resource_requirements.json"))

preds, _ = build_predecessors(act, [], True)
states, _ = infer_activity_states_without_state_file(act, rr, rc, preds, CURRENT_DAY, CPSAT_TIME, 1)
baseline_sched    = build_reference_no_crash_schedule(act, rr, rc, preds, CURRENT_DAY, CPSAT_TIME, 1)
baseline_makespan = max(v["end"] for v in baseline_sched.values())
print(f"Baseline makespan: {baseline_makespan} days")

cfg = SolveConfig(
    target_end_date=T_MAX, current_day=CURRENT_DAY,
    time_limit=CPSAT_TIME, num_workers=1,
    auto_fix_paint_trim_cycle=True, remove_edges=[],
    c_late=C_LATE, c_early=C_EARLY,
)

t0 = time.perf_counter()
result = build_model_and_solve(act, rr, rc, preds, states, cfg, mode="bonus_penalty")
elapsed = time.perf_counter() - t0

status = result.get("status", "UNKNOWN")
print(f"Status: {status},  Makespan: {result.get('makespan')} days,  Solve time: {elapsed:.1f}s")

makespan   = result["makespan"]
crash_cost = result["total_crash_cost"]
total_normal_cost = sum(float(a.get("activity_base_cost", 0.0)) for a in act.values())
total_comparable_cost = total_normal_cost + crash_cost
penalty  = C_LATE  * max(0, makespan - T_MAX)
bonus    = C_EARLY * max(0, T_MAX - makespan)
total_cost = total_comparable_cost + penalty - bonus

result.update({
    "total_normal_cost":     total_normal_cost,
    "total_comparable_cost": total_comparable_cost,
    "penalty": penalty, "bonus": bonus, "total_cost": total_cost,
})

out_json  = os.path.join(OUTPUTS_DIR, "C_cpsat.json")
out_csv   = os.path.join(OUTPUTS_DIR, "C_cpsat_schedule.csv")
out_gantt = os.path.join(OUTPUTS_DIR, "C_cpsat_gantt.png")
write_json(out_json, result)
if "schedule" in result:
    write_schedule_csv(out_csv, result["schedule"])
try:
    generate_gantt_comparison_plot(baseline_sched, result.get("schedule", []), CURRENT_DAY, out_gantt)
except Exception as ex:
    print(f"[warn] Gantt: {ex}")

print(f"\nCrash cost     : ${crash_cost:,.2f}")
print(f"Normal cost    : ${total_normal_cost:,.2f}  (Sum W_ik*r_k)")
print(f"Comparable cost: ${total_comparable_cost:,.2f}")
print(f"Penalty        : ${penalty:,.2f}   Bonus: ${bonus:,.2f}")
print(f"Total cost     : ${total_cost:,.2f}")

# Update comparison_summary.json — keep A and B unchanged
summary_path = os.path.join(OUTPUTS_DIR, "comparison_summary.json")
with open(summary_path, "r") as f:
    summary = json.load(f)

c_entry = {
    "scenario": "C",
    "method": "CP-SAT (linear crash cost)",
    "baseline_makespan": float(baseline_makespan),
    "makespan": float(makespan),
    "makespan_reduction": float(baseline_makespan - makespan),
    "labor_cost": total_comparable_cost,
    "crash_cost": crash_cost,
    "normal_cost": total_normal_cost,
    "penalty": penalty,
    "bonus": bonus,
    "total_cost": total_cost,
    "solve_time_s": round(elapsed, 2),
    "output_json": out_json,
    "output_csv": out_csv,
    "output_gantt_png": out_gantt,
}
summary["results"] = [r if r["scenario"] != "C" else c_entry for r in summary["results"]]
with open(summary_path, "w") as f:
    json.dump(summary, f, indent=2)
print(f"\nUpdated {summary_path}")
