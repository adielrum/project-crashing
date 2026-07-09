import os
import json
import numpy as np
import matplotlib.pyplot as plt
import matplotlib.ticker as ticker

class OrderOfMagnitudeFormatter(ticker.ScalarFormatter):
    """Custom formatter to force 1e6 scale with exactly 2 decimal places."""
    def __init__(self, order=0, **kwargs):
        super().__init__(**kwargs)
        self.order = order
    def _set_order_of_magnitude(self):
        self.orderOfMagnitude = self.order
    def __call__(self, x, pos=None):
        try:
            xp = (x - getattr(self, 'offset', 0)) / (10 ** self.orderOfMagnitude)
            if abs(xp) < 1e-8:
                xp = 0.0
            return f"{xp:.2f}"
        except Exception:
            return super().__call__(x, pos)

def main():
    # Setup styling exactly matching publication guidelines
    plt.rcParams.update({
        "font.family": "serif",
        "font.serif": ["New Computer Modern", "Computer Modern", "CMU Serif", "Times New Roman", "DejaVu Serif"],
        "mathtext.fontset": "cm",
        "font.size": 9,
        "axes.labelsize": 9,
        "legend.fontsize": 9,
        "xtick.labelsize": 9,
        "ytick.labelsize": 9,
        "figure.dpi": 600,
    })

    input_dir = "D:/ITB/Semester 6/Pemod/project-crashing/outputs/comparison/multi"
    output_dir = "C:/Users/User/.gemini/antigravity/brain/ca8e99ac-09d4-464c-9782-cf02bc20af4d"

    files = [
        "A_ga_cobb_pareto.json",
        "B_milp_cobb_pareto.json",
        "C_cpsat_pareto.json"
    ]

    valid = []
    for f in files:
        path = os.path.join(input_dir, f)
        if os.path.exists(path):
            with open(path, "r", encoding="utf-8") as fp:
                valid.append(json.load(fp))

    def _to_total_cost(pts, c_late=2000.0, c_early=2000.0):
        if not len(pts): return np.array([])
        pts_arr = np.array(pts)
        tc = []
        for pt in pts_arr:
            t, z = pt[0], pt[1]
            if t > 250.0:
                pen = c_late * (t - 250.0)
                bon = 0.0
            else:
                pen = 0.0
                bon = c_early * (250.0 - t)
            tc.append([t, z + pen - bon])
        return np.array(tc)

    styles = {
        "A": dict(color="#1f77b4", marker="o", linestyle="-", label="Resource-Based Model"),
        "B": dict(color="#d62728", marker="s", linestyle="--", label="Mode-Based Model"),
        "C": dict(color="#2ca02c", marker="^", linestyle="-.", label="Time-Based Model"),
    }

    fig, ax = plt.subplots(figsize=(6.27, 4.18), dpi=600)
    ax.yaxis.set_major_formatter(OrderOfMagnitudeFormatter(order=6, useMathText=False))

    for r in valid:
        scen = r["scenario"]
        pts  = _to_total_cost(r["pareto_points"], c_late=2000.0, c_early=2000.0)
        st   = styles.get(scen, dict(color="black", marker="x", linestyle=":", label=f"Scenario {scen}"))
        
        if scen == "A" and len(pts) > 0:
            thinned_pts = []
            last_ms = -999.0
            for pt in pts:
                if abs(pt[0] - last_ms) >= 1.5:
                    thinned_pts.append(pt)
                    last_ms = pt[0]
            if not thinned_pts or thinned_pts[-1][0] != pts[-1][0]:
                thinned_pts.append(pts[-1])
            pts_to_plot = np.array(thinned_pts)
        else:
            pts_to_plot = pts

        if scen == "A" and r.get("all_runs_pareto"):
            x_grid = np.linspace(210.0, 344.0, 200)
            c_low, c_high = [], []
            for x in x_grid:
                costs_at_x = []
                for run_pts in r["all_runs_pareto"]:
                    run_tc = _to_total_cost(run_pts, c_late=2000.0, c_early=2000.0)
                    run_tc = run_tc[np.argsort(run_tc[:, 0])]
                    if run_tc[0, 0] <= x <= run_tc[-1, 0]:
                        val = np.interp(x, run_tc[:, 0], run_tc[:, 1])
                        costs_at_x.append(val)
                    elif x > run_tc[-1, 0]:
                        costs_at_x.append(run_tc[-1, 1] + 2000.0 * (x - max(250.0, run_tc[-1, 0])) if x > 250.0 else run_tc[-1, 1])
                    elif x < run_tc[0, 0]:
                        costs_at_x.append(run_tc[0, 1])
                if len(costs_at_x) >= 3:
                    c_low.append(min(costs_at_x))
                    c_high.append(max(costs_at_x))
                else:
                    c_low.append(np.nan)
                    c_high.append(np.nan)
            ax.fill_between(x_grid, c_low, c_high, color=st["color"], alpha=0.18, label="_nolegend_", zorder=1)

        ax.plot(
            pts_to_plot[:, 0], pts_to_plot[:, 1],
            color=st["color"], marker=st["marker"], linestyle=st["linestyle"],
            linewidth=1.2, markersize=3.5, label=st["label"], alpha=0.85, zorder=3
        )

    ax.set_xlabel("Time (days)", fontsize=9, labelpad=6)
    ax.set_ylabel("Total Project Cost ($)", fontsize=9, labelpad=6)
    ax.grid(True, linestyle=":", alpha=0.55)
    ax.legend(fontsize=9, frameon=True, facecolor="white", edgecolor="none")
    fig.tight_layout()
    ax.set_position([0.115, 0.12, 0.85, 0.85])

    out_png = os.path.join(output_dir, "multiobjective_totalcost_comparison_clate2000.png")
    out_svg = os.path.join(output_dir, "multiobjective_totalcost_comparison_clate2000.svg")
    fig.savefig(out_png, dpi=600)
    fig.savefig(out_svg)
    plt.close(fig)
    print(f"Saved hypothetical $2000/d penalty chart to: {out_png}")

if __name__ == "__main__":
    main()
