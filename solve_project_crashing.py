#!/usr/bin/env python3
"""
Reusable OR-Tools solver for Dynamic Resource-Constrained Project Crashing (RCPSP-TCT).

Features
- Reads activity, resource-capacity, and resource-requirements JSON files.
- Supports deadline-driven minimum crash-cost optimization.
- Supports minimum-makespan fallback analysis when deadline is infeasible.
- Supports dynamic re-scheduling inputs: current_day + activity state locks.
- Detects precedence cycles and can apply known auto-repair for the Paint/Interior Trim pair.
- Exports solution summary and activity schedule to JSON/CSV.

Example
  python solve_project_crashing.py \
      --target-end-date 243 \
      --current-day 20 \
      --output-json outputs/solution_243.json \
      --output-csv outputs/schedule_243.csv
"""

from __future__ import annotations

import argparse
import csv
import json
import os
from dataclasses import dataclass
from decimal import Decimal
from typing import Dict, List, Optional, Tuple, Any

from ortools.sat.python import cp_model


@dataclass
class SolveConfig:
    target_end_date: Optional[int]
    current_day: int
    time_limit: float
    num_workers: int
    auto_fix_paint_trim_cycle: bool
    remove_edges: List[Tuple[str, str]]


def read_json(path: str) -> Any:
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def decimal_scale(values: List[float]) -> int:
    max_dp = 0
    for v in values:
        d = Decimal(str(v))
        dp = max(0, -d.as_tuple().exponent)
        max_dp = max(max_dp, dp)
    return 10 ** max_dp


def detect_cycle_nodes(activities: List[str], predecessors: Dict[str, List[str]]) -> List[str]:
    indeg = {a: 0 for a in activities}
    succ = {a: [] for a in activities}
    for a in activities:
        for p in predecessors[a]:
            indeg[a] += 1
            succ[p].append(a)

    q = [a for a in activities if indeg[a] == 0]
    seen = 0
    i = 0
    while i < len(q):
        u = q[i]
        i += 1
        seen += 1
        for v in succ[u]:
            indeg[v] -= 1
            if indeg[v] == 0:
                q.append(v)

    if seen == len(activities):
        return []
    return [a for a in activities if indeg[a] > 0]


def build_predecessors(
    activity_data: Dict[str, Dict[str, Any]],
    remove_edges: List[Tuple[str, str]],
    auto_fix_paint_trim_cycle: bool,
) -> Tuple[Dict[str, List[str]], List[str]]:
    activities = list(activity_data.keys())
    predecessors = {
        a: list(activity_data[a].get("required_activities", [])) for a in activities
    }

    logs: List[str] = []

    # Apply explicit edge removals first. Edge format is predecessor -> successor.
    for pred, succ in remove_edges:
        if succ in predecessors and pred in predecessors[succ]:
            predecessors[succ] = [p for p in predecessors[succ] if p != pred]
            logs.append(f"Removed precedence edge: {pred} -> {succ} (user override)")

    # Known data repair for this dataset if requested.
    if auto_fix_paint_trim_cycle:
        if (
            "Interior Trim" in predecessors
            and "Paint" in predecessors
            and "Paint" in predecessors["Interior Trim"]
            and "Interior Trim" in predecessors["Paint"]
        ):
            predecessors["Interior Trim"] = [
                p for p in predecessors["Interior Trim"] if p != "Paint"
            ]
            logs.append(
                "Auto-repair applied: removed precedence edge Paint -> Interior Trim "
                "to break 2-cycle (Paint <-> Interior Trim)."
            )

    cycle_nodes = detect_cycle_nodes(activities, predecessors)
    if cycle_nodes:
        msg = (
            "Precedence graph contains cycle(s). Nodes involved: "
            + ", ".join(cycle_nodes)
            + ". Provide --remove-edge 'A->B' overrides, or adjust source data."
        )
        raise ValueError(msg)

    return predecessors, logs


