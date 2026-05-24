import os
import json
from datetime import datetime, timedelta
import pyomo.environ as pyo

# ==============================================================================
# 0) CONFIGURATION (Keep these open for user inputs)
# ==============================================================================
CONFIG = {
    # Cobb-Douglas parameters
    "alpha": 0.6,        # Global resource elasticity sum (divided among task resources)
    "beta": 0.3,         # Overtime effectiveness elasticity
    "ot_mult": 1.5,      # Overtime wage multiplier (overtime_rate = ot_mult * standard_rate)
    "eta_val": 0.85,     # Overtime efficiency multiplier (fatigue adjusted)
    
    # Project economics
    "c_late": 5000.0,    # Lateness penalty (Rp or USD / day)
    "c_early": 2000.0,   # Earliness completion benefit (Rp or USD / day)
    "c_ind": 1000.0,     # Indirect daily project overhead cost (Rp or USD / day)
    "T_d": 480,          # Contractual project deadline (days from start)
    
    # Practical limits
    "x_grid": [1.0, 1.25, 1.5, 1.75, 2.0],  # Crowding multiplier levels
    "tau_grid": [0.0, 1.0, 2.0, 3.0, 4.0],  # Daily overtime levels (hours)
    
    # Optimization Scenario
    # 'A' - Time-Cost Tradeoff (Minimize Total Project Cost: Labor + Overhead + Penalties - Benefits)
    # 'B' - Budget-Constrained (Minimize Project Duration T, subject to Total Cost <= B_max)
    # 'C' - Deadline-Constrained (Minimize Total Project Cost, subject to T <= T_d)
    "scenario": "A",
    "B_max": 200000.0,   # Max budget for Scenario B
    
    # Solver Options
    "solver_name": "cbc",
    "time_limit": 180,   # Solver time limit in seconds
    "verbose": True
}

# ==============================================================================
# 1) DATA LOADING & PRE-PROCESSING
# ==============================================================================
WORKSPACE_DIR = "/Users/macintoshhd/Documents/Adiel/pemod/Pemod-3.0/project-crashing"
DATA_DIR = os.path.join(WORKSPACE_DIR, "data/original-data")

def load_data():
    with open(os.path.join(DATA_DIR, "task_table.json"), encoding="utf-8") as f:
        tasks = json.load(f)
    with open(os.path.join(DATA_DIR, "resource_table.json"), encoding="utf-8") as f:
        resources = json.load(f)
    with open(os.path.join(DATA_DIR, "assignment_table.json"), encoding="utf-8") as f:
        assignments = json.load(f)
    return tasks, resources, assignments

# Utility Parsers
def parse_duration(s):
    if not s:
        return 0
    s = str(s).lower().strip()
    if 'wk' in s:
        return int(s.replace('wks', '').replace('wk', '').strip()) * 5
    return int(s.replace('days', '').replace('day', '').strip())

def parse_work_hours(s):
    if not s:
        return 0.0
    s = str(s).lower().strip()
    if 'h' in s:
        s = s.replace('hrs', '').replace('hr', '').replace('h', '')
    try:
        return float(s.strip())
    except ValueError:
        return 0.0

def parse_rate(s):
    if not s:
        return 0.0
    s = str(s).lower().replace('$', '').replace('/h', '').strip()
    try:
        return float(s)
    except ValueError:
        return 0.0

def parse_units(s):
    if not s:
        return 0.0
    s = str(s).strip()
    if '%' in s:
        try:
            return float(s.replace('%', '').strip()) / 100.0
        except ValueError:
            pass
    try:
        return float(s)
    except ValueError:
        return 1.0

def parse_predecessors(predecessor_str):
    if not predecessor_str:
        return []
    relations = []
    parts = str(predecessor_str).split(',')
    for part in parts:
        part = part.strip()
        if not part:
            continue
        i = 0
        while i < len(part) and (part[i].isdigit() or part[i] == '-'):
            i += 1
        if i == 0:
            continue
        pred_id = int(part[:i])
        remaining = part[i:].upper().strip()
        rel_type = 'FS'
        lag = 0.0
        if remaining:
            for t in ['FS', 'SS', 'FF', 'SF']:
                if remaining.startswith(t):
                    rel_type = t
                    remaining = remaining[len(t):].strip()
                    break
            if remaining:
                remaining = remaining.replace('DAYS', '').replace('DAY', '').replace('D', '').strip()
                try:
                    lag = float(remaining)
                except ValueError:
                    pass
        relations.append((pred_id, rel_type, lag))
    return relations

