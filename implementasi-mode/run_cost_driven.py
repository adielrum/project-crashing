import os
import sys

base_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.append(os.path.join(base_dir, "../implementasi-resource"))

from cobb_model import load_data, data_path, save_solution_json
from solver_milp import solve_milp_cobb_douglas

def main():
    print("=== Model B (Mode-Based MILP): Running Cost-Driven Scenario (T_max = 243) ===")
    tasks, precedence, resources, N, K_i = load_data(
        path_tasks=data_path("data_tasks.csv"),
        path_precedence=data_path("data_precedence.csv"),
        path_assignments=data_path("data_assignments.csv"),
    )
    
    sol = solve_milp_cobb_douglas(
        tasks, precedence, resources, N, K_i,
        alpha=0.7, beta=0.7, T_max=243, current_day=20,
        mode="cost_with_deadline", time_limit=60.0
    )
    
    if sol and isinstance(sol, dict) and "makespan" in sol:
        print(f"\nSolution Found:")
        print(f"  Makespan : {sol['makespan']} days")
        print(f"  Total Cost : ${sol['total_cost']:,.2f}")
        out_file = os.path.join(base_dir, "../outputs/mode-based/milp_cobb_cost_with_deadline.json")
        print(f"  Saved solution JSON to {out_file}")
    else:
        print("\nNo feasible solution found or time limit exceeded.")

if __name__ == "__main__":
    main()