def parse_remove_edges(raw: List[str]) -> List[Tuple[str, str]]:
    edges: List[Tuple[str, str]] = []
    for item in raw:
        if "->" not in item:
            raise ValueError(
                f"Invalid --remove-edge value '{item}'. Expected format: 'Predecessor->Successor'."
            )
        left, right = item.split("->", 1)
        pred = left.strip()
        succ = right.strip()
        if not pred or not succ:
            raise ValueError(
                f"Invalid --remove-edge value '{item}'. Empty predecessor or successor."
            )
        edges.append((pred, succ))
    return edges


def load_state_file(path: Optional[str]) -> Dict[str, Dict[str, Any]]:
    if not path:
        return {}
    data = read_json(path)
    if "activity_states" in data and isinstance(data["activity_states"], dict):
        return data["activity_states"]
    if "activities" in data and isinstance(data["activities"], dict):
        return data["activities"]
    if isinstance(data, dict):
        # Allow direct mapping activity -> state object
        return data
    raise ValueError("Invalid state file format.")


def normalize_activity_states(
    activities: List[str],
    raw_states: Dict[str, Dict[str, Any]],
) -> Dict[str, Dict[str, Any]]:
    norm: Dict[str, Dict[str, Any]] = {}
    for a in activities:
        st = raw_states.get(a, {})
        status = str(st.get("status", "not_started")).strip().lower()
        if status not in {"not_started", "in_progress", "completed"}:
            raise ValueError(
                f"Invalid status for activity '{a}': '{status}'. "
                "Allowed: not_started, in_progress, completed"
            )
        norm[a] = {
            "status": status,
            "actual_start": st.get("actual_start"),
            "actual_duration": st.get("actual_duration"),
            "actual_end": st.get("actual_end"),
        }
    return norm


def _must_int(x: Any, field_name: str, activity: str) -> int:
    if x is None:
        raise ValueError(f"Missing '{field_name}' for activity '{activity}'.")
    if not isinstance(x, int):
        raise ValueError(
            f"Field '{field_name}' for activity '{activity}' must be integer, got: {x!r}"
        )
    return x


