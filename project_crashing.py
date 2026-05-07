"""
Project Crashing Optimization for Commercial Construction
==========================================================
Mathematical model to find optimal activity acceleration strategy.

Features:
  - CPM baseline analysis (critical path, durations, costs)
  - LP-based optimization using piecewise-linear cost approximation
  - Genetic Algorithm for nonlinear optimization
  - Time-cost tradeoff curve generation
  - Sensitivity analysis

Author : Adiel Rum (assisted by AI)
Date   : March 2026
"""

import pandas as pd
import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from pulp import *
import os, sys, re, copy, random, warnings, math
from collections import defaultdict
from dataclasses import dataclass, field
from typing import Dict, List, Tuple, Optional, Set

warnings.filterwarnings("ignore")
plt.rcParams.update({
    "figure.figsize": (14, 7),
    "font.size": 11,
    "axes.titlesize": 14,
    "axes.labelsize": 12,
})

# ╔══════════════════════════════════════════════════════════════╗
# ║                    CONFIGURATION                            ║
# ╚══════════════════════════════════════════════════════════════╝

EXCHANGE_RATE      = 16_000          # 1 USD = Rp 16,000
PENALTY_PER_DAY    = 150_000_000     # Rp per day late
BONUS_PER_DAY      = 100_000_000     # Rp per day early
CRASH_RATIO        = 0.50            # activities can be crashed to 50 % of normal
COST_EXPONENT      = 1.2             # alpha – cost escalation exponent
LP_SEGMENTS        = 10              # piecewise-linear breakpoints per activity
GA_POP_SIZE        = 200
GA_GENERATIONS     = 300
GA_TOURNAMENT_SIZE = 3
GA_CROSSOVER_PROB  = 0.9
GA_MUTATION_PROB   = 0.1
GA_ELITISM_FRAC    = 0.10

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
CSV_DIR  = os.path.join(BASE_DIR, "Schedules_CSV")
OUT_DIR  = os.path.join(BASE_DIR, "output")
os.makedirs(OUT_DIR, exist_ok=True)

# ╔══════════════════════════════════════════════════════════════╗
# ║                  DATA  STRUCTURES                           ║
# ╚══════════════════════════════════════════════════════════════╝

@dataclass
class Task:
    id: int
    name: str
    duration_days: int          # normal duration (working days)
    predecessors: list          # [(pred_id, rel_type, lag_days), ...]
    outline_level: int
    is_summary: bool = False
    normal_cost_rp: float = 0.0
    crash_duration: int = 0
    # CPM fields
    es: int = 0
    ef: int = 0
    ls: int = 0
    lf: int = 0
    total_float: int = 0

@dataclass
class Resource:
    id: int
    name: str
    rate_per_hour_usd: float
    max_units: float

# ╔══════════════════════════════════════════════════════════════╗
# ║                  PARSERS  &  HELPERS                        ║
# ╚══════════════════════════════════════════════════════════════╝

def parse_duration(s: str) -> int:
    """Convert '3 days', '2 wks', '1 wk', '12 wks', '1 day' → working days."""
    s = str(s).strip().lower()
    m = re.match(r"([\d.]+)\s*(day|days|wk|wks|week|weeks)", s)
    if not m:
        return 0
    val = float(m.group(1))
    unit = m.group(2)
    if unit in ("wk", "wks", "week", "weeks"):
        return int(val * 5)
    return int(val)

def parse_work_hours(s: str) -> float:
    """'24h' → 24.0"""
    s = str(s).strip().lower().replace("h", "").replace(",", "")
    try:
        return float(s)
    except ValueError:
        return 0.0

def parse_rate(s: str) -> float:
    """'$50.00/h' → 50.0"""
    s = str(s).strip()
    m = re.search(r"\$([\d,.]+)", s)
    return float(m.group(1).replace(",", "")) if m else 0.0

def parse_units(s: str) -> float:
    """'100%' → 1.0,  '50%' → 0.5"""
    s = str(s).strip().replace("%", "")
    try:
        return float(s) / 100.0
    except ValueError:
        return 1.0

def parse_predecessors(s: str) -> List[Tuple[int, str, int]]:
    """
    Parse predecessor strings like:
      '2'          → [(2, 'FS', 0)]
      '18,19'      → [(18,'FS',0), (19,'FS',0)]
      '27FF+1d'    → [(27,'FF',1)]
      '88FS+5d'    → [(88,'FS',5)]
      '27FF+1d,28' → [(27,'FF',1), (28,'FS',0)]
    """
    if pd.isna(s) or str(s).strip() == "":
        return []
    result = []
    for token in str(s).split(","):
        token = token.strip()
        m = re.match(r"(\d+)\s*(FS|FF|SS|SF)?\s*([+-]\d+d?)?", token, re.IGNORECASE)
        if not m:
            continue
        pred_id = int(m.group(1))
        rel = (m.group(2) or "FS").upper()
        lag_str = m.group(3) or ""
        lag = int(re.sub(r"[dD]", "", lag_str)) if lag_str else 0
        result.append((pred_id, rel, lag))
    return result

# ╔══════════════════════════════════════════════════════════════╗
# ║                      DATA  LOADING                          ║
# ╚══════════════════════════════════════════════════════════════╝

