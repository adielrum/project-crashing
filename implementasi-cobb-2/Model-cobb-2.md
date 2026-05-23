# V2 Formulation Blueprint — Project Crashing with Overcrowding + Overtime

## 0) Scope and modeling stance

This V2 is a **time-indexed resource-constrained crashing model** with two acceleration levers:
1. additional crews/resources (overcrowding),
2. overtime.

It is designed for immediate coding handoff and supports Scenario A/B/C from the problem statement.

---

## 1) Sets, indices, parameters, variables

## 1.1 Sets and indices
- $i,j \in V$: activities (including dummy start $0$ and dummy end $n$).
- $k \in K$: renewable resource types (crew/trade/equipment categories).
- $t \in \mathcal{T}=\{1,\dots,H\}$: discrete time periods (days).
- $E_{FS},E_{SS},E_{FF}$: precedence arc sets with lag.

## 1.2 Parameters
- $\delta^{FS}_{ij},\delta^{SS}_{ij},\delta^{FF}_{ij}$: lags (days).
- $R^{reg}_{k,t}$: regular-hour capacity of resource $k$ on day $t$.
- $R^{ot}_{k,t}$: max overtime-hour capacity of resource $k$ on day $t$.
- $\Omega_i$: required work content of activity $i$ (work units).
- $A_i$: baseline productivity scale for activity $i$.
- $\alpha_{i,k}\in(0,1)$: resource elasticity in activity $i$.
- $\beta_i\in(0,1)$: overtime effectiveness elasticity for activity $i$.
- $\eta_k\in(0,1]$: overtime efficiency multiplier (fatigue-adjusted).
- $r_k, r'_k$: regular and overtime wage (Rp/hour), with $r'_k\ge r_k$.
- $\bar u_{i,k,t}$: max regular hours assignable to $(i,k,t)$.
- $\bar o_{i,k,t}$: max overtime hours assignable to $(i,k,t)$.
- $\bar x_{i,k}\ge 1$: max crowding multiplier (activity-resource specific).
- $\underline d_i,\bar d_i$: min/max feasible duration of activity $i$ (optional hard bounds).
- $T^d$: contractual deadline (day).
- $c^{late}, c^{early}$: late penalty / early benefit (Rp/day).
- $c^{ind}$: indirect daily project overhead (Rp/day).
- $M$: big-$M$ constant.

## 1.3 Decision variables
- $y_{i,t}\in\{0,1\}$: activity $i$ active on day $t$.
- $u_{i,k,t}\ge0$: regular hours of resource $k$ assigned to activity $i$ at day $t$.
- $o_{i,k,t}\ge0$: overtime hours of resource $k$ assigned to activity $i$ at day $t$.
- $S_i,F_i\ge0$: start/finish time of activity $i$.
- $d_i\ge0$: duration of activity $i$.
- $T\ge0$: project completion time.
- $L,E\ge0$: lateness and earliness days.

Optional helper variables for crowding interpretation:
- $x_{i,k,t}\ge1$: crowding multiplier s.t. $u_{i,k,t}=u^{base}_{i,k,t}x_{i,k,t}$ (if baseline profile exists).

---

## 2) Objective and constraint blocks

