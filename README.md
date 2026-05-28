# Project Crashing Optimizer

Resource-Constrained Project Crashing Optimizer for commercial construction scheduling. Solves the **Dynamic Resource-Constrained Project Scheduling Problem with Time-Cost Trade-offs (RCPSP-TCT)** using multiple optimization approaches.

## Problem Statement

A mid-sized commercial office building is under construction. The developer faces:

- **Late delivery penalty:** Rp 150,000,000/day
- **Early delivery bonus:** Rp 100,000,000/day

Due to weather disruptions and supply chain delays, the project is behind schedule. The optimizer determines which activities to accelerate ("crash") and by how much, minimizing total cost while meeting the contractual deadline.

## Key Features

- **Multiple Solver Approaches** - CP-SAT, MILP, Genetic Algorithm, Pyomo MILP/MINLP
- **Dynamic Re-scheduling** - Locks completed/in-progress tasks, re-optimizes remaining activities
- **Cobb-Douglas Production Function** - Models diminishing returns from overcrowding and overtime
- **Time-Cost Trade-off Analysis** - Generates curves showing duration vs. crashing cost
- **Interactive Web UI** - Flask-based interface with real-time Plotly visualizations
- **Resource Capacity Constraints** - Enforces daily resource availability limits

## Mathematical Models

| Model | Description | Solver |
|-------|-------------|--------|
| **Baseline (Scenario 1)** | Linear crash cost per day, cumulative resource constraints | CP-SAT (OR-Tools) |
| **Cobb-Douglas (Scenario 2)** | Nonlinear duration/cost via production function, overcrowding (x) and overtime (tau) variables | GA (pymoo) |
| **Hybrid (Scenario 3)** | Cobb-Douglas preprocessing to derive d_min and crash slopes, then CP-SAT for fast solving | CP-SAT |

Full mathematical formulations are in `docs/Model_Baseline.md`, `docs/Model_CD.md`, and `docs/Model_Hybrid.md`.

## Prerequisites

- Python 3.11+

## Installation

```bash
pip install flask ortools pulp pymoo pyomo numpy scipy pandas matplotlib plotly openpyxl
```

## Quick Start

### Web Application (Recommended)

```bash
cd webapp
python webapp.py
# Open http://127.0.0.1:5001
```

The web UI provides:
- Sidebar for parameter tuning (Cobb-Douglas params, cost params, solver selection)
- Tabbed views: Summary, Original Gantt, Optimized Gantt, Trade-off, Crash Plan, Resource Load

### CP-SAT Solver (CLI)

```bash
python solve_project_crashing.py \
    --target-end-date 243 \
    --current-day 20 \
    --output-json outputs/solution.json \
    --output-csv outputs/schedule.csv
```

### V2/V3 Optimizer (Interactive CLI)

```bash
python project_optimizer_v2.py   # MILP + GA without resource capacity
python project_optimizer_v3.py   # MILP + GA with resource capacity
```

Both prompt for `current_day` and `target_day` interactively.

## Project Structure

```
project-crashing/
├── webapp/                       # Main Web Application directory
│   ├── webapp.py                 # Flask web UI (primary entry point)
│   ├── optimizer_core.py         # Shared: data classes, Cobb-Douglas math, GA solver, Plotly vis
│   ├── solver_milp.py            # MILP solver via PuLP+CBC
│   ├── templates/index.html      # Jinja2 template for web UI
│   ├── static/
│   │   ├── css/style.css
│   │   └── js/main.js
│   └── Schedules_CSV/            # CSV exports from MS Project (web data source)
│
├── solve_project_crashing.py     # OR-Tools CP-SAT solver (standalone CLI)
├── project_optimizer.py          # V1: LP + scipy optimizer
├── project_optimizer_v2.py       # V2: MILP + GA without resource capacity
├── project_optimizer_v3.py       # V3: MILP + GA with resource capacity
├── gantt_chart.py                # Static Gantt chart generator (matplotlib)
├── update_rates.py               # Utility to update resource wage rates
│
├── data/                         # Schedule data (JSON)
│   ├── activity_data_v3.json
│   ├── resource_capacity_v3.json
│   ├── resource_requirements_v3.json
│   └── original-data/            # Raw data from Excel
│
├── Schedules_CSV/                # CSV exports from MS Project
│
├── output/                       # V1/V2/V3 results
├── outputs/                      # CP-SAT solver results
│
├── implementasi-cobb/            # Cobb-Douglas GA implementation (pymoo)
├── implementasi-cobb-2/          # Cobb-Douglas Pyomo MILP/MINLP
│
└── docs/                         # Mathematical formulations and reports
    ├── Model_Baseline.md
    ├── Model_CD.md
    ├── Model_Hybrid.md
    └── Laporan.typ / Laporan.pdf
```

## Data Format

### activity_data_v3.json

```json
{
  "activities": {
    "1": {
      "name": "Activity Name",
      "normal_time": 30,
      "min_time": 20,
      "crash_cost_per_day": 5000000,
      "predecessors": ["0"]
    }
  }
}
```

### resource_capacity_v3.json

```json
{
  "resources": {
    "1": { "name": "Structural Workers", "capacity": 20 },
    "2": { "name": "Electricians", "capacity": 10 }
  }
}
```

### resource_requirements_v3.json

```json
{
  "assignments": [
    { "activity_id": "1", "resource_id": "1", "daily_demand": 8 }
  ]
}
```

## Output Examples

The optimizer generates:

- **Gantt Charts** - Interactive Plotly HTML or static matplotlib PNG/PDF
- **Resource Load Charts** - Daily resource utilization over time
- **Trade-off Curves** - Project duration vs. total cost (crash cost + penalties)
- **Crash Plans** - Detailed table of which activities to crash and by how much
- **Solution JSON** - Complete optimization results with schedules and metrics

## Configuration

The webapp uses these defaults (defined in `optimizer_core.py`):

| Parameter | Default | Description |
|-----------|---------|-------------|
| `alpha` | 0.3 | Cobb-Douglas overcrowding exponent |
| `beta` | 0.4 | Cobb-Douglas overtime exponent |
| `x_max` | 2.0 | Maximum overcrowding multiplier |
| `tau_max` | 2.0 | Maximum overtime hours/day |
| `ot_mult` | 1.5 | Overtime wage multiplier |
| `c_late` | 150000000 | Late delivery penalty (Rp/day) |
| `c_early` | 100000000 | Early delivery bonus (Rp/day) |

## Documentation

- `docs/Model_Baseline.md` - CP-SAT mathematical formulation (Indonesian)
- `docs/Model_CD.md` - Cobb-Douglas model formulation (Indonesian)
- `docs/Model_Hybrid.md` - Hybrid model formulation (Indonesian)
- `implementasi-cobb/model_formulation.md` - GA formulation (English)
- `implementasi-cobb-2/Model-cobb-2.md` - Pyomo MILP formulation blueprint
- `docs/Laporan.typ` / `docs/Laporan.pdf` - Full project report