# ==============================================================================
# 2) DIAGNOSTICS & TIME-WINDOW PREPROCESSING
# ==============================================================================
def process_project():
    raw_tasks, raw_resources, raw_assignments = load_data()
    
    # 1. Map name to ID
    name_to_task_id = {t['Name'].strip(): t['ID'] for t in raw_tasks if t.get('Name')}
    name_to_res_id = {r['Name'].strip(): r['ID'] for r in raw_resources if r.get('Name')}
    
    # 2. Identify outline level 2 tasks
    leaf_tasks_dict = {}
    for i, t in enumerate(raw_tasks):
        if int(t['Outline Level']) == 2:
            # Reconstruct tasks as clean dictionaries
            tid = int(t['ID'])
            leaf_tasks_dict[tid] = {
                'id': tid,
                'name': t['Name'],
                'duration_days': parse_duration(t['Duration']),
                'predecessors': parse_predecessors(t.get('Predecessors')),
                'start_str': t['Start'],
                'finish_str': t['Finish']
            }
            
    task_ids = sorted(list(leaf_tasks_dict.keys()))
    
    # Predecessor mapping (only referencing leaf tasks)
    predecessors_clean = {}
    successors_clean = {tid: [] for tid in task_ids}
    for tid in task_ids:
        preds = []
        for pid, rel_type, lag in leaf_tasks_dict[tid]['predecessors']:
            if pid in leaf_tasks_dict:
                preds.append((pid, rel_type, lag))
                successors_clean[pid].append(tid)
        predecessors_clean[tid] = preds

    # 3. Detect Cycles (Kahn's Algorithm)
    adj = {tid: [] for tid in task_ids}
    in_degree = {tid: 0 for tid in task_ids}
    for tid in task_ids:
        for pid, _, _ in predecessors_clean[tid]:
            adj[pid].append(tid)
            in_degree[tid] += 1
            
    queue = [tid for tid in task_ids if in_degree[tid] == 0]
    visited = 0
    while queue:
        u = queue.pop(0)
        visited += 1
        for v in adj[u]:
            in_degree[v] -= 1
            if in_degree[v] == 0:
                queue.append(v)
                
    if visited < len(task_ids):
        raise ValueError("Precedence Cycle Detected! The precedence relations form a directed loop.")
    print("Diagnostics: Precedence network is clean and acyclic.")

    # 4. Map Assignments to Resource IDs
    assignments_by_task = {tid: [] for tid in task_ids}
    for a in raw_assignments:
        tname = a['Task Name'].strip()
        rname = a['Resource Name'].strip()
        if tname in name_to_task_id and rname in name_to_res_id:
            tid = name_to_task_id[tname]
            rid = name_to_res_id[rname]
            if tid in leaf_tasks_dict:
                assignments_by_task[tid].append({
                    'res_id': rid,
                    'work_hours': parse_work_hours(a['Work']),
                    'units': parse_units(a['Units'])
                })

    # 5. Extract Resource Properties
    resources_dict = {}
    for r in raw_resources:
        if r.get('Name'):
            rid = int(r['ID'])
            resources_dict[rid] = {
                'id': rid,
                'name': r['Name'],
                'standard_rate': parse_rate(r.get('Standard Rate', '$50.00/h')),
                'max_units': parse_units(r.get('Max Units', '100%'))
            }

    # 6. Check Resource Overload
    overloaded_tasks = []
    for tid in task_ids:
        for asg in assignments_by_task[tid]:
            rid = asg['res_id']
            needed = asg['units']
            available = resources_dict[rid]['max_units']
            if needed > available:
                overloaded_tasks.append(
                    f"Task ID {tid} ('{leaf_tasks_dict[tid]['name']}') requires {needed*100}% of Resource ID {rid} ({resources_dict[rid]['name']}), but only {available*100}% is available."
                )
    if overloaded_tasks:
        print("\nWARNING: Resource Overloads Detected!")
        for ot in overloaded_tasks:
            print(f"  {ot}")
        print("Note: Solver may find this infeasible if tasks run in parallel. Check daily limits.\n")
    else:
        print("Diagnostics: No individual task resource requirement exceeds global capacity.")

    # 7. Parse Base Date & Compute Calendar Days
    starts = []
    for t in raw_tasks:
        if t.get('Start'):
            try:
                dt = datetime.strptime(t['Start'].strip(), "%d %B %Y %I:%M %p")
                starts.append(dt)
            except ValueError:
                pass
    base_date = min(starts)
    
    # Calculate baseline start and finish day for each task (calendar days)
    for tid, t in leaf_tasks_dict.items():
        try:
            start_dt = datetime.strptime(t['start_str'].strip(), "%d %B %Y %I:%M %p")
            finish_dt = datetime.strptime(t['finish_str'].strip(), "%d %B %Y %I:%M %p")
            t['start_day'] = (start_dt - base_date).days + 1
            t['finish_day'] = (finish_dt - base_date).days + 1
        except Exception:
            t['start_day'] = 1
            t['finish_day'] = t['start_day'] + t['duration_days']

    # 8. Time-Window Preprocessing (CPM Forward & Backward pass)
    # This keeps the model small and fast
    H = max(t['finish_day'] for t in leaf_tasks_dict.values()) + 15
    
    # We estimate min task duration by applying max crowding (x = max) and max overtime (tau = max)
    alpha = CONFIG["alpha"]
    beta = CONFIG["beta"]
    max_x = max(CONFIG["x_grid"])
    max_tau = max(CONFIG["tau_grid"])
    max_crash_factor = (max_x ** alpha) * ((1.0 + max_tau/8.0) ** beta)
    
    # Minimum duration under maximum crashing
    min_dur = {}
    for tid in task_ids:
        d_base = leaf_tasks_dict[tid]['duration_days']
        if assignments_by_task[tid]:
            min_dur[tid] = max(1, int(d_base / max_crash_factor))
        else:
            min_dur[tid] = d_base

    # Forward pass: Earliest Start Day (ES)
    ES = {tid: 1 for tid in task_ids}
    for _ in range(len(task_ids)):
        for tid in task_ids:
            for pid, rel_type, lag in predecessors_clean[tid]:
                if pid in ES:
                    lag_int = int(lag)
                    if rel_type == 'FS':
                        ES[tid] = max(ES[tid], ES[pid] + min_dur[pid] + lag_int)
                    elif rel_type == 'SS':
                        ES[tid] = max(ES[tid], ES[pid] + lag_int)
                    elif rel_type == 'FF':
                        ES[tid] = max(ES[tid], ES[pid] + min_dur[pid] - min_dur[tid] + lag_int)

    # Backward pass: Latest Finish Day (LF)
    LF = {tid: H for tid in task_ids}
    for _ in range(len(task_ids)):
        for tid in task_ids:
            for succ_id in successors_clean[tid]:
                min_dur_succ = min_dur[succ_id]
                for pid, rel_type, lag in predecessors_clean[succ_id]:
                    if pid == tid:
                        lag_int = int(lag)
                        if rel_type == 'FS':
                            LF[tid] = min(LF[tid], LF[succ_id] - min_dur_succ - lag_int)
                        elif rel_type == 'SS':
                            LF[tid] = min(LF[tid], LF[succ_id] - min_dur_succ - lag_int + leaf_tasks_dict[tid]['duration_days'])
                        elif rel_type == 'FF':
                            LF[tid] = min(LF[tid], LF[succ_id] - lag_int)

    # Check Impossible Deadline (For Scenario C or overall feasibility)
    min_project_finish = max(ES[tid] + min_dur[tid] for tid in task_ids)
    print(f"Diagnostics: Minimum possible project completion time under max crashing is {min_project_finish} days.")
    if CONFIG["scenario"] == "C" and min_project_finish > CONFIG["T_d"]:
        raise ValueError(f"Impossible Deadline! Scenario C requires project finish <= {CONFIG['T_d']} days, "
                         f"but the absolute minimum project duration is {min_project_finish} days.")

    return {
        "tasks": leaf_tasks_dict,
        "resources": resources_dict,
        "assignments": assignments_by_task,
        "task_ids": task_ids,
        "resource_ids": sorted(list(resources_dict.keys())),
        "predecessors": predecessors_clean,
        "successors": successors_clean,
        "ES": ES,
        "LF": LF,
        "H": H
    }