def load_data():
    """Load and parse all CSV files, return work tasks, resources, cost dict."""

    # ---- Tasks ----
    task_df = pd.read_csv(os.path.join(CSV_DIR, "Task_Table.csv"))
    all_tasks: Dict[int, Task] = {}
    summary_ids: Set[int] = set()

    for _, row in task_df.iterrows():
        tid   = int(row["ID"])
        ol    = int(row["Outline Level"])
        preds = parse_predecessors(row.get("Predecessors", ""))
        dur   = parse_duration(str(row["Duration"]))

        is_summ = (ol == 0) or (ol == 1 and len(preds) == 0)
        if is_summ:
            summary_ids.add(tid)

        t = Task(
            id=tid,
            name=str(row["Name"]).strip(),
            duration_days=dur,
            predecessors=preds,
            outline_level=ol,
            is_summary=is_summ,
        )
        t.crash_duration = max(1, int(math.ceil(dur * (1 - CRASH_RATIO))))
        all_tasks[tid] = t

    work_tasks = {k: v for k, v in all_tasks.items() if not v.is_summary}

    # filter predecessors to only reference existing work tasks
    for t in work_tasks.values():
        t.predecessors = [(p, r, l) for p, r, l in t.predecessors if p in work_tasks]

    # ---- Resources ----
    res_df = pd.read_csv(os.path.join(CSV_DIR, "Resource_Table.csv"))
    resources: Dict[str, Resource] = {}
    for _, row in res_df.iterrows():
        r = Resource(
            id=int(row["ID"]),
            name=str(row["Name"]).strip(),
            rate_per_hour_usd=parse_rate(str(row["Standard Rate"])),
            max_units=parse_units(str(row["Max Units"])),
        )
        resources[r.name] = r

    # ---- Assignments → compute normal cost per task ----
    asgn_df = pd.read_csv(os.path.join(CSV_DIR, "Assignment_Table.csv"))
    task_name_to_id = {t.name: t.id for t in work_tasks.values()}

    for _, row in asgn_df.iterrows():
        tname = str(row["Task Name"]).strip()
        rname = str(row["Resource Name"]).strip()
        whrs  = parse_work_hours(str(row["Work"]))
        if tname not in task_name_to_id:
            continue
        tid = task_name_to_id[tname]
        rate_usd = resources[rname].rate_per_hour_usd if rname in resources else 50.0
        cost_rp = whrs * rate_usd * EXCHANGE_RATE  # convert to Rp
        work_tasks[tid].normal_cost_rp += cost_rp

    print(f"  Loaded {len(work_tasks)} work tasks, {len(resources)} resources")
    return work_tasks, resources

# ╔══════════════════════════════════════════════════════════════╗
# ║                        CPM  ENGINE                          ║
# ╚══════════════════════════════════════════════════════════════╝

def topological_sort(tasks: Dict[int, Task]) -> List[int]:
    """Kahn's algorithm – returns task IDs in topological order."""
    in_deg = defaultdict(int)
    adj = defaultdict(list)
    for t in tasks.values():
        if t.id not in in_deg:
            in_deg[t.id] = 0
        for pid, _, _ in t.predecessors:
            adj[pid].append(t.id)
            in_deg[t.id] += 1
    queue = [tid for tid in tasks if in_deg[tid] == 0]
    queue.sort()
    order = []
    while queue:
        u = queue.pop(0)
        order.append(u)
        for v in sorted(adj[u]):
            in_deg[v] -= 1
            if in_deg[v] == 0:
                queue.append(v)
    return order

def cpm_forward(tasks: Dict[int, Task], topo: List[int],
                durations: Optional[Dict[int, int]] = None) -> int:
    """Forward pass – compute ES, EF.  Returns project duration."""
    dur = durations or {t.id: t.duration_days for t in tasks.values()}
    for tid in topo:
        t = tasks[tid]
        es = 0
        for pid, rel, lag in t.predecessors:
            p = tasks[pid]
            if rel == "FS":
                es = max(es, p.ef + lag)
            elif rel == "FF":
                # EF_j >= EF_i + lag  →  ES_j >= EF_i + lag - d_j
                es = max(es, p.ef + lag - dur[tid])
            elif rel == "SS":
                es = max(es, p.es + lag)
            elif rel == "SF":
                es = max(es, p.es + lag - dur[tid])
        t.es = es
        t.ef = es + dur[tid]
    return max(t.ef for t in tasks.values())

def cpm_backward(tasks: Dict[int, Task], topo: List[int], project_dur: int,
                 durations: Optional[Dict[int, int]] = None):
    """Backward pass – compute LS, LF, total float."""
    dur = durations or {t.id: t.duration_days for t in tasks.values()}
    # build successor map
    succ_map = defaultdict(list)  # pid → [(tid, rel, lag)]
    for t in tasks.values():
        for pid, rel, lag in t.predecessors:
            succ_map[pid].append((t.id, rel, lag))

    for tid in reversed(topo):
        t = tasks[tid]
        lf = project_dur
        for sid, rel, lag in succ_map.get(tid, []):
            s = tasks[sid]
            if rel == "FS":
                lf = min(lf, s.ls - lag)
            elif rel == "FF":
                lf = min(lf, s.lf - lag)
            elif rel == "SS":
                lf = min(lf, s.ls - lag + dur[tid])
            elif rel == "SF":
                lf = min(lf, s.lf - lag + dur[tid])
        t.lf = lf
        t.ls = lf - dur[tid]
        t.total_float = t.ls - t.es

def run_cpm(tasks: Dict[int, Task],
            durations: Optional[Dict[int, int]] = None) -> int:
    """Full CPM pass: forward + backward. Returns project duration."""
    topo = topological_sort(tasks)
    pdur = cpm_forward(tasks, topo, durations)
    cpm_backward(tasks, topo, pdur, durations)
    return pdur

def get_critical_path(tasks: Dict[int, Task]) -> List[int]:
    """Return list of task IDs on the critical path (float = 0)."""
    return sorted([t.id for t in tasks.values() if t.total_float == 0],
                  key=lambda x: tasks[x].es)

# ╔══════════════════════════════════════════════════════════════╗
# ║                     COST  MODEL                             ║
# ╚══════════════════════════════════════════════════════════════╝

def crash_cost_func(normal_cost_rp: float, d_normal: int, d_actual: int,
                    alpha: float = COST_EXPONENT) -> float:
    """
    Power-law crash cost:  C(d) = NormalCost × (d_normal / d_actual)^alpha
    Returns total activity cost (Rp) at duration d_actual.
    """
    if d_actual <= 0:
        d_actual = 1
    if d_normal <= 0:
        return normal_cost_rp
    return normal_cost_rp * (d_normal / d_actual) ** alpha

