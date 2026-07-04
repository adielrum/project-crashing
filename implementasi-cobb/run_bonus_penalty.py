import os
from cobb_model import (
    load_data, data_path, ResourceBasedScheduling, solve,
    save_solution_json, generate_gantt_comparison_plot, generate_interactive_gantt_html,
)

def run_bonus_penalty():
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
        mode="bonus_penalty", c_late=5000.0, c_early=2000.0,
    )

    solution = solve(problem, pop_size=200, seed=42, verbose=True)

    if solution is not None:
        base_dir = os.path.dirname(os.path.abspath(__file__))
        out_json = os.path.join(base_dir, "../outputs/cobb/cobb_bonus_penalty.json")
        out_gantt = os.path.join(base_dir, "../outputs/cobb/cobb_bonus_penalty_gantt.png")
        out_html = os.path.join(base_dir, "../outputs/cobb/cobb_bonus_penalty_gantt.html")

        save_solution_json(
            tasks, resources, precedence, problem,
            solution["pymoo_result"].X, solution["x_ik"], solution["tau_ik"],
            solution["D_ik"], solution["D_i"], solution["s"], solution["f"],
            CURRENT_DAY, T_MAX, solution["makespan"], solution["labor_cost"],
            solution["total_cost"], out_json,
        )
        generate_gantt_comparison_plot(
            tasks, problem.s_baseline, problem.f_baseline,
            solution["s"], solution["f"], CURRENT_DAY, out_gantt,
        )
        generate_interactive_gantt_html(
            tasks, resources, problem.s_baseline, problem.f_baseline,
            solution["s"], solution["f"], solution["x_ik"], solution["tau_ik"],
            solution["D_ik"], solution["D_i"], CURRENT_DAY, T_MAX, out_html,
        )
        print(f"Bonus Penalty: Makespan = {solution['makespan']:.2f}, "
              f"Total Cost = {solution['total_cost']:.2f}")
    else:
        print("Bonus Penalty: No feasible solution found.")

if __name__ == "__main__":
    run_bonus_penalty()