# ==============================================================================
# 3) OPTIMIZATION MODEL BUILDER
# ==============================================================================
def build_and_solve_model(data):
    model = pyo.ConcreteModel()
    
    # Config parameters
    alpha_tot = CONFIG["alpha"]
    beta = CONFIG["beta"]
    ot_mult = CONFIG["ot_mult"]
    c_ind = CONFIG["c_ind"]
    c_late = CONFIG["c_late"]
    c_early = CONFIG["c_early"]
    T_d = CONFIG["T_d"]
    x_grid = CONFIG["x_grid"]
    tau_grid = CONFIG["tau_grid"]
    H = data["H"]
    
    M_len = len(x_grid)
    N_len = len(tau_grid)
    
    # Sets
    model.I = pyo.Set(initialize=data["task_ids"])
    model.K = pyo.Set(initialize=data["resource_ids"])
    model.M = pyo.Set(initialize=range(M_len))
    model.N = pyo.Set(initialize=range(N_len))
    
    # Precompute modes (duration, daily cost, daily resource usage)
    d_pre = {}
    cost_pre = {}
    u_day_pre = {}
    o_day_pre = {}
    
    for i in data["task_ids"]:
        asgs = data["assignments"][i]
        d_base = data["tasks"][i]["duration_days"]
        omega = sum(asg["work_hours"] for asg in asgs) if asgs else d_base
        sum_alpha = alpha_tot if asgs else 0.0
        
        for m in range(M_len):
            x = x_grid[m]
            for n in range(N_len):
                tau = tau_grid[n]
                
                # Duration crashed (integer days)
                if asgs:
                    dur_val = d_base / ((x ** sum_alpha) * ((1.0 + tau/8.0) ** beta))
                    dur = max(1, int(round(dur_val)))
                else:
                    dur = d_base
                d_pre[(i, m, n)] = dur
                
                # Daily resource regular and overtime hours
                for asg in asgs:
                    rid = asg["res_id"]
                    u_day_pre[(i, rid, m, n)] = asg["units"] * 8.0 * x
                    o_day_pre[(i, rid, m, n)] = asg["units"] * tau
                
                # Daily cost under this mode
                l_cost = 0.0
                for asg in asgs:
                    rid = asg["res_id"]
                    units = asg["units"]
                    std_rate = data["resources"][rid]["standard_rate"]
                    ot_rate = std_rate * ot_mult
                    l_cost += std_rate * (units * 8.0 * x) + ot_rate * (units * tau)
                cost_pre[(i, m, n)] = l_cost

    # 1. Mode decision variables (binary, per task)
    model.chi = pyo.Var(model.I, model.M, model.N, domain=pyo.Binary)

    # Mode selection constraint: exactly one mode per task
    def mode_selection_rule(m_eq, i):
        return sum(m_eq.chi[i, m, n] for m in range(M_len) for n in range(N_len)) == 1
    model.mode_selection = pyo.Constraint(model.I, rule=mode_selection_rule)

    # 2. Time-indexed variables (sparse)
    valid_it = []
    for i in data["task_ids"]:
        for t in range(data["ES"][i], data["LF"][i] + 1):
            valid_it.append((i, t))
            
    model.y = pyo.Var(valid_it, domain=pyo.NonNegativeReals, bounds=(0.0, 1.0)) # active
    model.z = pyo.Var(valid_it, domain=pyo.NonNegativeReals, bounds=(0.0, 1.0)) # start

    # Scheduling variables (continuous)
    model.S = pyo.Var(model.I, domain=pyo.NonNegativeReals)
    model.F = pyo.Var(model.I, domain=pyo.NonNegativeReals)
    model.d = pyo.Var(model.I, domain=pyo.NonNegativeReals)
    
    # Project metrics
    model.T_proj = pyo.Var(domain=pyo.NonNegativeReals)
    model.L = pyo.Var(domain=pyo.NonNegativeReals)
    model.E = pyo.Var(domain=pyo.NonNegativeReals)

    # Link scheduling variables to time-indexed variables
    def start_time_rule(m_eq, i):
        return m_eq.S[i] == sum(t * m_eq.z[i, t] for t in range(data["ES"][i], data["LF"][i] + 1))
    model.start_time = pyo.Constraint(model.I, rule=start_time_rule)

    def duration_rule(m_eq, i):
        return m_eq.d[i] == sum(m_eq.y[i, t] for t in range(data["ES"][i], data["LF"][i] + 1))
    model.duration = pyo.Constraint(model.I, rule=duration_rule)

    def finish_time_rule(m_eq, i):
        return m_eq.F[i] == m_eq.S[i] + m_eq.d[i]
    model.finish_time = pyo.Constraint(model.I, rule=finish_time_rule)

    # Link task duration to the selected mode
    def task_duration_mode_rule(m_eq, i):
        return m_eq.d[i] == sum(m_eq.chi[i, m, n] * d_pre[(i, m, n)] for m in range(M_len) for n in range(N_len))
    model.task_duration_mode = pyo.Constraint(model.I, rule=task_duration_mode_rule)

    # Contiguity
    def contiguity_rule_1(m_eq, i, t):
        if t == data["ES"][i]:
            return m_eq.z[i, t] == m_eq.y[i, t]
        else:
            return m_eq.z[i, t] >= m_eq.y[i, t] - m_eq.y[i, t-1]
    model.contiguity_1 = pyo.Constraint(valid_it, rule=contiguity_rule_1)
    
    def contiguity_rule_2(m_eq, i):
        return sum(m_eq.z[i, t] for t in range(data["ES"][i], data["LF"][i] + 1)) <= 1
    model.contiguity_2 = pyo.Constraint(model.I, rule=contiguity_rule_2)

    # Precedence
    model.precedence = pyo.ConstraintList()
    for j in data["task_ids"]:
        for pid, rel_type, lag in data["predecessors"][j]:
            lag_val = float(lag)
            if rel_type == 'FS':
                model.precedence.add(model.S[j] >= model.F[pid] + lag_val)
            elif rel_type == 'SS':
                model.precedence.add(model.S[j] >= model.S[pid] + lag_val)
            elif rel_type == 'FF':
                model.precedence.add(model.F[j] >= model.F[pid] + lag_val)

    # 3. Resource daily variables and linearization (McCormick envelopes)
    valid_ir_t = []
    for i in data["task_ids"]:
        asgs = data["assignments"][i]
        for asg in asgs:
            rid = asg["res_id"]
            for t in range(data["ES"][i], data["LF"][i] + 1):
                valid_ir_t.append((i, rid, t))
                
    model.u_daily = pyo.Var(valid_ir_t, domain=pyo.NonNegativeReals)
    model.o_daily = pyo.Var(valid_ir_t, domain=pyo.NonNegativeReals)
    
    # Task-level resource usage variables
    model.u_task_day = pyo.Var([(i, asg["res_id"]) for i in data["task_ids"] for asg in data["assignments"][i]], domain=pyo.NonNegativeReals)
    model.o_task_day = pyo.Var([(i, asg["res_id"]) for i in data["task_ids"] for asg in data["assignments"][i]], domain=pyo.NonNegativeReals)
    
    # Link task-level daily resource usage to mode selection
    def u_task_day_rule(m_eq, i, rid):
        return m_eq.u_task_day[(i, rid)] == sum(m_eq.chi[i, m, n] * u_day_pre[(i, rid, m, n)] for m in range(M_len) for n in range(N_len))
    model.u_task_day_const = pyo.Constraint(model.u_task_day.index_set(), rule=u_task_day_rule)
    
    def o_task_day_rule(m_eq, i, rid):
        return m_eq.o_task_day[(i, rid)] == sum(m_eq.chi[i, m, n] * o_day_pre[(i, rid, m, n)] for m in range(M_len) for n in range(N_len))
    model.o_task_day_const = pyo.Constraint(model.o_task_day.index_set(), rule=o_task_day_rule)

    # McCormick Envelopes to linearize daily usage: u_daily[i, rid, t] = y[i, t] * u_task_day[i, rid]
    model.mccormick = pyo.ConstraintList()
    for (i, rid, t) in valid_ir_t:
        asgs = data["assignments"][i]
        asg = next(a for a in asgs if a["res_id"] == rid)
        u_max = asg["units"] * 8.0 * max(x_grid)
        o_max = asg["units"] * max(tau_grid)
        
        # Regular hours
        model.mccormick.add(model.u_daily[i, rid, t] <= u_max * model.y[i, t])
        model.mccormick.add(model.u_daily[i, rid, t] <= model.u_task_day[(i, rid)])
        model.mccormick.add(model.u_daily[i, rid, t] >= model.u_task_day[(i, rid)] - u_max * (1.0 - model.y[i, t]))
        
        # Overtime hours
        model.mccormick.add(model.o_daily[i, rid, t] <= o_max * model.y[i, t])
        model.mccormick.add(model.o_daily[i, rid, t] <= model.o_task_day[(i, rid)])
        model.mccormick.add(model.o_daily[i, rid, t] >= model.o_task_day[(i, rid)] - o_max * (1.0 - model.y[i, t]))

    # Resource capacity checks on each day t
    model.res_capacity_reg = pyo.ConstraintList()
    model.res_capacity_ot = pyo.ConstraintList()
    
    for t in range(1, H + 1):
        for rid in data["resource_ids"]:
            # Find active assignments on day t
            active_tasks = []
            for i in data["task_ids"]:
                if data["ES"][i] <= t <= data["LF"][i]:
                    for asg in data["assignments"][i]:
                        if asg["res_id"] == rid:
                            active_tasks.append(i)
                            
            if active_tasks:
                max_units = data["resources"][rid]["max_units"]
                r_reg_cap = max_units * 8.0
                r_ot_cap = max_units * max(tau_grid)
                
                model.res_capacity_reg.add(sum(model.u_daily[i, rid, t] for i in active_tasks) <= r_reg_cap)
                model.res_capacity_ot.add(sum(model.o_daily[i, rid, t] for i in active_tasks) <= r_ot_cap)

    # 4. Project makespan definition
    def project_finish_rule(m_eq, i):
        return m_eq.T_proj >= m_eq.F[i]
    model.project_finish = pyo.Constraint(model.I, rule=project_finish_rule)

    # Earliness / Lateness linearization
    def late_early_rule(m_eq):
        return m_eq.T_proj - T_d == m_eq.L - m_eq.E
    model.late_early = pyo.Constraint(rule=late_early_rule)

    # ---------------------------------------------------------
    # OBJECTIVES & SCENARIOS
    # ---------------------------------------------------------
    # Labor Cost is sum_{i} cost^{total}_i
    labor_cost_expr = sum(model.chi[i, m, n] * d_pre[(i, m, n)] * cost_pre[(i, m, n)]
                           for i in data["task_ids"]
                           for m in range(M_len)
                           for n in range(N_len))
    overhead_cost_expr = c_ind * model.T_proj
    penalty_cost_expr = c_late * model.L - c_early * model.E
    total_cost_expr = labor_cost_expr + overhead_cost_expr + penalty_cost_expr

    if CONFIG["scenario"] == "A":
        model.obj = pyo.Objective(expr=total_cost_expr, sense=pyo.minimize)
    elif CONFIG["scenario"] == "B":
        def budget_limit_rule(m_eq):
            return total_cost_expr <= CONFIG["B_max"]
        model.budget_limit = pyo.Constraint(rule=budget_limit_rule)
        model.obj = pyo.Objective(expr=model.T_proj, sense=pyo.minimize)
    elif CONFIG["scenario"] == "C":
        def deadline_limit_rule(m_eq):
            return model.T_proj <= T_d
        model.deadline_limit = pyo.Constraint(rule=deadline_limit_rule)
        model.obj = pyo.Objective(expr=total_cost_expr, sense=pyo.minimize)

    # Solve
    print(f"Solving model under Scenario {CONFIG['scenario']} using {CONFIG['solver_name']}...")
    solver = pyo.SolverFactory(CONFIG["solver_name"])
    solver.options['sec'] = CONFIG["time_limit"]
    
    results = solver.solve(model, tee=CONFIG["verbose"])
    
    if (results.solver.status == pyo.SolverStatus.ok) and (results.solver.termination_condition == pyo.TerminationCondition.optimal):
        return model, d_pre, cost_pre, total_cost_expr, labor_cost_expr
    else:
        print("Optimization Status:", results.solver.status)
        print("Termination Condition:", results.solver.termination_condition)
        raise RuntimeError("Solver failed to find an optimal solution.")

