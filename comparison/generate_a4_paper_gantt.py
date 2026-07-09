"""
generate_a4_paper_gantt.py
==========================
Generates publication-quality Gantt chart formats tailored specifically for
academic papers (A4 portrait and landscape, 600 DPI & SVG vector format):

  0. Individual Standalone Models (Model A, Model B, Model C)
     Separate horizontal A4 figures (11.69" x 8.27") for detailed one-by-one discussion.

  1. Side-by-Side Shared-Y Layout (Landscape A4: 11.69" x 8.27")
     Compares Model A, Model B, and Model C in three synchronized vertical columns.

  2. Dual-Bar Overlay Layout (Portrait A4: 8.27" x 11.69")
     Displays Baseline (ghost wireframe bar) and Optimized (solid bar) on the SAME row.

  3. Compact Track-Packed Layout (Landscape A4: 11.69" x 8.27")
     Uses greedy interval packing to condense 30+ activities onto shared horizontal tracks.
"""

import os
import sys
if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
import json
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
from matplotlib.lines import Line2D
import numpy as np

# Configure Academic Styling: New Computer Modern / Serif, 10pt relative to A4
plt.rcParams.update({
    "font.family": "serif",
    "font.serif": ["New Computer Modern", "Computer Modern", "CMU Serif", "Times New Roman", "DejaVu Serif"],
    "font.size": 10,
    "axes.labelsize": 10,
    "axes.titlesize": 11,
    "legend.fontsize": 10,
    "xtick.labelsize": 10,
    "ytick.labelsize": 10,
    "figure.titlesize": 12,
    "mathtext.fontset": "cm"
})

# Add parent directory to path to import solver_base and preprocessing
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
ROOT_DIR = os.path.dirname(SCRIPT_DIR)
sys.path.append(os.path.join(ROOT_DIR, "implementasi-base"))
sys.path.append(os.path.join(ROOT_DIR, "implementasi-cobb"))
sys.path.append(os.path.join(ROOT_DIR, "implementasi-hybrid"))

from solver_base import build_predecessors, build_reference_no_crash_schedule
from preprocessing import preprocess

# Configuration
OUTPUTS_DIR = os.path.join(ROOT_DIR, "outputs", "comparison", "single")
ALPHA = 0.5
BETA = 0.5
X_MAX = 2.0
TAU_MAX = 4.0
OVERTIME_MULT = 1.5
HOURS_PER_DAY = 8
CURRENT_DAY = 20
T_MAX = 250

MODEL_NAMES = [
    ("Model A: Resource-Based", "A_ga_cobb.json", "a4_model_A_resource_based"),
    ("Model B: Mode-Based Model", "B_milp_cobb.json", "a4_model_B_mode_based"),
    ("Model C: Time-Based Model", "C_cpsat.json", "a4_model_C_time_based")
]


def load_data():
    act, rr, rc = preprocess(
        alpha=ALPHA, beta=BETA,
        x_max=X_MAX, tau_max=TAU_MAX,
        overtime_mult=OVERTIME_MULT, hours_per_day=HOURS_PER_DAY,
    )
    preds, _ = build_predecessors(act, [], True)
    baseline_sched = build_reference_no_crash_schedule(act, rr, rc, preds, CURRENT_DAY, 30.0, 1)
    
    models = {}
    for name, fname, _ in MODEL_NAMES:
        fpath = os.path.join(OUTPUTS_DIR, fname)
        if os.path.exists(fpath):
            with open(fpath, "r", encoding="utf-8") as f:
                data = json.load(f)
                model_map = {}
                for row in data.get("schedule", []):
                    act_id = str(row.get("activity", row.get("task_id", "")))
                    start = float(row.get("optimized_start", row.get("start", 0)))
                    end = float(row.get("optimized_finish", row.get("end", 0)))
                    dur = float(row.get("optimized_duration", row.get("duration", 0)))
                    crash_days = float(row.get("crash_days", 0))
                    if crash_days == 0 and "baseline_duration" in row:
                        crash_days = max(0.0, float(row["baseline_duration"]) - dur)
                    
                    # Extract max x and tau across assignments if present (for Model A / B)
                    max_x = 1.0
                    max_tau = 0.0
                    has_xtau = False
                    if "assignments" in row and isinstance(row["assignments"], list) and len(row["assignments"]) > 0:
                        has_xtau = True
                        for ass in row["assignments"]:
                            max_x = max(max_x, float(ass.get("x", 1.0)))
                            max_tau = max(max_tau, float(ass.get("tau", 0.0)))
                    elif "x" in row or "tau" in row:
                        has_xtau = True
                        max_x = float(row.get("x", 1.0))
                        max_tau = float(row.get("tau", 0.0))
                        
                    task_dict = {
                        "activity": act_id,
                        "start": start,
                        "end": end,
                        "duration": dur,
                        "crash_days": crash_days
                    }
                    if has_xtau:
                        task_dict["max_x"] = max_x
                        task_dict["max_tau"] = max_tau
                    model_map[act_id] = task_dict
                models[name] = model_map
    return act, baseline_sched, models


