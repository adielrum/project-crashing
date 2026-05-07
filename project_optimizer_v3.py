"""
v3: MILP + GA crashing optimizer WITH time-indexed resource capacity constraints.

Per Model.md §1.3, daily load per resource is enforced. The simplification:
we use baseline U_{i,k} (without x amplification) in the capacity sum to
keep the MILP linear. Crashing via x still affects duration and cost; only
its effect on capacity is approximated.
"""

from datetime import datetime
from project_optimizer_v2 import run


def main():
    folder = "/Users/macintoshhd/Documents/Adiel/pemod/Pemod-Sandbox/Schedules_CSV"
    base_date = datetime(2023, 5, 1)

    print("=" * 60)
    print("PROJECT CRASHING OPTIMIZER v3 (with resource capacity)")
    print("=" * 60)

    horizon = 480
    while True:
        try:
            cd = int(input(f"\nCurrent project day [1..{horizon}]: "))
            if 1 <= cd <= horizon:
                break
        except ValueError:
            pass
    while True:
        try:
            td = int(input(f"Target project end day [{cd}..{horizon}]: "))
            if cd <= td <= horizon:
                break
        except ValueError:
            pass

    run(folder, base_date, cd, td, output_prefix="v3", capacity=True)


if __name__ == "__main__":
    main()