def build_model_and_solve(
    activity_data: Dict[str, Dict[str, Any]],
    resource_requirements: Dict[str, Dict[str, int]],
    resource_capacity: Dict[str, int],
    predecessors: Dict[str, List[str]],
    states: Dict[str, Dict[str, Any]],
    cfg: SolveConfig,
    mode: str,
) -> Dict[str, Any]:
    """
    mode:
      - 'cost_with_deadline': minimize crash cost subject to Cmax <= target_end_date
      - 'min_makespan': minimize Cmax (no explicit deadline)
    """
    activities = list(activity_data.keys())

    # Scale crash costs to integer coefficients.
    scale = decimal_scale([float(activity_data[a]["crash_cost"]) for a in activities])

    # Horizon strategy:
    # - deadline mode: follow spec and cap horizon at target_end_date
    # - min-makespan mode: allow a wider horizon
    if mode == "cost_with_deadline":
        if cfg.target_end_date is None:
            raise ValueError("target_end_date is required for cost_with_deadline mode")
        horizon = cfg.target_end_date
    elif mode == "min_makespan":
        sum_nt = sum(int(activity_data[a]["activity_normal_time"]) for a in activities)
        horizon = max(sum_nt + cfg.current_day + 5, (cfg.target_end_date or 0) + 5)
    else:
        raise ValueError(f"Unknown mode: {mode}")

    model = cp_model.CpModel()

    s: Dict[str, cp_model.IntVar] = {}
    d: Dict[str, cp_model.IntVar] = {}
    e: Dict[str, cp_model.IntVar] = {}
    c: Dict[str, cp_model.IntVar] = {}
    intervals: Dict[str, cp_model.IntervalVar] = {}

    NT: Dict[str, int] = {}
    MT: Dict[str, int] = {}

    for a in activities:
        nt = int(activity_data[a]["activity_normal_time"])
        mt = int(activity_data[a]["activity_min_time"])
        NT[a] = nt
        MT[a] = mt

        s[a] = model.NewIntVar(0, horizon, f"s[{a}]")
        d[a] = model.NewIntVar(mt, nt, f"d[{a}]")
        e[a] = model.NewIntVar(0, horizon, f"e[{a}]")
        c[a] = model.NewIntVar(0, nt - mt, f"c[{a}]")

        model.Add(d[a] + c[a] == nt)
        intervals[a] = model.NewIntervalVar(s[a], d[a], e[a], f"iv[{a}]")

    # Precedence
    for a in activities:
        for p in predecessors[a]:
            if p not in activity_data:
                raise ValueError(f"Activity '{a}' has unknown predecessor '{p}'.")
            model.Add(s[a] >= e[p])

    # Resource capacities via cumulative constraints
    for r, cap in resource_capacity.items():
        ivs = []
        demands = []
        for a in activities:
            dem = int(resource_requirements.get(a, {}).get(r, 0))
            if dem > 0:
                ivs.append(intervals[a])
                demands.append(dem)
        model.AddCumulative(ivs, demands, int(cap))

    # Dynamic state/current_day constraints
    for a in activities:
        st = states[a]
        status = st["status"]

        if status == "not_started":
            model.Add(s[a] >= cfg.current_day)

        elif status == "in_progress":
            actual_start = _must_int(st["actual_start"], "actual_start", a)
            if actual_start > cfg.current_day:
                raise ValueError(
                    f"Activity '{a}' marked in_progress but actual_start={actual_start} > current_day={cfg.current_day}."
                )
            model.Add(s[a] == actual_start)
            # Must still be active on current_day (end is exclusive)
            model.Add(e[a] >= cfg.current_day + 1)

            elapsed = max(0, cfg.current_day - actual_start)
            min_total_duration = max(MT[a], elapsed + 1)
            if min_total_duration > NT[a]:
                raise ValueError(
                    f"In-progress activity '{a}' cannot satisfy elapsed progress. "
                    f"Required minimum duration {min_total_duration} exceeds normal duration {NT[a]}."
                )
            model.Add(d[a] >= min_total_duration)

        elif status == "completed":
            actual_start = _must_int(st["actual_start"], "actual_start", a)
            model.Add(s[a] == actual_start)

            if st["actual_duration"] is not None:
                actual_duration = _must_int(st["actual_duration"], "actual_duration", a)
                if actual_duration < MT[a] or actual_duration > NT[a]:
                    raise ValueError(
                        f"Completed activity '{a}' has actual_duration={actual_duration} outside [{MT[a]}, {NT[a]}]."
                    )
                model.Add(d[a] == actual_duration)
            elif st["actual_end"] is not None:
                actual_end = _must_int(st["actual_end"], "actual_end", a)
                model.Add(e[a] == actual_end)
            else:
                raise ValueError(
                    f"Completed activity '{a}' requires either actual_duration or actual_end in state file."
                )

            model.Add(e[a] <= cfg.current_day)

    Cmax = model.NewIntVar(0, horizon, "Cmax")
    for a in activities:
        model.Add(Cmax >= e[a])

    # Objective
    if mode == "cost_with_deadline":
        assert cfg.target_end_date is not None
        model.Add(Cmax <= cfg.target_end_date)

        # Past completed costs are sunk and excluded from objective.
        terms = []
        for a in activities:
            if states[a]["status"] != "completed":
                coeff = int(Decimal(str(activity_data[a]["crash_cost"])) * scale)
                terms.append(coeff * c[a])

        total_crash_cost_scaled = model.NewIntVar(0, 10**12, "total_crash_cost_scaled")
        if terms:
            model.Add(total_crash_cost_scaled == sum(terms))
        else:
            model.Add(total_crash_cost_scaled == 0)
        model.Minimize(total_crash_cost_scaled)

    else:  # min_makespan
        total_crash_cost_scaled = model.NewIntVar(0, 10**12, "total_crash_cost_scaled")
        model.Add(total_crash_cost_scaled == 0)
        model.Minimize(Cmax)

    solver = cp_model.CpSolver()
    solver.parameters.max_time_in_seconds = cfg.time_limit
    solver.parameters.num_search_workers = cfg.num_workers

    status = solver.Solve(model)
    status_name = solver.StatusName(status)

    result: Dict[str, Any] = {
        "status": status_name,
        "mode": mode,
        "horizon": horizon,
        "scale": scale,
    }

    if status not in (cp_model.OPTIMAL, cp_model.FEASIBLE):
        return result

    schedule_rows = []
    total_crash_cost_unscaled = Decimal("0")
    total_crash_days = 0
    crashed_activities = []

    for a in activities:
        start = solver.Value(s[a])
        dur = solver.Value(d[a])
        end = solver.Value(e[a])
        crash_days = solver.Value(c[a])
        crash_cost_day = Decimal(str(activity_data[a]["crash_cost"]))
        row_cost = crash_cost_day * Decimal(crash_days)

        # Follow objective definition: completed activities are sunk costs.
        if states[a]["status"] != "completed":
            total_crash_cost_unscaled += row_cost

        total_crash_days += crash_days

        row = {
            "activity": a,
            "status": states[a]["status"],
            "start": start,
            "end": end,
            "duration": dur,
            "normal_duration": NT[a],
            "min_duration": MT[a],
            "crash_days": crash_days,
            "crash_cost_per_day": float(crash_cost_day),
            "crash_cost": float(row_cost),
        }
        schedule_rows.append(row)

        if crash_days > 0:
            crashed_activities.append(row)

    schedule_rows.sort(key=lambda x: (x["start"], x["end"], x["activity"]))
    crashed_activities.sort(key=lambda x: (-x["crash_cost"], x["activity"]))

    result.update(
        {
            "objective_value": float(total_crash_cost_unscaled)
            if mode == "cost_with_deadline"
            else int(solver.Value(Cmax)),
            "makespan": int(solver.Value(Cmax)),
            "total_crash_cost": float(total_crash_cost_unscaled),
            "total_crash_days": int(total_crash_days),
            "num_crashed_activities": len(crashed_activities),
            "crashed_activities": crashed_activities,
            "schedule": schedule_rows,
        }
    )

    return result


