import os
import sys

base_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.append(os.path.join(base_dir, "../implementasi-resource"))

from run_sensitivity_ga import run_ga_sensitivity

def run_master_model_a_sensitivity():
    print("==========================================================================")
    print("     STARTING MASTER SENSITIVITY ORCHESTRATION: MODEL A (GA APPROACH)     ")
    print("==========================================================================")
    try:
        run_ga_sensitivity()
    except Exception as e:
        print(f"[ERROR] Model A Sensitivity failed: {e}")
        
    print("==========================================================================")
    print("           MODEL A (GA) MASTER SENSITIVITY SUITE COMPLETE!                ")
    print("==========================================================================")

if __name__ == "__main__":
    run_master_model_a_sensitivity()