## 2.1 Objective (base single-objective)
$$
\min Z = \sum_{i,k,t}\left(r_k u_{i,k,t}+r'_k o_{i,k,t}\right)
+ c^{ind}T + c^{late}L - c^{early}E + \sum_i \psi_i,
$$
where $\psi_i$ is optional convex safety/quality risk penalty (e.g., high crowding/overtime).

For Scenario B (budget-constrained): replace objective by $\min T$ and add $Z\le B_{max}$.

---

## 2.2 Activity execution logic and timing

**Duration from active periods**
$$
d_i = \sum_{t\in\mathcal T} y_{i,t},\quad \underline d_i \le d_i \le \bar d_i \quad (\text{if used}).
$$

**Start/finish linking (tight linear form)**
$$
S_i \le t + M(1-y_{i,t}),\quad \forall i,t,
$$
$$
F_i \ge t\,y_{i,t},\quad \forall i,t,
$$
$$
F_i \ge S_i + d_i.
$$
(Equivalent alternative linking forms are acceptable in code.)

**Contiguity (non-preemptive, optional but recommended):**
Introduce start indicator $z_{i,t}\in\{0,1\}$ and enforce one start plus run-length; or use standard consecutive-ones constraints.

---

## 2.3 Precedence constraints

$$
S_j \ge F_i + \delta^{FS}_{ij},\quad \forall (i,j)\in E_{FS},
$$
$$
S_j \ge S_i + \delta^{SS}_{ij},\quad \forall (i,j)\in E_{SS},
$$
$$
F_j \ge F_i + \delta^{FF}_{ij},\quad \forall (i,j)\in E_{FF}.
$$

Project finish:
$$
T \ge F_i,\ \forall i\in V_{end} \quad (\text{or } T=F_n \text{ with dummy end}).
$$

---

## 2.4 Resource capacity by time/calendar

$$
\sum_i u_{i,k,t} \le R^{reg}_{k,t},\quad \forall k,t,
$$
$$
\sum_i o_{i,k,t} \le R^{ot}_{k,t},\quad \forall k,t.
$$

Assignment only when active:
$$
0\le u_{i,k,t}\le \bar u_{i,k,t}y_{i,t},\quad
0\le o_{i,k,t}\le \bar o_{i,k,t}y_{i,t},\quad \forall i,k,t.
$$

Crowding bound (if baseline per-day hours $u^{base}_{i,k,t}$ available):
$$
u_{i,k,t} \le \bar x_{i,k}\,u^{base}_{i,k,t}y_{i,t}.
$$

---

## 2.5 Work completion with diminishing returns (Cobb–Douglas core)

Daily effective production:
$$
q_{i,t} = A_i\Bigg(\prod_{k\in K_i} u_{i,k,t}^{\alpha_{i,k}}\Bigg)
\cdot \left(\sum_{k\in K_i}\eta_k o_{i,k,t}\right)^{\beta_i},
$$
with diminishing returns condition
$$
\sum_{k\in K_i}\alpha_{i,k} + \beta_i \le 1.
$$

Completion requirement:
$$
\sum_{t\in\mathcal T} q_{i,t} \ge \Omega_i,\quad \forall i\in V\setminus\{0,n\}.
$$

> Note: This block is nonlinear (MINLP). For MILP, use piecewise-linear outer approximation (Section 5).

---

## 2.6 Earliness/lateness linearization

$$
T - T^d = L - E,
$$
$$
L\ge0,\ E\ge0.
$$

This supports symmetric/asymmetric economics directly in objective.

---

## 2.7 Optional safety/quality and uncertainty hooks

**Rolling overtime fatigue cap** (example):
$$
\sum_{\tau=t-W+1}^{t} o_{i,k,\tau} \le \Gamma_{i,k},\quad \forall i,k,t.
$$

**Quality-risk budget** (example):
$$
\sum_i \psi_i(u,o) \le \Psi^{max}
$$
or keep $\psi_i$ in objective.

**Uncertainty-ready hook**
- Scenario index $\omega\in\Omega$ for weather/supply productivity shocks, replace $A_i\to A_i^{\omega}$ and optimize expected cost or robust worst-case.

---

## 3) What changed from the original model

| Original model element | V2 replacement | Why better |
|---|---|---|
| Activity duration constrained per $(i,k)$ with max-like effect | Activity completion via aggregate production $\sum_t q_{i,t}\ge\Omega_i$ | Captures **joint crew production** instead of inconsistent per-resource lower bounds |
| No explicit time-indexed resource feasibility | $\sum_i u_{i,k,t}\le R^{reg}_{k,t}$ and $\sum_i o_{i,k,t}\le R^{ot}_{k,t}$ | Prevents infeasible simultaneous crashing; calendar-aware |
| Overtime/crowding cost mixed multiplicatively in one term | Explicit labor-hour costing $r u + r' o$ + optional risk penalty | Correct units, avoids double counting, easier calibration |
| Implicit activity execution from $s_i,f_i$ only | Binary activity-time logic $y_{i,t}$ + linking to $S_i,F_i,d_i$ | Implementation-ready for RCPSP-style solvers |
| Cobb–Douglas tied to transformed duration formula | Cobb–Douglas tied to **daily production** $q_{i,t}$ | More physically interpretable and extensible |
| Early/late logic present but tied to $f_n$ only | Keeps linear split $T-T^d=L-E$ with explicit $T$ | Works with or without dummy end; cleaner for scenario variants |
| No direct safety/fatigue constraints | Rolling overtime cap / risk budget hooks | Supports operational realism and policy constraints |
| No uncertainty structure | Scenario/robust extension hooks | Enables robustness against weather/supply disruption |

---

## 4) Practical implementation note

## 4.1 MILP approximation path (default implementation path)

Use MILP first for reliability and speed:
1. Approximate nonlinear production $q_{i,t}=f(u,o)$ by **piecewise linear envelopes** (SOS2 or lambda formulation).
2. Keep all precedence, capacity, earliness/lateness, and binary activity-time logic linear.
3. Solve Scenario A/B/C repeatedly to build time-cost frontier.

Use this when project size is medium/large and fast, auditable solutions are needed.

## 4.2 When to use MINLP

Use MINLP when:
- high-fidelity nonlinear productivity is critical,
- instance size is moderate,
- computational budget is higher,
- calibration confidence in Cobb–Douglas parameters is good.

If MINLP is unstable, revert to MILP with finer PWL segments.

## 4.3 Data needed for calibration

Minimum data package:
1. Activity network + FS/SS/FF lags.
2. Resource calendars $R^{reg}_{k,t},R^{ot}_{k,t}$.
3. Baseline per-activity work content $\Omega_i$ (or reconstruct from as-built logs).
4. Historical productivity to fit $A_i,\alpha_{i,k},\beta_i,\eta_k$ by activity class.
5. Wage rates (regular/overtime), indirect cost/day, penalty and early revenue rates.
6. Practical caps: $\bar x_{i,k},\bar o_{i,k,t},\Gamma_{i,k}$, and min/max duration bounds.

---

## 5) Coding handoff checklist (short)

- Implement V2 as `Pyomo` model with switch: `mode = MILP_PWL | MINLP`.
- Start with FS-only precedence, then enable SS/FF once baseline verified.
- Validate baseline (no crashing) reproduces current schedule/cost before optimization.
- Add automated infeasibility diagnostics (resource overload, precedence cycle, impossible deadline).
- Output: optimal schedule, critical activities, crash levers used, and time-cost curve points.
