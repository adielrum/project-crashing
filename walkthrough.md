# Project Crashing Optimization – Walkthrough

## Overview

Built a complete mathematical optimization system for accelerating a 344-day commercial construction project. The model uses **resource-based dynamic cost calculation** (not flat lookup costs) and solves via both **Linear Programming** (PuLP) and a **Genetic Algorithm**.

---

## Mathematical Model

### Cost Model (Power-Law, Resource-Driven)

Instead of fixed crash costs per activity, costs are computed from actual resource data:

```
NormalCost_i = Σ (work_hours × hourly_rate × exchange_rate)
CrashCost_i(d) = NormalCost_i × (d_normal / d_actual)^α     where α = 1.2
```

- Resource rates from [Resource_Table.csv](file:///c:/Users/WINDOWS/Desktop/Projects/pemod/Schedules_CSV/Resource_Table.csv) ($50/hr × 16,000 = Rp 800,000/hr)
- Work hours from [Assignment_Table.csv](file:///c:/Users/WINDOWS/Desktop/Projects/pemod/Schedules_CSV/Assignment_Table.csv) (159 resource assignments)
- Power-law exponent α=1.2 models diminishing returns from overtime/overcrowding

### Objective Function

```
min Z = Σ CrashCost_i(d_i) + max(P×(T-D), -B×(D-T))
```

Where P = Rp 150M/day (penalty), B = Rp 100M/day (bonus), D = deadline

### Constraints

| Constraint | Formula |
|---|---|
| Duration bounds | d_i^crash ≤ d_i ≤ d_i^normal |
| Precedence (FS) | S_j ≥ S_i + d_i + lag |
| Precedence (FF) | S_j + d_j ≥ S_i + d_i + lag |
| Completion | T ≥ S_i + d_i ∀i |

---

## Key Results

| Metric | Value |
|---|---|
| **Baseline duration** | 344 working days |
| **Baseline cost** | Rp 6.34 B |
| **Crash point (max)** | 185 working days |
| **Full crash cost** | Rp 13.97 B |
| **LP optimal duration** | 185 days |
| **LP optimal total cost** | Rp -6.50 B (net profit due to bonus) |
| **GA optimal total cost** | ~Rp -5.26 B |

> [!IMPORTANT]
> The optimal strategy is to **crash fully to 185 days** because the early-completion bonus (Rp 100M/day × 159 days = Rp 15.9B) far exceeds the additional crash cost (Rp 3.1B). This makes intuitive sense: the bonus rate is higher than the marginal crash cost for most activities.

### Budget-Constrained Analysis (Scenario B)

| Budget | Min Duration | Days Saved |
|---|---|---|
| Rp 500M | 280 days | 64 days |
| Rp 1.0B | 245 days | 99 days |
| Rp 2.0B | 207 days | 137 days |
| Rp 5.0B | 185 days | 159 days |

---

## Generated Visualizations

### Time-Cost Tradeoff Curve

![Time-cost tradeoff curve showing direct cost and total cost (with penalty/bonus) vs. project duration. The optimal point is at 185 days.](C:/Users/WINDOWS/.gemini/antigravity/brain/7c884b3a-e754-41a5-9b29-9c5935bf3d22/time_cost_curve.png)

### Gantt Chart – Baseline vs. Crashed

![Gantt chart comparing the baseline schedule (blue) with the crashed schedule (red), showing which activities were shortened.](C:/Users/WINDOWS/.gemini/antigravity/brain/7c884b3a-e754-41a5-9b29-9c5935bf3d22/gantt_comparison.png)

### Most Crashed Activities

![Bar chart showing the activities with the largest duration reductions.](C:/Users/WINDOWS/.gemini/antigravity/brain/7c884b3a-e754-41a5-9b29-9c5935bf3d22/crashed_activities.png)

### Sensitivity Analysis

![Tornado diagram showing how total cost changes when varying penalty rate, bonus rate, crash limits, and cost exponent.](C:/Users/WINDOWS/.gemini/antigravity/brain/7c884b3a-e754-41a5-9b29-9c5935bf3d22/sensitivity_tornado.png)

**Key sensitivity findings:**
- **Bonus rate** has the strongest influence (±Rp 7.9B swing)
- **Crash limit** is second most impactful (reducing from 50% to 30% costs Rp 5.2B more)
- Penalty rate and cost exponent have moderate/minimal impact

---

## Files Modified/Created

| File | Description |
|---|---|
| [project_crashing.py](file:///c:/Users/WINDOWS/Desktop/Projects/pemod/project_crashing.py) | Main optimization script (~1080 lines) |
| [requirements.txt](file:///c:/Users/WINDOWS/Desktop/Projects/pemod/requirements.txt) | Python dependencies |
| [output/time_cost_curve.png](file:///c:/Users/WINDOWS/Desktop/Projects/pemod/output/time_cost_curve.png) | Time-cost tradeoff curve |
| [output/gantt_comparison.png](file:///c:/Users/WINDOWS/Desktop/Projects/pemod/output/gantt_comparison.png) | Baseline vs crashed Gantt |
| [output/crashed_activities.png](file:///c:/Users/WINDOWS/Desktop/Projects/pemod/output/crashed_activities.png) | Most-crashed activities chart |
| [output/sensitivity_tornado.png](file:///c:/Users/WINDOWS/Desktop/Projects/pemod/output/sensitivity_tornado.png) | Sensitivity tornado diagram |
| [output/time_cost_curve.csv](file:///c:/Users/WINDOWS/Desktop/Projects/pemod/output/time_cost_curve.csv) | Raw curve data (30 points) |
| [output/sensitivity.csv](file:///c:/Users/WINDOWS/Desktop/Projects/pemod/output/sensitivity.csv) | Sensitivity results |

## How to Run

```bash
python project_crashing.py
```

The script runs all analyses sequentially: CPM baseline → LP optimization → Budget analysis → GA optimization → Time-cost curve → Sensitivity analysis. Total runtime is ~10-15 minutes (GA is the bottleneck). All outputs are saved to the `output/` folder.