def additional_crash_cost(normal_cost_rp: float, d_normal: int, d_actual: int,
                          alpha: float = COST_EXPONENT) -> float:
    """Additional cost incurred by crashing from d_normal to d_actual."""
    return crash_cost_func(normal_cost_rp, d_normal, d_actual, alpha) - normal_cost_rp

def compute_baseline_cost(tasks: Dict[int, Task]) -> float:
    """Sum of normal costs for all work tasks (Rp)."""
    return sum(t.normal_cost_rp for t in tasks.values())

def compute_total_cost(tasks: Dict[int, Task], durations: Dict[int, int],
                       project_dur: int, deadline: int) -> dict:
    """Compute full cost breakdown given durations and project duration."""
    crash_cost = sum(
        crash_cost_func(tasks[tid].normal_cost_rp, tasks[tid].duration_days, d)
        for tid, d in durations.items()
    )
    normal_cost = compute_baseline_cost(tasks)
    extra_crash = crash_cost - normal_cost
    late_days = max(0, project_dur - deadline)
    early_days = max(0, deadline - project_dur)
    penalty = PENALTY_PER_DAY * late_days
    bonus   = BONUS_PER_DAY * early_days
    total   = crash_cost + penalty - bonus

    return {
        "normal_cost": normal_cost,
        "crash_cost": crash_cost,
        "extra_crash_cost": extra_crash,
        "late_days": late_days,
        "early_days": early_days,
        "penalty": penalty,
        "bonus": bonus,
        "total_cost": total,
        "project_duration": project_dur,
    }

# ╔══════════════════════════════════════════════════════════════╗
# ║               LP  SOLVER  (PIECEWISE-LINEAR)                ║
# ╚══════════════════════════════════════════════════════════════╝

def solve_lp(tasks: Dict[int, Task], deadline: int,
             target_duration: Optional[int] = None,
             verbose: bool = False) -> Optional[dict]:
    """
    Solve the project crashing LP with piecewise-linear cost approximation.

    If target_duration is given, add constraint T ≤ target_duration and
    minimise pure crash cost (no penalty/bonus).
    Otherwise, minimise total cost including penalty/bonus.
    """
    tids = sorted(tasks.keys())
    n = len(tids)
    tid_idx = {tid: i for i, tid in enumerate(tids)}

    prob = LpProblem("ProjectCrashing", LpMinimize)

    # ── decision variables ──
    S = {tid: LpVariable(f"S_{tid}", lowBound=0) for tid in tids}
    x = {tid: LpVariable(f"x_{tid}", lowBound=0,
                          upBound=max(0, tasks[tid].duration_days - tasks[tid].crash_duration))
         for tid in tids}
    T = LpVariable("T", lowBound=0)

    # ── piecewise-linear crash cost variables ──
    # For each activity, divide crash range [0, max_crash] into K segments
    K = LP_SEGMENTS
    lam = {}   # lam[tid][k] = amount of crash used in segment k
    seg_slopes = {}  # marginal cost per day in each segment

    for tid in tids:
        t = tasks[tid]
        max_crash = t.duration_days - t.crash_duration
        if max_crash <= 0:
            seg_slopes[tid] = []
            continue

        breakpoints = np.linspace(0, max_crash, K + 1)
        slopes = []
        for k in range(K):
            x_lo = breakpoints[k]
            x_hi = breakpoints[k + 1]
            d_lo = t.duration_days - x_lo
            d_hi = t.duration_days - x_hi
            c_lo = additional_crash_cost(t.normal_cost_rp, t.duration_days, d_lo)
            c_hi = additional_crash_cost(t.normal_cost_rp, t.duration_days, d_hi)
            seg_width = x_hi - x_lo
            slope = (c_hi - c_lo) / seg_width if seg_width > 0 else 0
            slopes.append(slope)

            var = LpVariable(f"lam_{tid}_{k}", lowBound=0, upBound=seg_width)
            lam[(tid, k)] = var

        seg_slopes[tid] = slopes

    # ── link x_i to segment variables ──
    for tid in tids:
        max_crash = tasks[tid].duration_days - tasks[tid].crash_duration
        if max_crash <= 0:
            prob += x[tid] == 0, f"no_crash_{tid}"
            continue
        prob += x[tid] == lpSum(lam[(tid, k)] for k in range(K)), f"link_x_{tid}"

    # ── additional crash cost expression ──
    crash_cost_expr = lpSum(
        seg_slopes[tid][k] * lam[(tid, k)]
        for tid in tids
        for k in range(len(seg_slopes.get(tid, [])))
    )

    # ── objective ──
    if target_duration is not None:
        # pure crash cost minimisation with duration cap
        prob += crash_cost_expr, "Minimize_Crash_Cost"
        prob += T <= target_duration, "target_duration_cap"
    else:
        # include penalty/bonus via a single convex net-time-cost variable.
        # net_time_cost = max(P*(T-D), -B*(D-T))  which is convex, so
        # in minimisation the solver picks the correct piece.
        net_time_cost = LpVariable("net_time_cost")
        prob += net_time_cost >= PENALTY_PER_DAY * (T - deadline), "penalty_bound"
        prob += net_time_cost >= -BONUS_PER_DAY  * (deadline - T), "bonus_bound"
        prob += crash_cost_expr + net_time_cost, "Minimize_Total_Cost"

    # ── precedence constraints ──
    for tid in tids:
        t = tasks[tid]
        d_n = t.duration_days
        for pid, rel, lag in t.predecessors:
            p = tasks[pid]
            p_dn = p.duration_days
            if rel == "FS":
                # S_j >= S_i + d_i + lag  →  S_j >= S_i + (d_i_N - x_i) + lag
                prob += S[tid] >= S[pid] + p_dn - x[pid] + lag, \
                        f"prec_FS_{pid}_{tid}"
            elif rel == "FF":
                # EF_j >= EF_i + lag
                # S_j + (d_j_N - x_j) >= S_i + (d_i_N - x_i) + lag
                prob += S[tid] + d_n - x[tid] >= S[pid] + p_dn - x[pid] + lag, \
                        f"prec_FF_{pid}_{tid}"
            elif rel == "SS":
                prob += S[tid] >= S[pid] + lag, f"prec_SS_{pid}_{tid}"
            elif rel == "SF":
                prob += S[tid] + d_n - x[tid] >= S[pid] + lag, \
                        f"prec_SF_{pid}_{tid}"

    # ── project completion ──
    for tid in tids:
        t = tasks[tid]
        prob += T >= S[tid] + t.duration_days - x[tid], f"completion_{tid}"

    # ── solve ──
    solver = PULP_CBC_CMD(msg=0, timeLimit=120)
    status = prob.solve(solver)

    if LpStatus[status] != "Optimal":
        if verbose:
            print(f"  LP status: {LpStatus[status]}")
        return None

    # ── extract solution ──
    durations_out = {}
    starts_out = {}
    for tid in tids:
        crash_amt = value(x[tid]) or 0
        d = tasks[tid].duration_days - crash_amt
        durations_out[tid] = max(tasks[tid].crash_duration, round(d))
        starts_out[tid] = value(S[tid]) or 0

    proj_dur = round(value(T))
    costs = compute_total_cost(tasks, durations_out, proj_dur, deadline)
    costs["starts"] = starts_out
    costs["durations"] = durations_out
    return costs

