# Mathematical Model Formulation

This document describes the mathematical optimization model implemented in [run_pymoo.py](file:///Users/macintoshhd/Documents/Adiel/pemod/Pemod-3.0/project-crashing/implementasi-cobb/run_pymoo.py).

---

## 1. Decision Variables

The optimization problem optimizes the start times and the resources allocated to task-resource pairs. The decision variable vector $X$ of length $N + 2P$ (where $N$ is the number of tasks and $P$ is the number of task-resource assignments) is structured as:

1. **Start Times ($s_i$)**:
   - Start day of task $i$ from project start.
   - Represented by $X[0:N]$.
   - Bounded by:
     $$ 0.0 \le s_i \le 2 \cdot T_{\max} $$
     *(In the default run: $0.0 \le s_i \le 688.0$)*

2. **Labor Multiplier ($x_{i,k}$)**:
   - Multiplier for resource $k$ on task $i$, representing the factor by which the baseline crew is increased.
   - Represented by $X[N:N+P]$.
   - Bounded by:
     $$ x_{\min} \le x_{i,k} \le x_{\max} $$
     *(In the default run: $1.0 \le x_{i,k} \le 2.0$)*

3. **Daily Overtime ($\tau_{i,k}$)**:
   - Daily overtime hours worked by resource $k$ on task $i$.
   - Represented by $X[N+P:N+2P]$.
   - Bounded by:
     $$ \tau_{\min} \le \tau_{i,k} \le \tau_{\max} $$
     *(In the default run: $0.0 \le \tau_{i,k} \le 4.0$)*

---

## 2. Resource-Level Crash Duration (Cobb-Douglas)

The crashed duration $D_{i,k}$ (in days) for a specific assignment of resource $k$ to task $i$ is calculated using the Cobb-Douglas production function model:

$$ D_{i,k}(x_{i,k}, \tau_{i,k}) = D_{\text{base},i,k} \cdot \left(\frac{1}{x_{i,k}}\right)^\alpha \cdot \left(\frac{8}{8 + \tau_{i,k}}\right)^\beta $$

Where:
- $D_{\text{base},i,k}$: Baseline duration of the task-resource assignment (from the `D_base` column).
- $\alpha$: Crowding exponent governing productivity losses when more workers are assigned ($0.5$).
- $\beta$: Fatigue exponent governing productivity losses during overtime ($0.5$).
- $8$: Standard hours per working day.

---

## 3. Task-Level Duration

A task $i$ is complete only when all its assigned resources $k \in K_i$ have finished their work. The task duration $D_i$ is determined by the slowest resource:

$$ D_i = \max_{k \in K_i} D_{i,k}(x_{i,k}, \tau_{i,k}) $$

---

## 4. Project Completion Time (Makespan)

The total project completion time (makespan) is the finish time of the last task, where $f_i = s_i + D_i$ is the finish time of task $i$:

$$ T_{\text{finish}} = \max_{i=0..N-1} (s_i + D_i) $$

---

## 5. Objective Function

The objective is to minimize the total project cost $F$, defined as:

$$ \text{Minimize} \quad F = \text{Labor Cost} + \text{Penalty} - \text{Bonus} + \text{Precedence Penalty} $$

Where:

1. **Labor Cost**:
   $$ \text{Labor Cost} = \sum_{p=0}^{P-1} D_{i,k} \cdot x_{i,k} \cdot U_{i,k} \cdot (8 r_k + \tau_{i,k} r'_k) $$
   - $U_{i,k}$: Baseline resource allocation percentage (from the `U_ik` column).
   - $r_k$: Standard hourly wage rate of resource $k$ in Million Rupiah per hour:
     $$ r_k = \frac{\text{r\_k\_usd}_k \cdot \text{exchange\_rate}}{10^6} $$
   - $r'_k$: Overtime hourly wage rate of resource $k$:
     $$ r'_k = r_k \cdot \text{overtime\_mult} $$
   - $8$: Standard hours per day (`hours_per_day`).

2. **Late Penalty**:
   $$ \text{Penalty} = c_{\text{late}} \cdot \max(0.0, T_{\text{finish}} - T_{\max}) $$
   - $c_{\text{late}}$: Late penalty per day ($150.0$ M Rp/day).
   - $T_{\max}$: Target project deadline ($344$ days).

3. **Early Bonus**:
   $$ \text{Bonus} = c_{\text{early}} \cdot \max(0.0, T_{\max} - T_{\text{finish}}) $$
   - $c_{\text{early}}$: Early completion bonus per day ($100.0$ M Rp/day).

4. **Precedence Penalty**:
   $$ \text{Precedence Penalty} = \text{weight} \cdot \sum_{(j,i) \in E} \max(0.0, \text{violation}_{j,i}) $$
   - $\text{weight}$: Precedence penalty weight coefficient ($10^5$).
   - $\text{violation}_{j,i}$: The amount of precedence violation imposed by predecessor $j$ on successor $i$ based on dependency type:
     - **Finish-to-Start (FS)**:
       $$ \text{violation}_{j,i} = s_j + D_j + \text{lag}_{j,i} - s_i $$
     - **Start-to-Start (SS)**:
       $$ \text{violation}_{j,i} = s_j + \text{lag}_{j,i} - s_i $$
     - **Finish-to-Finish (FF)**:
       $$ \text{violation}_{j,i} = s_j + D_j + \text{lag}_{j,i} - s_i - D_i $$
