import numpy as np
import matplotlib.pyplot as plt
import os
import seaborn as sns

# 1. Alpha (Overcrowding) Calibration Plot
# If we multiply the workforce by x (e.g., x=2 means 2x workers)
# The duration becomes (1/x)^alpha. 
# So the effective "work" we get out of the new workforce multiplier is 1 / ((1/x)^alpha) = x^alpha
# We can express this as: "If I hire 100% more workers (x=2), how much more output per day do I get?"
# Output multiplier = 2^alpha.

alpha_vals = np.linspace(0.1, 1.0, 10)
x_vals = np.array([1.5, 2.0, 3.0]) # 50% more, 100% more, 200% more workers

plt.figure(figsize=(10, 6))
colors = ['blue', 'orange', 'green']
labels = ['+50% Workers (1.5x)', '+100% Workers (2x)', '+200% Workers (3x)']

for x, color, label in zip(x_vals, colors, labels):
    output_multiplier = x ** alpha_vals
    # Convert to % extra output
    extra_output_pct = (output_multiplier - 1) * 100
    plt.plot(alpha_vals, extra_output_pct, marker='o', color=color, label=label, linewidth=2)

plt.xlabel('Overcrowding Parameter (alpha)', fontsize=12)
plt.ylabel('Actual Extra Output Gained (%)', fontsize=12)
plt.title('Translating Alpha: What do you actually get for hiring more workers?', fontsize=14)
plt.grid(True, linestyle='--', alpha=0.6)
plt.legend(fontsize=11)

# Annotate some key points
plt.axvline(x=1.0, color='red', linestyle=':', alpha=0.5)
plt.text(0.95, 20, 'Ideal (No coordination loss)\nalpha = 1.0', rotation=90, color='red', va='bottom')

plt.axvline(x=0.5, color='gray', linestyle=':', alpha=0.5)
plt.text(0.45, 20, 'High coordination loss\nalpha = 0.5', rotation=90, color='gray', va='bottom')

out_dir = '/Users/macintoshhd/Documents/Adiel/pemod/Pemod-3.0/project-crashing/outputs/sensitivity_analysis'
os.makedirs(out_dir, exist_ok=True)
out_path_alpha = os.path.join(out_dir, 'calibration_alpha.png')
plt.savefig(out_path_alpha, dpi=200, bbox_inches='tight')
plt.close()


# 2. Beta (Overtime) Calibration Plot
# If a worker works tau extra hours (tau=2, 4), total hours = 8 + tau
# The duration multiplier is (8 / (8 + tau))^beta
# Effective daily output multiplier = ((8 + tau) / 8)^beta

beta_vals = np.linspace(0.1, 1.0, 10)
tau_vals = np.array([2, 4, 6]) # +25%, +50%, +75% more hours
labels_tau = ['+2 Hours (10h shift)', '+4 Hours (12h shift)', '+6 Hours (14h shift)']
colors_tau = ['purple', 'teal', 'brown']

plt.figure(figsize=(10, 6))

for tau, color, label in zip(tau_vals, colors_tau, labels_tau):
    output_multiplier = ((8 + tau) / 8) ** beta_vals
    extra_output_pct = (output_multiplier - 1) * 100
    plt.plot(beta_vals, extra_output_pct, marker='s', color=color, label=label, linewidth=2)

# Also plot the "Ideal" lines (if beta=1, output scales linearly with hours)
for tau, color in zip(tau_vals, colors_tau):
    ideal_pct = (tau / 8) * 100
    plt.axhline(y=ideal_pct, color=color, linestyle=':', alpha=0.4)

plt.xlabel('Overtime Parameter (beta)', fontsize=12)
plt.ylabel('Actual Extra Output Gained (%)', fontsize=12)
plt.title('Translating Beta: What do you actually get for working overtime?', fontsize=14)
plt.grid(True, linestyle='--', alpha=0.6)
plt.legend(fontsize=11)

# Annotate some key points
plt.axvline(x=1.0, color='red', linestyle=':', alpha=0.5)
plt.text(0.95, 10, 'Ideal (No fatigue)\nbeta = 1.0', rotation=90, color='red', va='bottom')

plt.axvline(x=0.4, color='gray', linestyle=':', alpha=0.5)
plt.text(0.35, 10, 'Heavy fatigue\nbeta = 0.4', rotation=90, color='gray', va='bottom')

out_path_beta = os.path.join(out_dir, 'calibration_beta.png')
plt.savefig(out_path_beta, dpi=200, bbox_inches='tight')
plt.close()

# 3. Generate a Markdown Table string to include in the report
with open(os.path.join(out_dir, 'calibration_tables.txt'), 'w') as f:
    f.write("### Alpha Calibration Lookup Table (Double the Workforce)\n")
    f.write("| If you double your workforce (2x workers), and the task finishes in... | Then your Alpha (α) is approximately... | Example Trade |\n")
    f.write("|---|---|---|\n")
    f.write("| 50% of original time (Perfect efficiency) | 1.0 | Trench digging, basic labor |\n")
    f.write("| 60% of original time | 0.7 - 0.8 | Bricklaying, framing |\n")
    f.write("| 70% of original time | 0.5 | Electrical wiring, plumbing |\n")
    f.write("| 85% of original time (Terrible efficiency) | 0.2 - 0.3 | Highly confined spaces, elevator shaft install |\n\n")

    f.write("### Beta Calibration Lookup Table (12-Hour Shifts vs 8-Hour)\n")
    f.write("| If you switch to 12-hour shifts (+50% hours), and daily output increases by... | Then your Beta (β) is approximately... | Example Trade |\n")
    f.write("|---|---|---|\n")
    f.write("| 50% (Perfect efficiency, no fatigue) | 1.0 | Automated machine operation |\n")
    f.write("| 35% | 0.7 - 0.8 | Painting, light assembly |\n")
    f.write("| 20% | 0.4 - 0.5 | Heavy lifting, concrete pouring |\n")
    f.write("| <10% (Extreme fatigue, almost useless) | 0.2 | Extreme physical labor under heat |\n")

print("Generated alpha and beta calibration plots and tables.")