# ╔══════════════════════════════════════════════════════════════╗
# ║                 GENETIC  ALGORITHM  SOLVER                  ║
# ╚══════════════════════════════════════════════════════════════╝

class GeneticAlgorithm:
    """GA for project crashing optimisation."""

    def __init__(self, tasks: Dict[int, Task], deadline: int, seed: int = 42):
        self.tasks = tasks
        self.deadline = deadline
        self.tids = sorted(tasks.keys())
        self.n = len(self.tids)
        self.rng = random.Random(seed)
        np.random.seed(seed)

        # pre-compute crash ranges
        self.max_crash = {
            tid: tasks[tid].duration_days - tasks[tid].crash_duration
            for tid in self.tids
        }

    def decode(self, chromosome: np.ndarray) -> Dict[int, int]:
        """Decode chromosome [0,1]^n → duration dict."""
        durs = {}
        for i, tid in enumerate(self.tids):
            crash = chromosome[i] * self.max_crash[tid]
            d = self.tasks[tid].duration_days - crash
            durs[tid] = max(self.tasks[tid].crash_duration, round(d))
        return durs

    def evaluate(self, chromosome: np.ndarray) -> float:
        """Evaluate fitness = total cost (lower is better)."""
        durs = self.decode(chromosome)
        # run CPM with these durations
        tasks_copy = copy.deepcopy(self.tasks)
        pdur = run_cpm(tasks_copy, durs)
        costs = compute_total_cost(tasks_copy, durs, pdur, self.deadline)
        return costs["total_cost"]

    def _tournament(self, pop: np.ndarray, fits: np.ndarray) -> np.ndarray:
        idxs = self.rng.sample(range(len(pop)), GA_TOURNAMENT_SIZE)
        best = min(idxs, key=lambda i: fits[i])
        return pop[best].copy()

    def _sbx_crossover(self, p1: np.ndarray, p2: np.ndarray,
                       eta: float = 2.0) -> Tuple[np.ndarray, np.ndarray]:
        c1, c2 = p1.copy(), p2.copy()
        for i in range(self.n):
            if self.rng.random() < 0.5:
                if abs(p1[i] - p2[i]) < 1e-14:
                    continue
                u = self.rng.random()
                if u <= 0.5:
                    beta = (2.0 * u) ** (1.0 / (eta + 1.0))
                else:
                    beta = (1.0 / (2.0 * (1.0 - u))) ** (1.0 / (eta + 1.0))
                c1[i] = 0.5 * ((1 + beta) * p1[i] + (1 - beta) * p2[i])
                c2[i] = 0.5 * ((1 - beta) * p1[i] + (1 + beta) * p2[i])
                c1[i] = np.clip(c1[i], 0.0, 1.0)
                c2[i] = np.clip(c2[i], 0.0, 1.0)
        return c1, c2

    def _polynomial_mutation(self, ind: np.ndarray,
                             eta: float = 20.0) -> np.ndarray:
        for i in range(self.n):
            if self.rng.random() < GA_MUTATION_PROB:
                u = self.rng.random()
                if u < 0.5:
                    delta = (2.0 * u) ** (1.0 / (eta + 1.0)) - 1.0
                else:
                    delta = 1.0 - (2.0 * (1.0 - u)) ** (1.0 / (eta + 1.0))
                ind[i] = np.clip(ind[i] + delta * 0.2, 0.0, 1.0)
        return ind

    def run(self, verbose: bool = True) -> dict:
        """Run the GA and return the best solution."""
        pop_size = GA_POP_SIZE
        n_elite = max(2, int(pop_size * GA_ELITISM_FRAC))

        # initialise population
        pop = np.random.rand(pop_size, self.n)
        # seed with no-crash and full-crash individuals
        pop[0] = np.zeros(self.n)
        pop[1] = np.ones(self.n)

        fits = np.array([self.evaluate(ind) for ind in pop])
        best_idx = np.argmin(fits)
        best_fit = fits[best_idx]
        best_ind = pop[best_idx].copy()

        if verbose:
            print(f"  GA Gen   0 | Best: Rp {best_fit:,.0f}")

        for gen in range(1, GA_GENERATIONS + 1):
            # elitism
            elite_idxs = np.argsort(fits)[:n_elite]
            new_pop = [pop[i].copy() for i in elite_idxs]

            while len(new_pop) < pop_size:
                p1 = self._tournament(pop, fits)
                p2 = self._tournament(pop, fits)
                if self.rng.random() < GA_CROSSOVER_PROB:
                    c1, c2 = self._sbx_crossover(p1, p2)
                else:
                    c1, c2 = p1.copy(), p2.copy()
                c1 = self._polynomial_mutation(c1)
                c2 = self._polynomial_mutation(c2)
                new_pop.extend([c1, c2])

            pop = np.array(new_pop[:pop_size])
            fits = np.array([self.evaluate(ind) for ind in pop])

            gen_best_idx = np.argmin(fits)
            if fits[gen_best_idx] < best_fit:
                best_fit = fits[gen_best_idx]
                best_ind = pop[gen_best_idx].copy()

            if verbose and (gen % 50 == 0 or gen == GA_GENERATIONS):
                print(f"  GA Gen {gen:3d} | Best: Rp {best_fit:,.0f}")

        # decode best
        durs = self.decode(best_ind)
        tasks_copy = copy.deepcopy(self.tasks)
        pdur = run_cpm(tasks_copy, durs)
        costs = compute_total_cost(tasks_copy, durs, pdur, self.deadline)
        costs["durations"] = durs
        costs["chromosome"] = best_ind
        return costs

