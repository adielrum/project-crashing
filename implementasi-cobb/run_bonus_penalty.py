import os
import numpy as np
from pymoo.algorithms.soo.nonconvex.ga import GA
from pymoo.operators.crossover.sbx import SBX
from pymoo.operators.mutation.pm import PM
from pymoo.termination.ftol import MultiObjectiveSpaceTermination
from pymoo.termination.robust import RobustTermination
from pymoo.optimize import minimize
from cobb_model import (
    load_data, data_path, ResourceBasedScheduling, MyCallback,
    generate_gantt_comparison_plot, generate_interactive_gantt_html, save_solution_json
)

def run_bonus_penalty():
    base_dir = os.path.dirname(os.path.abspath(__file__))
    tasks, precedence, resources, N, K_i = load_data(
        path_tasks=data_path("data_tasks.csv"),
        path_precedence=data_path("data_precedence.csv"),
        path_assignments=data_path("data_assignments.csv"),
    )

    CURRENT_DAY = 0
    T_MAX = 310

    problem = ResourceBasedScheduling(
        tasks=tasks, precedence=precedence, resources=resources, N=N, K_i=K_i,
        alpha=0.7, beta=0.7, x_min=1.0, tau_min=0.0, tau_max=4.0, D_min_ratio=0.5,
        T_max=T_MAX, current_day=CURRENT_DAY, overtime_mult=1.5, hours_per_day=8,
        mode="bonus_penalty", c_late=5000.0, c_early=2000.0
    )

    algorithm = GA(
        pop_size=200, crossover=SBX(prob=0.9, eta=15), mutation=PM(eta=20),
        eliminate_duplicates=True,
    )
    callback = MyCallback()
    termination = RobustTermination(MultiObjectiveSpaceTermination(tol=0.005, n_skip=5), period=20)

    res = minimize(problem, algorithm, termination, seed=42, callback=callback, verbose=False)

    if res.X is not None:
        x_opt = res.X
        P = problem.P
        x_ik_opt = x_opt[0:P]
        tau_ik_opt = x_opt[P:2*P]
        
        for p in problem.completed_pairs:
            x_ik_opt[p] = 1.0
            tau_ik_opt[p] = 0.0

        D_ik_opt, D_i_opt = problem.compute_durations(x_opt)
        for i in problem.completed_tasks:
            D_i_opt[i] = problem.D_base_i[i]

        s_opt, f_opt = problem.forward_pass(D_i_opt)
        makespan = float(np.max(f_opt))

        labor_cost = float(np.sum(D_ik_opt * x_ik_opt * problem.U_ik * (problem.hours_per_day * problem.r_k + tau_ik_opt * problem.r_k_ot)))
        penalty = problem.c_late * max(0.0, makespan - problem.T_max)
        bonus = problem.c_early * max(0.0, problem.T_max - makespan)
        total_cost = labor_cost + penalty - bonus

        out_json = os.path.join(base_dir, "../outputs/cobb_bonus_penalty.json")
        out_gantt = os.path.join(base_dir, "../outputs/cobb_bonus_penalty_gantt.png")
        out_html = os.path.join(base_dir, "../outputs/cobb_bonus_penalty_gantt.html")

        save_solution_json(
            tasks, resources, precedence, problem,
            x_opt, x_ik_opt, tau_ik_opt, D_ik_opt, D_i_opt, s_opt, f_opt,
            CURRENT_DAY, T_MAX, makespan, labor_cost, total_cost, out_json
        )
        generate_gantt_comparison_plot(tasks, problem.s_baseline, problem.f_baseline, s_opt, f_opt, CURRENT_DAY, out_gantt)
        generate_interactive_gantt_html(tasks, resources, problem.s_baseline, problem.f_baseline, s_opt, f_opt, x_ik_opt, tau_ik_opt, D_ik_opt, D_i_opt, CURRENT_DAY, T_MAX, out_html)
        print(f"Bonus Penalty: Status = Feasible, Makespan = {makespan}, Total Cost = {total_cost}")
    else:
        print("Bonus Penalty: No feasible solution found.")

if __name__ == "__main__":
    run_bonus_penalty()