def get_bar_color(opt_info, current_day):
    if current_day > 0 and opt_info["end"] <= current_day:
        return "#95a5a6", "Completed"  # Grey
    
    crash_days = opt_info.get("crash_days", 0)
    
    # Check if it has x/tau info (Model A / Model B)
    if "max_x" in opt_info or "max_tau" in opt_info:
        max_x = opt_info.get("max_x", 1.0)
        max_tau = opt_info.get("max_tau", 0.0)
        # To avoid GA numerical noise: only crash if x or tau changed significantly (> 0.05) OR crash_days > 0.05
        if (max_x - 1.0 > 0.05) or (max_tau > 0.05):
            return "#e74c3c", "Crashed"
        elif crash_days > 0.05 and (max_x - 1.0 > 0.01 or max_tau > 0.01):
            return "#e74c3c", "Crashed"
        else:
            return "#3498db", "Normal"
    else:
        # For Model C (Time-Based), no x/tau info exists, so crash_days > 0.05 strictly means crashed!
        if crash_days > 0.05:
            return "#e74c3c", "Crashed"
        else:
            return "#3498db", "Normal"


def draw_optimized_bar(ax, y, opt_info, current_day, height=0.55, label=None):
    color, _ = get_bar_color(opt_info, current_day)
    start_val = opt_info["start"]
    end_val = opt_info["end"]
    dur_val = opt_info["duration"]
    if current_day > 0 and start_val < current_day < end_val:
        elapsed_dur = current_day - start_val
        remaining_dur = end_val - current_day
        ax.barh(y, elapsed_dur, left=start_val, height=height, color="#95a5a6", linewidth=0, label=label if label else "_nolegend_")
        ax.barh(y, remaining_dur, left=current_day, height=height, color=color, linewidth=0, label="_nolegend_")
    else:
        ax.barh(y, dur_val, left=start_val, height=height, color=color, linewidth=0, label=label if label else "_nolegend_")


def save_figure(fig, base_filename):
    png_path = os.path.join(OUTPUTS_DIR, f"{base_filename}.png")
    svg_path = os.path.join(OUTPUTS_DIR, f"{base_filename}.svg")
    fig.savefig(png_path, dpi=600, bbox_inches="tight")
    fig.savefig(svg_path, format="svg", bbox_inches="tight")
    print(f"✓ Saved: {png_path} (600 DPI) & .svg")


