import os
import numpy as np
import matplotlib.pyplot as plt
from pymoo.algorithms.moo.nsga2 import NSGA2
from pymoo.operators.crossover.sbx import SBX
from pymoo.operators.mutation.pm import PM
from pymoo.termination import get_termination
from pymoo.optimize import minimize
from cobb_model import load_data, data_path, ResourceBasedScheduling

def run_multiobjective():
    base_dir = os.path.dirname(os.path.abspath(__file__))
    tasks, precedence, resources, N, K_i = load_data(
        path_tasks=data_path("data_tasks.csv"),
        path_precedence=data_path("data_precedence.csv"),
        path_assignments=data_path("data_assignments.csv"),
    )

    CURRENT_DAY = 0

    problem = ResourceBasedScheduling(
        tasks=tasks, precedence=precedence, resources=resources, N=N, K_i=K_i,
        alpha=0.7, beta=0.7, x_min=1.0, tau_min=0.0, tau_max=4.0, D_min_ratio=0.5,
        T_max=344, current_day=CURRENT_DAY, overtime_mult=1.5, hours_per_day=8,
        mode="multiobjective"
    )

    algorithm = NSGA2(
        pop_size=200, crossover=SBX(prob=0.9, eta=15), mutation=PM(eta=20),
        eliminate_duplicates=True,
    )
    termination = get_termination("n_gen", 100)

    res = minimize(problem, algorithm, termination, seed=42, verbose=True)

    if res.F is not None:
        F = res.F
        # Sort by makespan
        sorted_indices = np.argsort(F[:, 0])
        F_sorted = F[sorted_indices]
        
        plt.figure(figsize=(8, 6))
        plt.scatter(F_sorted[:, 0], F_sorted[:, 1], color='b', marker='o')
        plt.plot(F_sorted[:, 0], F_sorted[:, 1], color='b', linestyle='-')
        plt.xlabel('Makespan (days)')
        plt.ylabel('Labor Cost ($)')
        plt.title('Time-Cost Pareto Front (Cobb-Douglas NSGA-II)')
        plt.grid(True)
        
        out_dir = os.path.join(base_dir, "../outputs")
        os.makedirs(out_dir, exist_ok=True)
        plt.savefig(os.path.join(out_dir, "cobb_pareto_front.png"))
        print(f"Saved Pareto front plot to {os.path.join(out_dir, 'cobb_pareto_front.png')}")
    else:
        print("Multi-objective: No feasible solutions found.")

if __name__ == "__main__":
    run_multiobjective()