def write_json(path: Optional[str], data: Dict[str, Any]) -> None:
    if not path:
        return
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)


def write_schedule_csv(path: Optional[str], schedule: List[Dict[str, Any]]) -> None:
    if not path:
        return
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    fields = [
        "activity",
        "status",
        "start",
        "end",
        "duration",
        "normal_duration",
        "min_duration",
        "crash_days",
        "crash_cost_per_day",
        "crash_cost",
    ]
    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader()
        writer.writerows(schedule)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Solve dynamic RCPSP-TCT project crashing with OR-Tools CP-SAT"
    )
    parser.add_argument(
        "--activity-data",
        default="data/activity_data_v3.json",
        help="Path to activity_data JSON",
    )
    parser.add_argument(
        "--resource-capacity",
        default="data/resource_capacity_v3.json",
        help="Path to resource_capacity JSON",
    )
    parser.add_argument(
        "--resource-requirements",
        default="data/resource_requirements_v3.json",
        help="Path to resource_requirements JSON",
    )
    parser.add_argument(
        "--state-file",
        default=None,
        help="Optional path to activity states JSON",
    )
    parser.add_argument(
        "--target-end-date",
        type=int,
        default=None,
        help="Target absolute deadline day (if omitted, script runs min-makespan mode)",
    )
    parser.add_argument(
        "--current-day",
        type=int,
        default=0,
        help="Current execution day",
    )
    parser.add_argument("--time-limit", type=float, default=60.0, help="Solver time limit in seconds")
    parser.add_argument("--num-workers", type=int, default=8, help="CP-SAT workers")
    parser.add_argument(
        "--remove-edge",
        action="append",
        default=[],
        help="Remove precedence edge in format 'Predecessor->Successor'. Can be repeated.",
    )
    parser.add_argument(
        "--disable-auto-paint-trim-fix",
        action="store_true",
        help="Disable built-in repair for Paint<->Interior Trim 2-cycle.",
    )
    parser.add_argument(
        "--output-json",
        default="outputs/solution.json",
        help="Path to output solution JSON",
    )
    parser.add_argument(
        "--output-csv",
        default="outputs/schedule.csv",
        help="Path to output schedule CSV",
    )
    parser.add_argument(
        "--print-top",
        type=int,
        default=25,
        help="How many schedule rows to print to console",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()

    activity_data = read_json(args.activity_data)
    resource_capacity = read_json(args.resource_capacity)
    resource_requirements = read_json(args.resource_requirements)

    activities = list(activity_data.keys())

    # Basic consistency checks
    missing_req = [a for a in activities if a not in resource_requirements]
    if missing_req:
        raise ValueError(f"Missing resource requirement entries for activities: {missing_req}")

    for a in activities:
        for p in activity_data[a].get("required_activities", []):
            if p not in activity_data:
                raise ValueError(f"Activity '{a}' has unknown predecessor '{p}'.")

    remove_edges = parse_remove_edges(args.remove_edge)
    predecessors, cycle_logs = build_predecessors(
        activity_data=activity_data,
        remove_edges=remove_edges,
        auto_fix_paint_trim_cycle=not args.disable_auto_paint_trim_fix,
    )

    raw_states = load_state_file(args.state_file)
    states = normalize_activity_states(activities, raw_states)

    cfg = SolveConfig(
        target_end_date=args.target_end_date,
        current_day=args.current_day,
        time_limit=args.time_limit,
        num_workers=args.num_workers,
        auto_fix_paint_trim_cycle=not args.disable_auto_paint_trim_fix,
        remove_edges=remove_edges,
    )

    if args.target_end_date is not None:
        primary = build_model_and_solve(
            activity_data,
            resource_requirements,
            resource_capacity,
            predecessors,
            states,
            cfg,
            mode="cost_with_deadline",
        )

        result = {
            "input": {
                "target_end_date": args.target_end_date,
                "current_day": args.current_day,
                "activity_data": args.activity_data,
                "resource_capacity": args.resource_capacity,
                "resource_requirements": args.resource_requirements,
                "state_file": args.state_file,
            },
            "preprocessing_logs": cycle_logs,
            "primary": primary,
        }

        if primary["status"] in {"INFEASIBLE", "MODEL_INVALID", "UNKNOWN"}:
            fallback = build_model_and_solve(
                activity_data,
                resource_requirements,
                resource_capacity,
                predecessors,
                states,
                cfg,
                mode="min_makespan",
            )
            result["fallback_min_makespan"] = fallback
        else:
            result["fallback_min_makespan"] = None

    else:
        min_ms = build_model_and_solve(
            activity_data,
            resource_requirements,
            resource_capacity,
            predecessors,
            states,
            cfg,
            mode="min_makespan",
        )
        result = {
            "input": {
                "target_end_date": None,
                "current_day": args.current_day,
                "activity_data": args.activity_data,
                "resource_capacity": args.resource_capacity,
                "resource_requirements": args.resource_requirements,
                "state_file": args.state_file,
            },
            "preprocessing_logs": cycle_logs,
            "primary": min_ms,
            "fallback_min_makespan": None,
        }

    write_json(args.output_json, result)

    primary = result["primary"]
    if "schedule" in primary:
        write_schedule_csv(args.output_csv, primary["schedule"])

    # Console summary
    print("=== RCPSP-TCT Solve Summary ===")
    print("Primary status:", primary["status"])
    for log in cycle_logs:
        print("[preprocess]", log)

    if "makespan" in primary:
        print("Makespan:", primary["makespan"])
    if primary.get("mode") == "cost_with_deadline" and "total_crash_cost" in primary:
        print("Total crash cost:", primary["total_crash_cost"])
        print("Num crashed activities:", primary.get("num_crashed_activities", 0))

    if "schedule" in primary:
        print("\nTop schedule rows:")
        for row in primary["schedule"][: args.print_top]:
            print(
                f"{row['start']:>4} -> {row['end']:<4} | d={row['duration']:<3} "
                f"cr={row['crash_days']:<2} | {row['activity']}"
            )

    if result.get("fallback_min_makespan"):
        fb = result["fallback_min_makespan"]
        print("\nFallback min-makespan status:", fb["status"])
        if "makespan" in fb:
            print("Shortest achievable makespan:", fb["makespan"])

    if args.output_json:
        print("\nWrote JSON:", args.output_json)
    if args.output_csv and "schedule" in primary:
        print("Wrote CSV:", args.output_csv)


if __name__ == "__main__":
    main()