# ==============================================================================
# 4) REPORTING & EXPORT
# ==============================================================================
def generate_report(model, data, total_cost_expr, labor_cost_expr):
    T_val = pyo.value(model.T_proj)
    L_val = pyo.value(model.L)
    E_val = pyo.value(model.E)
    tot_cost = pyo.value(total_cost_expr)
    lab_cost = pyo.value(labor_cost_expr)
    
    print("\n" + "="*50)
    print("                OPTIMAL SCHEDULE REPORT")
    print("="*50)
    print(f"Scenario Selected:           {CONFIG['scenario']}")
    print(f"Project Completion Time:     {T_val:.1f} days")
    print(f"Target Deadline (T_d):       {CONFIG['T_d']} days")
    print(f"Earliness Days (E):          {E_val:.1f} days")
    print(f"Lateness Days (L):           {L_val:.1f} days")
    print(f"Total Labor Cost:            {lab_cost:.2f}")
    print(f"Total Project Cost:          {tot_cost:.2f}")
    print("-"*50)
    
    print(f"{'Task ID':<8}{'Task Name':<45}{'Start':<8}{'Finish':<8}{'Duration':<10}{'BaseDur':<8}{'Crashing levers used (x, tau)'}")
    print("-"*110)
    
    schedule_records = []
    x_grid = CONFIG["x_grid"]
    tau_grid = CONFIG["tau_grid"]
    
    for i in data["task_ids"]:
        s_i = pyo.value(model.S[i])
        f_i = pyo.value(model.F[i])
        d_i = pyo.value(model.d[i])
        d_base = data["tasks"][i]["duration_days"]
        
        # Find selected mode
        avg_x = 1.0
        avg_tau = 0.0
        found_mode = False
        for m in range(len(x_grid)):
            for n in range(len(tau_grid)):
                if pyo.value(model.chi[i, m, n]) > 0.5:
                    avg_x = x_grid[m]
                    avg_tau = tau_grid[n]
                    found_mode = True
                    break
            if found_mode:
                break
                
        lever_str = f"x={avg_x:.2f}, ot={avg_tau:.1f}h" if data["assignments"][i] else "No resource"
        
        if data["assignments"][i] or abs(d_i - d_base) > 0.01:
            name_truncated = data["tasks"][i]["name"][:42]
            print(f"{i:<8}{name_truncated:<45}{s_i:<8.1f}{f_i:<8.1f}{d_i:<10.1f}{d_base:<8}{lever_str}")
            
        active_days = []
        for t in range(data["ES"][i], data["LF"][i] + 1):
            if pyo.value(model.y[i, t]) > 0.5:
                active_days.append(t)
                
        schedule_records.append({
            "task_id": i,
            "task_name": data["tasks"][i]["name"],
            "start": round(s_i, 2),
            "finish": round(f_i, 2),
            "duration": round(d_i, 2),
            "base_duration": d_base,
            "average_crowding": round(avg_x, 2),
            "average_overtime": round(avg_tau, 2),
            "active_days": active_days
        })
        
    out_json = os.path.join(WORKSPACE_DIR, "data/optimal_schedule.json")
    with open(out_json, "w", encoding="utf-8") as f:
        json.dump({
            "summary": {
                "scenario": CONFIG["scenario"],
                "project_duration_days": round(T_val, 2),
                "earliness_days": round(E_val, 2),
                "lateness_days": round(L_val, 2),
                "labor_cost": round(lab_cost, 2),
                "total_cost": round(tot_cost, 2)
            },
            "schedule": schedule_records
        }, f, indent=4)
    print("-"*110)
    print(f"Detailed optimal schedule saved to: {out_json}\n")

# ==============================================================================
# MAIN RUNNER
# ==============================================================================
if __name__ == "__main__":
    try:
        project_data = process_project()
        model, d_pre, cost_pre, total_cost_expr, labor_cost_expr = build_and_solve_model(project_data)
        generate_report(model, project_data, total_cost_expr, labor_cost_expr)
    except Exception as e:
        print("An error occurred during optimization:")
        import traceback
        traceback.print_exc()