# ╔══════════════════════════════════════════════════════════════╗
# ║              TIME-COST  TRADEOFF  CURVE                     ║
# ╚══════════════════════════════════════════════════════════════╝

def generate_time_cost_curve(tasks: Dict[int, Task],
                             baseline_dur: int, deadline: int,
                             n_points: int = 30) -> pd.DataFrame:
    """
    Sweep target durations from fully-crashed to baseline.
    For each target, solve LP to get minimum crash cost.
    """
    # find minimum feasible duration (all crashed)
    tasks_full_crash = copy.deepcopy(tasks)
    crash_durs = {tid: t.crash_duration for tid, t in tasks_full_crash.items()}
    min_dur = run_cpm(tasks_full_crash, crash_durs)

    targets = sorted(set(
        list(np.linspace(min_dur, baseline_dur, n_points).astype(int)) +
        [min_dur, baseline_dur, deadline]
    ))

    records = []
    print(f"\n  Generating time-cost curve ({len(targets)} points)...")
    for i, td in enumerate(targets):
        sol = solve_lp(tasks, deadline, target_duration=td)
        if sol is None:
            continue

        # compute full cost INCLUDING penalty / bonus at this duration
        late = max(0, sol["project_duration"] - deadline)
        early = max(0, deadline - sol["project_duration"])
        total_with_penalty = (sol["crash_cost"]
                              + PENALTY_PER_DAY * late
                              - BONUS_PER_DAY * early)

        records.append({
            "target_duration": td,
            "actual_duration": sol["project_duration"],
            "crash_cost": sol["crash_cost"],
            "extra_crash_cost": sol["extra_crash_cost"],
            "penalty": PENALTY_PER_DAY * late,
            "bonus": BONUS_PER_DAY * early,
            "total_cost": total_with_penalty,
            "direct_cost_only": sol["crash_cost"],
        })
        if (i + 1) % 10 == 0:
            print(f"    ... {i+1}/{len(targets)} done")

    print(f"  Done – {len(records)} feasible points")
    return pd.DataFrame(records)

# ╔══════════════════════════════════════════════════════════════╗
# ║                  SENSITIVITY  ANALYSIS                      ║
# ╚══════════════════════════════════════════════════════════════╝

def sensitivity_analysis(tasks: Dict[int, Task], deadline: int,
                         baseline_dur: int) -> pd.DataFrame:
    """Tornado-style sensitivity: vary one parameter at a time.

    Uses the LP in target-duration mode to find the optimal duration,
    then computes total cost including penalty/bonus externally.
    """
    # Baseline optimal: solve LP with penalty/bonus
    base_sol = solve_lp(tasks, deadline)
    if base_sol is None:
        # fallback: use baseline (no crash) cost
        base_durs = {tid: t.duration_days for tid, t in tasks.items()}
        base_info = compute_total_cost(tasks, base_durs, baseline_dur, deadline)
        base_cost = base_info["total_cost"]
    else:
        base_cost = base_sol["total_cost"]

    results = []

    def _solve_scenario(label):
        """Solve LP with current globals and record result."""
        sol = solve_lp(tasks, deadline)
        if sol:
            cost = sol["total_cost"]
        else:
            # no solution from penalty-bonus LP; sweep durations
            cost = base_cost
        results.append({"parameter": label, "total_cost": cost,
                        "delta": cost - base_cost})

    # 1. Vary penalty rate ±50 %
    for factor, label in [(0.5, "Penalty -50%"), (1.5, "Penalty +50%")]:
        global PENALTY_PER_DAY
        orig = PENALTY_PER_DAY
        PENALTY_PER_DAY = int(orig * factor)
        _solve_scenario(label)
        PENALTY_PER_DAY = orig

    # 2. Vary bonus rate ±50 %
    for factor, label in [(0.5, "Bonus -50%"), (1.5, "Bonus +50%")]:
        global BONUS_PER_DAY
        orig = BONUS_PER_DAY
        BONUS_PER_DAY = int(orig * factor)
        _solve_scenario(label)
        BONUS_PER_DAY = orig

    # 3. Vary crash ratio
    for factor, label in [(0.3, "Crash Limit 30%"), (0.7, "Crash Limit 70%")]:
        global CRASH_RATIO
        orig = CRASH_RATIO
        CRASH_RATIO = factor
        for t in tasks.values():
            t.crash_duration = max(1, int(math.ceil(t.duration_days * (1 - CRASH_RATIO))))
        _solve_scenario(label)
        CRASH_RATIO = orig
        for t in tasks.values():
            t.crash_duration = max(1, int(math.ceil(t.duration_days * (1 - CRASH_RATIO))))

    # 4. Vary cost exponent
    for alpha, label in [(1.0, "Alpha = 1.0 (linear)"), (1.5, "Alpha = 1.5")]:
        global COST_EXPONENT
        orig = COST_EXPONENT
        COST_EXPONENT = alpha
        _solve_scenario(label)
        COST_EXPONENT = orig

    return pd.DataFrame(results)

# ╔══════════════════════════════════════════════════════════════╗
# ║                    VISUALISATION                            ║
# ╚══════════════════════════════════════════════════════════════╝

