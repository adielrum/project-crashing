import os
from cobb_model import (
    load_data, data_path, ResourceBasedScheduling, solve,
    save_solution_json, generate_gantt_comparison_plot, generate_interactive_gantt_html,
)

def run_time_driven():
    tasks, precedence, resources, N, K_i, resource_master = load_data(
        path_tasks=data_path("data_tasks.csv"),
        path_precedence=data_path("data_precedence.csv"),
        path_assignments=data_path("data_assignments.csv"),
        path_resources=data_path("data_resources.csv"),
    )

    CURRENT_DAY = 0
    BUDGET_LIMIT = 500000.0

    problem = ResourceBasedScheduling(
        tasks=tasks, precedence=precedence, resources=resources, N=N, K_i=K_i,
        resource_master=resource_master,
        alpha=0.7, beta=0.7, x_min=1.0, tau_min=0.0, tau_max=4.0, D_min_ratio=0.5,
        T_max=344, current_day=CURRENT_DAY, overtime_mult=1.5, hours_per_day=8,
        mode="time_with_budget", budget_limit=BUDGET_LIMIT,
        enforce_resource_constraint=True,
    )

    solution = solve(problem, pop_size=200, seed=42, verbose=False)

    if solution is not None:
        base_dir = os.path.dirname(os.path.abspath(__file__))
        out_json = os.path.join(base_dir, "../outputs/cobb_time_driven.json")
        out_gantt = os.path.join(base_dir, "../outputs/cobb_time_driven_gantt.png")
        out_html = os.path.join(base_dir, "../outputs/cobb_time_driven_gantt.html")

        save_solution_json(
            tasks, resources, precedence, problem,
            solution["pymoo_result"].X, solution["x_ik"], solution["tau_ik"],
            solution["D_ik"], solution["D_i"], solution["s"], solution["f"],
            CURRENT_DAY, 344, solution["makespan"], solution["labor_cost"],
            solution["labor_cost"], out_json,
        )
        generate_gantt_comparison_plot(
            tasks, problem.s_baseline, problem.f_baseline,
            solution["s"], solution["f"], CURRENT_DAY, out_gantt,
        )
        generate_interactive_gantt_html(
            tasks, resources, problem.s_baseline, problem.f_baseline,
            solution["s"], solution["f"], solution["x_ik"], solution["tau_ik"],
            solution["D_ik"], solution["D_i"], CURRENT_DAY, 344, out_html,
        )
        print(f"Time Driven: Makespan = {solution['makespan']:.2f}, "
              f"Labor Cost = {solution['labor_cost']:.2f}")
    else:
        print("Time Driven: No feasible solution found.")

if __name__ == "__main__":
    run_time_driven()