def generate_individual_models(act, baseline_sched, models):
    """Generate standalone horizontal A4 (11.69" x 8.27") figures for each model."""
    baseline_order = sorted(
        baseline_sched.keys(),
        key=lambda a: (baseline_sched[a]["start"], baseline_sched[a]["end"], a)
    )

    for name, _, out_base in MODEL_NAMES:
        if name not in models:
            continue
        opt_map = models[name]
        
        # Horizontal A4 Paper size minus 1-inch margins on all sides (9.69" x 6.27")
        fig, ax = plt.subplots(figsize=(9.69, 6.27), dpi=600)
        # ax.set_title(name, fontsize=12, weight="bold", pad=3)  # Removed per user request
        
        for y, a in enumerate(baseline_order):
            b_info = baseline_sched[a]
            opt_info = opt_map.get(a, {"start": b_info["start"], "end": b_info["end"], "duration": b_info["duration"], "crash_days": 0})
            
            # Baseline ghost outline (even thinner: linewidth=0.25, darker gray: #555555)
            ax.barh(y, b_info["duration"], left=b_info["start"], height=0.7,
                    color="none", edgecolor="#555555", linestyle="--", linewidth=0.25, alpha=0.85)
            
            # Optimized solid bar (NO black border: linewidth=0)
            draw_optimized_bar(ax, y, opt_info, CURRENT_DAY, height=0.55)

        max_base = max(b["end"] for b in baseline_sched.values())
        ax.axvline(x=CURRENT_DAY, color="#2c3e50", linestyle="--", linewidth=1.0, alpha=0.8)
        ax.axvline(x=T_MAX, color="green", linestyle=":", linewidth=1.2, alpha=0.8)
        ax.axvline(x=max_base, color="#555555", linestyle=":", linewidth=1.0, alpha=0.6)
        
        # Remove activity IDs on the left totally (along with label and ticks)
        ax.set_yticks([])
        ax.set_yticklabels([])
        ax.set_ylabel("")
        
        ax.set_xlabel("Project Day", fontsize=10)
        ax.grid(axis="x", linestyle=":", alpha=0.5)
        ax.set_xlim(0, max_base + 16)
        ax.set_xticks([0, CURRENT_DAY, 100, 175, T_MAX, int(max_base)])
        ax.set_xticklabels(["0", f"$T_0 = {CURRENT_DAY}$", "100", "175", f"$T_{{\\max}} = {T_MAX}$", f"$T_{{\\mathrm{{base}}}} = {int(max_base)}$"])
        ax.set_ylim(len(baseline_order) - 0.5, -0.5)

        legend_elements = [
            mpatches.Patch(facecolor="#3498db", label="Active Tasks", linewidth=0),
            mpatches.Patch(facecolor="#e74c3c", label="Crashed Tasks", linewidth=0),
            mpatches.Patch(facecolor="#95a5a6", label="Completed Tasks", linewidth=0),
            mpatches.Patch(facecolor="none", edgecolor="#555555", linestyle="--", linewidth=0.5, label="Baseline Position")
        ]
        # Legend in 1 single horizontal line left to right (ncol=4)
        fig.legend(handles=legend_elements, loc="lower center", bbox_to_anchor=(0.5, 0.01), ncol=4, frameon=True)
        plt.tight_layout(rect=[0, 0.07, 1, 0.96])
        save_figure(fig, out_base)
        plt.close(fig)


def generate_mockup1_side_by_side(act, baseline_sched, models):
    """Mockup 1: 3-Column Shared Y-Axis in A4 Landscape (9.69" x 6.27" printable area)"""
    fig, axes = plt.subplots(1, 3, sharey=True, figsize=(9.69, 6.27), dpi=600)
    # fig.suptitle("Project Crashing Comparison Across Paradigm Models", fontsize=13, weight="bold", y=0.96)

    baseline_order = sorted(
        baseline_sched.keys(),
        key=lambda a: (baseline_sched[a]["start"], baseline_sched[a]["end"], a)
    )

    for idx, (model_name, _, _) in enumerate(MODEL_NAMES):
        if model_name not in models:
            continue
        opt_map = models[model_name]
        ax = axes[idx]
        # ax.set_title(model_name, fontsize=11, weight="bold", pad=3)  # Removed per user request
        
        for y, a in enumerate(baseline_order):
            b_info = baseline_sched[a]
            opt_info = opt_map.get(a, {"start": b_info["start"], "end": b_info["end"], "duration": b_info["duration"], "crash_days": 0})
            
            # Baseline ghost outline (even thinner: linewidth=0.25, darker gray: #555555)
            ax.barh(y, b_info["duration"], left=b_info["start"], height=0.7,
                    color="none", edgecolor="#555555", linestyle="--", linewidth=0.25, alpha=0.85)
            
            # Optimized solid bar (NO border: linewidth=0)
            draw_optimized_bar(ax, y, opt_info, CURRENT_DAY, height=0.55)

        max_base = max(b["end"] for b in baseline_sched.values())
        ax.axvline(x=CURRENT_DAY, color="#2c3e50", linestyle="--", linewidth=1.0, alpha=0.8)
        ax.axvline(x=T_MAX, color="green", linestyle=":", linewidth=1.2, alpha=0.8)
        ax.axvline(x=max_base, color="#555555", linestyle=":", linewidth=1.0, alpha=0.6)
        ax.set_xlabel("Project Day", fontsize=10)
        ax.grid(axis="x", linestyle=":", alpha=0.5)
        ax.set_xlim(0, max_base + 16)
        ax.set_xticks([0, CURRENT_DAY, 100, 175, T_MAX, int(max_base)])
        ax.set_xticklabels(["0", f"$T_0 = {CURRENT_DAY}$", "100", "175", f"$T_{{\\max}} = {T_MAX}$", f"$T_{{\\mathrm{{base}}}} = {int(max_base)}$"])
        ax.set_ylim(len(baseline_order) - 0.5, -0.5)

        # Remove Y-axis ticks, labels, and IDs totally across all subplots
        ax.set_yticks([])
        ax.set_yticklabels([])
        ax.set_ylabel("")

    legend_elements = [
        mpatches.Patch(facecolor="#3498db", label="Active Tasks", linewidth=0),
        mpatches.Patch(facecolor="#e74c3c", label="Crashed Tasks", linewidth=0),
        mpatches.Patch(facecolor="#95a5a6", label="Completed Tasks", linewidth=0),
        mpatches.Patch(facecolor="none", edgecolor="#555555", linestyle="--", linewidth=0.5, label="Baseline Position")
    ]
    # Legend in 1 single horizontal line left to right (ncol=4)
    fig.legend(handles=legend_elements, loc="lower center", bbox_to_anchor=(0.5, 0.01), ncol=4, frameon=True)
    plt.tight_layout(rect=[0, 0.07, 1, 0.96])
    
    save_figure(fig, "a4_landscape_3model_comparison")
    plt.close(fig)