def plot_time_cost_curve(curve_df: pd.DataFrame, deadline: int,
                         baseline_dur: int, baseline_cost: float):
    """Plot the time-cost tradeoff curve."""
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(18, 7))

    # ── Left panel: Direct cost only ──
    ax1.plot(curve_df["actual_duration"], curve_df["direct_cost_only"] / 1e9,
             "b-o", markersize=4, linewidth=2, label="Direct Cost (Crash)")
    ax1.axvline(deadline, color="red", linestyle="--", alpha=0.7, label=f"Deadline ({deadline}d)")
    ax1.axvline(baseline_dur, color="green", linestyle="--", alpha=0.7,
                label=f"Baseline ({baseline_dur}d)")
    ax1.set_xlabel("Project Duration (working days)")
    ax1.set_ylabel("Direct Cost (Billion Rp)")
    ax1.set_title("Direct Cost vs. Duration")
    ax1.legend(fontsize=9)
    ax1.grid(True, alpha=0.3)

    # ── Right panel: Total cost (with penalty/bonus) ──
    ax2.plot(curve_df["actual_duration"], curve_df["total_cost"] / 1e9,
             "r-s", markersize=4, linewidth=2, label="Total Cost")
    ax2.plot(curve_df["actual_duration"], curve_df["direct_cost_only"] / 1e9,
             "b--", alpha=0.5, linewidth=1, label="Direct Cost Only")

    # mark optimal
    opt_idx = curve_df["total_cost"].idxmin()
    opt_row = curve_df.iloc[opt_idx]
    ax2.scatter(opt_row["actual_duration"], opt_row["total_cost"] / 1e9,
                color="gold", s=200, zorder=5, edgecolors="black",
                label=f"Optimal ({int(opt_row['actual_duration'])}d)")
    # mark baseline
    bl_row = curve_df.loc[curve_df["actual_duration"] == baseline_dur]
    if not bl_row.empty:
        ax2.scatter(baseline_dur, bl_row.iloc[0]["total_cost"] / 1e9,
                    color="green", s=150, zorder=5, marker="D", edgecolors="black",
                    label=f"Normal Point ({baseline_dur}d)")
    # mark crash point
    crash_row = curve_df.iloc[0]
    ax2.scatter(crash_row["actual_duration"], crash_row["total_cost"] / 1e9,
                color="purple", s=150, zorder=5, marker="^", edgecolors="black",
                label=f"Crash Point ({int(crash_row['actual_duration'])}d)")

    ax2.axvline(deadline, color="red", linestyle="--", alpha=0.7,
                label=f"Deadline ({deadline}d)")
    ax2.set_xlabel("Project Duration (working days)")
    ax2.set_ylabel("Total Cost (Billion Rp)")
    ax2.set_title("Total Cost (incl. Penalty/Bonus) vs. Duration")
    ax2.legend(fontsize=9, loc="upper right")
    ax2.grid(True, alpha=0.3)

    plt.tight_layout()
    path = os.path.join(OUT_DIR, "time_cost_curve.png")
    plt.savefig(path, dpi=150)
    plt.close()
    print(f"  Saved: {path}")

def plot_sensitivity(sens_df: pd.DataFrame, base_cost: float):
    """Tornado diagram."""
    if sens_df.empty:
        return
    fig, ax = plt.subplots(figsize=(12, 6))
    sens_df = sens_df.sort_values("delta", key=abs, ascending=True)
    colors = ["#e74c3c" if d > 0 else "#27ae60" for d in sens_df["delta"]]
    ax.barh(sens_df["parameter"], sens_df["delta"] / 1e9, color=colors)
    ax.set_xlabel("Change in Total Cost (Billion Rp)")
    ax.set_title("Sensitivity Analysis – Tornado Diagram")
    ax.axvline(0, color="black", linewidth=0.8)
    ax.grid(True, axis="x", alpha=0.3)
    plt.tight_layout()
    path = os.path.join(OUT_DIR, "sensitivity_tornado.png")
    plt.savefig(path, dpi=150)
    plt.close()
    print(f"  Saved: {path}")

def plot_gantt_comparison(tasks: Dict[int, Task],
                          baseline_durs: Dict[int, int],
                          crashed_durs: Dict[int, int],
                          crashed_starts: Dict[int, float],
                          critical_ids: List[int]):
    """Gantt chart comparing baseline vs crashed schedules."""
    # sort by baseline early start
    tids = sorted(tasks.keys(), key=lambda x: tasks[x].es, reverse=True)
    # limit to critical + near-critical for readability
    show_ids = [tid for tid in tids if tasks[tid].total_float <= 5]
    if len(show_ids) < 15:
        show_ids = tids[:40]

    fig, ax = plt.subplots(figsize=(18, max(8, len(show_ids) * 0.35)))
    y_pos = list(range(len(show_ids)))
    labels = [f"[{tid}] {tasks[tid].name[:40]}" for tid in show_ids]

    for i, tid in enumerate(show_ids):
        t = tasks[tid]
        # baseline
        ax.barh(i + 0.15, baseline_durs[tid], left=t.es, height=0.3,
                color="#3498db", alpha=0.6, label="Baseline" if i == 0 else "")
        # crashed
        cs = crashed_starts.get(tid, t.es)
        cd = crashed_durs.get(tid, t.duration_days)
        color = "#e74c3c" if cd < baseline_durs[tid] else "#2ecc71"
        ax.barh(i - 0.15, cd, left=cs, height=0.3,
                color=color, alpha=0.8,
                label="Crashed" if i == 0 else "")

    ax.set_yticks(y_pos)
    ax.set_yticklabels(labels, fontsize=7)
    ax.set_xlabel("Working Days from Project Start")
    ax.set_title("Gantt Chart – Baseline vs. Crashed Schedule")
    ax.legend(loc="lower right")
    ax.grid(True, axis="x", alpha=0.3)
    plt.tight_layout()
    path = os.path.join(OUT_DIR, "gantt_comparison.png")
    plt.savefig(path, dpi=150)
    plt.close()
    print(f"  Saved: {path}")

