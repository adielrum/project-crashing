# Mathematical Model: Project Crashing Optimization

This document outlines the mathematical formulation used to optimize the commercial construction schedule. The goal is to minimize the total project cost by balancing the direct costs of crashing (accelerating) activities against the indirect costs/benefits of time (penalties and bonuses).

---

## 1. Parameters and Variables

The model distinguishes between inputs derived from the schedule data and those defined by management assumptions.

### **1.1 Parameters (Constants)**

| Parameter | Symbol | Source | Description |
| :--- | :---: | :--- | :--- |
| **Normal Duration** | $d_{i,N}$ | Schedule Data | Base duration of activity $i$ (working days). |
| **Normal Cost** | $C_{i,N}$ | Resource Data | Base cost of activity $i$ calculated from resource hourly rates. |
| **Deadline** | $D$ | Contract | Contractual completion date (working days). |
| **Penalty Rate** | $P$ | Contract | Liquidated damages per day ($150,000,000$ Rp). |
| **Bonus Rate** | $B$ | Contract | Early completion revenue per day ($100,000,000$ Rp). |
| **Exchange Rate** | $ER$ | Assumption | Conversion from USD to IDR ($16,000$ Rp/$). |
| **Crash Limit Ratio** | $R$ | Assumption | Max percentage an activity can be crashed (default $50\%$). |
| **Min. Duration** | $d_{i,min}$ | Formula | $d_{i,N} \times (1 - R)$. The floor for acceleration. |
| **Cost Exponent** | $\alpha$ | Assumption | Power-law factor ($\alpha=1.2$) for non-linear crash costs. |

### **1.2 Decision Variables (Output)**

| Variable | Symbol | Description |
| :--- | :---: | :--- |
| **Start Time** | $S_i$ | The scheduled start day for activity $i$. |
| **Crash Amount** | $x_i$ | Days removed from task $i$'s normal duration ($0 \le x_i \le d_{i,N} - d_{i,min}$). |
| **Actual Duration** | $d_i$ | The resulting duration after crashing: $d_i = d_{i,N} - x_i$. |
| **Project Finish** | $T$ | The completion time of the entire project network. |

---

## 2. Objective Function

The objective is to **Minimize Total Project Cost ($Z$)**, which is the sum of activity costs and time-based financial impacts.

### **Total Cost Equation**
$$ \min Z = \sum_{i} C_i(d_i) + \text{Penalty}(T) - \text{Bonus}(T) $$

#### **Direct Activity Cost ($C_i$)**
The model assumes that crashing becomes exponentially more expensive as the duration nears the limit. This is modeled using a power-law function:
$$ C_i(d_i) = C_{i,N} \times \left( \frac{d_{i,N}}{d_i} \right)^\alpha $$

#### **Time-based Indirect Costs**
- **Penalty:** $P \times \max(0, T - D)$
- **Bonus:** $B \times \max(0, D - T)$

---

## 3. Constraints

### **3.1 Precedence Constraints**
Ensures that activities follow the logical sequence defined in the construction schedule.

- **Finish-to-Start (FS):** Activity $j$ cannot start until its predecessor $i$ finishes.
  $$ S_j \ge S_i + (d_{i,N} - x_i) + \text{lag}_{ij} $$
- **Finish-to-Finish (FF):** Activity $j$ cannot finish until $i$ finishes.
  $$ S_j + (d_{j,N} - x_j) \ge S_i + (d_{i,N} - x_i) + \text{lag}_{ij} $$
- **Start-to-Start (SS):** Activity $j$ cannot start until $i$ starts.
  $$ S_j \ge S_i + \text{lag}_{ij} $$

### **3.2 Crashing Bounds**
Physical limits on how much an activity can be accelerated.
$$ 0 \le x_i \le d_{i,N} - d_{i,min} $$

### **3.3 Project Completion**
$T$ is constrained by the finish time of all terminal tasks in the network.
$$ T \ge S_i + (d_{i,N} - x_i) \quad \forall i $$

---

## 4. Algorithms Used

The system uses three distinct methods to solve the model, providing both a rigorous mathematical optimum and a robust heuristic backup.

### **4.1 Critical Path Method (CPM)**
**Used for:** Baseline analysis.
- Calculates the earliest/latest starts and "float" for every task.
- Identifies the **Critical Path**: the sequence of tasks with zero float. Only tasks on this path are candidates for crashing to reduce project duration.

### **4.2 Linear Programming (LP) with Piecewise Approximation**
**Used for:** Finding the exact optimal solution within the defined bounds.
- Since the cost function $C_i(d_i)$ is non-linear, the LP solver (`PuLP`) uses a **Piecewise-Linear Approximation**.
- Each activity's cost curve is broken into $K=10$ linear segments. Each segment has an increasing "marginal cost per day of crashing." 
- Because the cost function is convex ($\alpha > 1$), the LP solver naturally picks the cheapest segments first.

### **4.3 Genetic Algorithm (GA)**
**Used for:** Handling complex, non-linear, or discrete cost scenarios.
- **Representation:** A chromosome is a vector of values $[0, 1]^n$, where each value represents the percentage of allowed crash used for task $i$.
- **Evolution:** Uses **Simulated Binary Crossover (SBX)** and **Polynomial Mutation** to explore the solution space.
- **Fitness:** The total cost ($Z$) calculated by running a full CPM pass for every individual in the population.
- **Benefit:** Can bypass local optima and doesn't require the cost function to be linear or differentiable.