def generate_mockup2_dual_bar_overlay(act, baseline_sched, models):
    """Mockup 2: 3-Model Stacked Dual-Bar Overlay in A4 Portrait (6.27" x 9.69" printable area)"""
    fig, axes = plt.subplots(3, 1, sharex=True, figsize=(6.27, 9.69), dpi=600)
    # fig.suptitle("Synchronized Dual-Bar Gantt Charts (Baseline Outline vs. Crashed Solid)", fontsize=13, weight="bold", y=0.97)

    baseline_order = sorted(
        baseline_sched.keys(),
        key=lambda a: (baseline_sched[a]["start"], baseline_sched[a]["end"], a)
    )

    for idx, (model_name, _, _) in enumerate(MODEL_NAMES):
        if model_name not in models:
            continue
        opt_map = models[model_name]
        ax = axes[idx]
        # ax.set_title(model_name, fontsize=11, weight="bold", loc="left", pad=3)  # Removed per user request
        
        for y, a in enumerate(baseline_order):
            b_info = baseline_sched[a]
            opt_info = opt_map.get(a, {"start": b_info["start"], "end": b_info["end"], "duration": b_info["duration"], "crash_days": 0})
            
            # Baseline wireframe bar (even thinner: linewidth=0.25, darker gray: #555555)
            ax.barh(y, b_info["duration"], left=b_info["start"], height=0.75,
                    color="#f8f9fa", edgecolor="#555555", linestyle="--", linewidth=0.25, label="_nolegend_")
            
            # Optimized solid bar (NO border: linewidth=0)
            draw_optimized_bar(ax, y, opt_info, CURRENT_DAY, height=0.45, label="_nolegend_")

        max_base = max(b["end"] for b in baseline_sched.values())
        ax.axvline(x=CURRENT_DAY, color="#2c3e50", linestyle="--", linewidth=1.0)
        ax.axvline(x=T_MAX, color="green", linestyle=":", linewidth=1.2)
        ax.axvline(x=max_base, color="#555555", linestyle=":", linewidth=1.0, alpha=0.6)
        
        # Remove activity IDs on the left totally (along with label and ticks)
        ax.set_yticks([])
        ax.set_yticklabels([])
        ax.set_ylabel("")
        
        ax.grid(axis="x", linestyle=":", alpha=0.5)
        ax.set_ylim(len(baseline_order) - 0.5, -0.5)

    axes[2].set_xlabel("Project Day", fontsize=10)
    axes[2].set_xlim(0, max_base + 16)
    axes[2].set_xticks([0, CURRENT_DAY, 100, 175, T_MAX, int(max_base)])
    axes[2].set_xticklabels(["0", f"$T_0 = {CURRENT_DAY}$", "100", "175", f"$T_{{\\max}} = {T_MAX}$", f"$T_{{\\mathrm{{base}}}} = {int(max_base)}$"])

    legend_elements = [
        mpatches.Patch(facecolor="#3498db", label="Active Tasks", linewidth=0),
        mpatches.Patch(facecolor="#e74c3c", label="Crashed Tasks", linewidth=0),
        mpatches.Patch(facecolor="#95a5a6", label="Completed Tasks", linewidth=0),
        mpatches.Patch(facecolor="none", edgecolor="#555555", linestyle="--", linewidth=0.5, label="Baseline Position")
    ]
    # Legend in 1 single horizontal line left to right (ncol=4)
    fig.legend(handles=legend_elements, loc="lower center", bbox_to_anchor=(0.5, 0.01), ncol=4, frameon=True)
    plt.tight_layout(rect=[0, 0.06, 1, 0.96])
    
    save_figure(fig, "a4_portrait_diff_overlay")
    plt.close(fig)