def plot_crashed_activities(tasks: Dict[int, Task],
                            baseline_durs: Dict[int, int],
                            crashed_durs: Dict[int, int]):
    """Bar chart showing which activities were crashed and by how much."""
    crashed = [(tid, baseline_durs[tid] - crashed_durs[tid])
               for tid in tasks if crashed_durs.get(tid, baseline_durs[tid]) < baseline_durs[tid]]
    if not crashed:
        print("  No activities were crashed.")
        return
    crashed.sort(key=lambda x: x[1], reverse=True)

    tids_c = [c[0] for c in crashed[:30]]
    reductions = [c[1] for c in crashed[:30]]
    labels = [f"[{tid}] {tasks[tid].name[:35]}" for tid in tids_c]

    fig, ax = plt.subplots(figsize=(14, max(6, len(labels) * 0.35)))
    colors = plt.cm.Reds(np.linspace(0.3, 0.9, len(labels)))
    ax.barh(range(len(labels)), reductions, color=colors)
    ax.set_yticks(range(len(labels)))
    ax.set_yticklabels(labels, fontsize=8)
    ax.set_xlabel("Days Reduced")
    ax.set_title("Most Crashed Activities")
    ax.invert_yaxis()
    ax.grid(True, axis="x", alpha=0.3)
    plt.tight_layout()
    path = os.path.join(OUT_DIR, "crashed_activities.png")
    plt.savefig(path, dpi=150)
    plt.close()
    print(f"  Saved: {path}")

# ╔══════════════════════════════════════════════════════════════╗
# ║                        MAIN                                ║
# ╚══════════════════════════════════════════════════════════════╝

def fmt_rp(val):
    """Format Rupiah value."""
    if abs(val) >= 1e9:
        return f"Rp {val/1e9:,.2f} B"
    elif abs(val) >= 1e6:
        return f"Rp {val/1e6:,.1f} M"
    else:
        return f"Rp {val:,.0f}"