def generate_mockup3_compact_track_packed(act, baseline_sched, models):
    """Mockup 3: Resource/Interval Packed Gantt in A4 Landscape (9.69" x 6.27" printable area)"""
    fig, axes = plt.subplots(3, 1, sharex=True, figsize=(9.69, 6.27), dpi=600)
    # fig.suptitle("Compact Track-Packed Gantt Charts (Non-overlapping tasks share rows)", fontsize=13, weight="bold", y=0.96)

    for idx, (model_name, _, _) in enumerate(MODEL_NAMES):
        if model_name not in models:
            continue
        opt_map = models[model_name]
        ax = axes[idx]
        # ax.set_title(model_name, fontsize=11, weight="bold", loc="left", pad=3)  # Removed per user request
        
        sorted_acts = sorted(opt_map.values(), key=lambda row: (row["start"], -row["duration"], row["activity"]))
        tracks = []
        act_track_map = {}
        
        for row in sorted_acts:
            a = row["activity"]
            s, e = row["start"], row["end"]
            placed = False
            for t_idx, t_end in enumerate(tracks):
                if s >= t_end:
                    tracks[t_idx] = e
                    act_track_map[a] = t_idx
                    placed = True
                    break
            if not placed:
                act_track_map[a] = len(tracks)
                tracks.append(e)
                
        num_tracks = len(tracks)
        
        for row in sorted_acts:
            a = row["activity"]
            s, d, e = row["start"], row["duration"], row["end"]
            t_idx = act_track_map[a]
            
            draw_optimized_bar(ax, t_idx, row, CURRENT_DAY, height=0.65)

        max_base = max(b["end"] for b in baseline_sched.values())
        ax.axvline(x=CURRENT_DAY, color="#2c3e50", linestyle="--", linewidth=1.0)
        ax.axvline(x=T_MAX, color="green", linestyle=":", linewidth=1.2)
        ax.axvline(x=max_base, color="#555555", linestyle=":", linewidth=1.0, alpha=0.6)
        
        # Remove activity IDs on the left totally (along with label and ticks)
        ax.set_yticks([])
        ax.set_yticklabels([])
        ax.set_ylabel("")
        
        ax.grid(axis="x", linestyle=":", alpha=0.5)
        ax.set_ylim(num_tracks - 0.5, -0.5)

    axes[2].set_xlabel("Project Day", fontsize=10)
    axes[2].set_xlim(0, max_base + 16)
    axes[2].set_xticks([0, CURRENT_DAY, 100, 175, T_MAX, int(max_base)])
    axes[2].set_xticklabels(["0", f"$T_0 = {CURRENT_DAY}$", "100", "175", f"$T_{{\\max}} = {T_MAX}$", f"$T_{{\\mathrm{{base}}}} = {int(max_base)}$"])

    legend_elements = [
        mpatches.Patch(facecolor="#3498db", label="Active Tasks", linewidth=0),
        mpatches.Patch(facecolor="#e74c3c", label="Crashed Tasks", linewidth=0),
        mpatches.Patch(facecolor="#95a5a6", label="Completed Tasks", linewidth=0),
        mpatches.Patch(facecolor="none", edgecolor="#555555", linestyle="--", linewidth=0.5, label="Baseline Position")
    ]
    # Legend in 1 single horizontal line left to right (ncol=4)
    fig.legend(handles=legend_elements, loc="lower center", bbox_to_anchor=(0.5, 0.01), ncol=4, frameon=True)
    plt.tight_layout(rect=[0, 0.07, 1, 0.96])
    
    save_figure(fig, "a4_compact_track_gantt")
    plt.close(fig)


if __name__ == "__main__":
    print("Generating publication-quality A4 Gantt charts (600 DPI & SVG) ...")
    act, baseline_sched, models = load_data()
    if not models:
        print("Error: No solution JSON files found in outputs/comparison/single/!")
        sys.exit(1)
    generate_individual_models(act, baseline_sched, models)
    generate_mockup1_side_by_side(act, baseline_sched, models)
    generate_mockup2_dual_bar_overlay(act, baseline_sched, models)
    generate_mockup3_compact_track_packed(act, baseline_sched, models)
    print("Done! All academic figures generated successfully in PNG (600 DPI) and SVG formats.")