def main():
    print("=" * 70)
    print("  PROJECT CRASHING OPTIMISATION – COMMERCIAL CONSTRUCTION")
    print("=" * 70)

    # ── 1. Load data ──
    print("\n[1] LOADING DATA...")
    tasks, resources = load_data()

    # ── 2. Baseline CPM ──
    print("\n[2] BASELINE CPM ANALYSIS...")
    baseline_durs = {tid: t.duration_days for tid, t in tasks.items()}
    baseline_dur = run_cpm(tasks, baseline_durs)
    critical_ids = get_critical_path(tasks)
    baseline_cost = compute_baseline_cost(tasks)

    # Deadline = baseline duration (as per approved plan)
    deadline = baseline_dur

    print(f"  Baseline duration  : {baseline_dur} working days")
    print(f"  Baseline cost      : {fmt_rp(baseline_cost)}")
    print(f"  Contractual deadline: {deadline} working days")
    print(f"  Critical path tasks : {len(critical_ids)}")
    print(f"  Critical path IDs  : {critical_ids[:20]}{'...' if len(critical_ids)>20 else ''}")
    print(f"\n  Critical path activities:")
    for tid in critical_ids:
        t = tasks[tid]
        cp_flag = "★" if t.total_float == 0 else " "
        print(f"    {cp_flag} [{tid:3d}] {t.name[:50]:<50s}  "
              f"Dur={t.duration_days:3d}d  ES={t.es:3d}  EF={t.ef:3d}  "
              f"Float={t.total_float:2d}")

    # ── 3. Crash point (all crashed) ──
    print("\n[3] CRASH POINT ANALYSIS...")
    tasks_tmp = copy.deepcopy(tasks)
    crash_durs_all = {tid: t.crash_duration for tid, t in tasks_tmp.items()}
    crash_dur_min = run_cpm(tasks_tmp, crash_durs_all)
    crash_cost_all = sum(
        crash_cost_func(tasks[tid].normal_cost_rp, tasks[tid].duration_days, d)
        for tid, d in crash_durs_all.items()
    )
    print(f"  Maximum crash duration: {crash_dur_min} working days")
    print(f"  Full crash cost       : {fmt_rp(crash_cost_all)}")
    print(f"  Duration reduction    : {baseline_dur - crash_dur_min} days "
          f"({(baseline_dur-crash_dur_min)/baseline_dur*100:.1f}%)")

    # ── 4. Scenario A – Deadline-Driven LP ──
    print("\n[4] SCENARIO A – DEADLINE-DRIVEN OPTIMISATION (LP)...")
    print(f"  Minimising total cost with deadline = {deadline} days")
    lp_sol = solve_lp(tasks, deadline)
    if lp_sol:
        print(f"  LP Result:")
        print(f"    Project duration : {lp_sol['project_duration']} days")
        print(f"    Direct cost      : {fmt_rp(lp_sol['crash_cost'])}")
        print(f"    Extra crash cost : {fmt_rp(lp_sol['extra_crash_cost'])}")
        print(f"    Penalty          : {fmt_rp(lp_sol['penalty'])}")
        print(f"    Bonus            : {fmt_rp(lp_sol['bonus'])}")
        print(f"    Total cost       : {fmt_rp(lp_sol['total_cost'])}")

        # show crashed activities
        crashed_ids = [tid for tid in tasks
                       if lp_sol["durations"][tid] < baseline_durs[tid]]
        if crashed_ids:
            print(f"\n  Crashed activities ({len(crashed_ids)}):")
            for tid in sorted(crashed_ids,
                              key=lambda x: baseline_durs[x] - lp_sol["durations"][x],
                              reverse=True)[:20]:
                orig = baseline_durs[tid]
                new = lp_sol["durations"][tid]
                nc = tasks[tid].normal_cost_rp
                cc = crash_cost_func(nc, orig, new)
                print(f"    [{tid:3d}] {tasks[tid].name[:45]:<45s}  "
                      f"{orig:3d}d → {new:3d}d  (-{orig-new}d)  "
                      f"Cost: {fmt_rp(nc)} → {fmt_rp(cc)}")
    else:
        print("  LP solver returned no solution.")

    # ── 5. Scenario B – Budget-Constrained (solve at various budgets) ──
    print("\n[5] SCENARIO B – BUDGET-CONSTRAINED ANALYSIS...")
    budgets_rp = [0.5e9, 1e9, 2e9, 5e9, 10e9]
    print(f"  {'Budget':>15s}  {'Min Duration':>14s}  {'Savings':>10s}")
    print(f"  {'-'*15}  {'-'*14}  {'-'*10}")
    for budget in budgets_rp:
        # find minimum duration achievable within budget
        best_dur = baseline_dur
        for td in range(crash_dur_min, baseline_dur + 1):
            sol = solve_lp(tasks, deadline, target_duration=td)
            if sol and sol["extra_crash_cost"] <= budget:
                best_dur = sol["project_duration"]
                break
        savings = baseline_dur - best_dur
        print(f"  {fmt_rp(budget):>15s}  {best_dur:>10d} days  {savings:>6d} days")

    # ── 6. Genetic Algorithm ──
    print("\n[6] GENETIC ALGORITHM OPTIMISATION...")
    ga = GeneticAlgorithm(tasks, deadline, seed=42)
    ga_sol = ga.run(verbose=True)
    print(f"\n  GA Result:")
    print(f"    Project duration : {ga_sol['project_duration']} days")
    print(f"    Direct cost      : {fmt_rp(ga_sol['crash_cost'])}")
    print(f"    Extra crash cost : {fmt_rp(ga_sol['extra_crash_cost'])}")
    print(f"    Penalty          : {fmt_rp(ga_sol['penalty'])}")
    print(f"    Bonus            : {fmt_rp(ga_sol['bonus'])}")
    print(f"    Total cost       : {fmt_rp(ga_sol['total_cost'])}")

    # ── 7. Time-Cost Tradeoff Curve ──
    print("\n[7] TIME-COST TRADEOFF CURVE...")
    curve_df = generate_time_cost_curve(tasks, baseline_dur, deadline, n_points=30)

    if not curve_df.empty:
        opt_row = curve_df.loc[curve_df["total_cost"].idxmin()]
        print(f"\n  Optimal point on curve:")
        print(f"    Duration : {int(opt_row['actual_duration'])} days")
        print(f"    Total cost: {fmt_rp(opt_row['total_cost'])}")

        curve_df.to_csv(os.path.join(OUT_DIR, "time_cost_curve.csv"), index=False)
        plot_time_cost_curve(curve_df, deadline, baseline_dur, baseline_cost)

    # ── 8. Sensitivity Analysis ──
    print("\n[8] SENSITIVITY ANALYSIS...")
    sens_df = sensitivity_analysis(tasks, deadline, baseline_dur)
    if not sens_df.empty:
        print(f"\n  {'Parameter':<25s}  {'Total Cost':>18s}  {'Delta':>18s}")
        print(f"  {'-'*25}  {'-'*18}  {'-'*18}")
        for _, row in sens_df.iterrows():
            print(f"  {row['parameter']:<25s}  {fmt_rp(row['total_cost']):>18s}  "
                  f"{'+' if row['delta']>=0 else ''}{fmt_rp(row['delta']):>17s}")
        sens_df.to_csv(os.path.join(OUT_DIR, "sensitivity.csv"), index=False)
        plot_sensitivity(sens_df, lp_sol["total_cost"] if lp_sol else baseline_cost)

    # ── 9. Visualisations ──
    print("\n[9] GENERATING VISUALISATIONS...")
    # prefer LP solution, fall back to GA
    viz_sol = lp_sol or ga_sol
    if viz_sol:
        viz_starts = viz_sol.get("starts", {tid: tasks[tid].es for tid in tasks})
        plot_gantt_comparison(tasks, baseline_durs, viz_sol["durations"],
                              viz_starts, critical_ids)
        plot_crashed_activities(tasks, baseline_durs, viz_sol["durations"])

    # ── 10. Summary & Recommendations ──
    print("\n" + "=" * 70)
    print("  SUMMARY & RECOMMENDATIONS")
    print("=" * 70)
    print(f"""
  ┌─────────────────────────────────────────────────────────────────┐
  │  BASELINE                                                      │
  │    Duration : {baseline_dur} working days                              │
  │    Cost     : {fmt_rp(baseline_cost):<46s}   │
  │    Deadline : {deadline} working days                              │
  ├─────────────────────────────────────────────────────────────────┤
  │  CRASH POINT (maximum acceleration)                            │
  │    Duration : {crash_dur_min} working days                              │
  │    Cost     : {fmt_rp(crash_cost_all):<46s}   │
  ├─────────────────────────────────────────────────────────────────┤""")

    if lp_sol:
        print(f"""  │  LP OPTIMAL SOLUTION                                          │
  │    Duration : {lp_sol['project_duration']} working days{' '*(31-len(str(lp_sol['project_duration'])))}│
  │    Cost     : {fmt_rp(lp_sol['total_cost']):<46s}   │""")
    if ga_sol:
        print(f"""  │  GA OPTIMAL SOLUTION                                          │
  │    Duration : {ga_sol['project_duration']} working days{' '*(31-len(str(ga_sol['project_duration'])))}│
  │    Cost     : {fmt_rp(ga_sol['total_cost']):<46s}   │""")

    print(f"  └─────────────────────────────────────────────────────────────────┘")

    if not curve_df.empty:
        opt = curve_df.loc[curve_df["total_cost"].idxmin()]
        print(f"""
  RECOMMENDATION:
    The optimal project duration is {int(opt['actual_duration'])} working days.
    This achieves a total cost of {fmt_rp(opt['total_cost'])}.
    Compared to keeping the baseline ({baseline_dur} days), this represents
    a schedule reduction of {baseline_dur - int(opt['actual_duration'])} days and
    earns a bonus of {fmt_rp(opt['bonus'])} for early completion.

  KEY INSIGHTS:
    • Crashing beyond the optimal point yields diminishing returns.
    • The cost escalation follows a power-law with α = {COST_EXPONENT}.
    • Activities on the critical path yield the most benefit from crashing.
    • See output/ folder for all plots and detailed CSV data.
""")

    print(f"\n  All outputs saved to: {OUT_DIR}")
    print("=" * 70)


if __name__ == "__main__":
    main()
