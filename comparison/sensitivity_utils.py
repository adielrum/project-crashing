import os
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

# Standardized New Computer Modern / CMU Serif typography
plt.rcParams.update({
    "font.family": "serif",
    "font.serif": ["CMU Serif", "cmr10", "Computer Modern", "Times New Roman", "DejaVu Serif"],
    "font.size": 9,
    "axes.labelsize": 9,
    "axes.titlesize": 9,
    "xtick.labelsize": 8,
    "ytick.labelsize": 8,
    "legend.fontsize": 8,
    "mathtext.fontset": "cm",
    "axes.formatter.use_mathtext": True
})

def plot_dual_axis_oat(df, param_col, title, out_path, param_label=None, show_ms_label=True, show_cost_label=True, ylim_ms=None, ylim_cost=None):
    """
    Plots a standardized 50% A4 width (3.14 x 2.15 inches) dual Y-axis OAT chart.
    Supports sharing Y-limits and suppressing left/right labels for clean side-by-side manuscript layouts.
    """
    fig, ax1 = plt.subplots(figsize=(3.14, 2.15), dpi=600)
    
    cost_col = 'total_cost' if 'total_cost' in df.columns else ('net_cost' if 'net_cost' in df.columns else 'cost')
    y_vals_1e6 = df[cost_col] / 1e6
    color_cost = 'tab:red'
    
    ax1.set_xlabel(param_label if param_label else param_col)
    if show_cost_label:
        ax1.set_ylabel(r"Total Cost ($\times 10^6$ USD)" if cost_col == 'total_cost' else r"Net Project Cost ($\times 10^6$ USD)", color=color_cost)
        ax1.tick_params(axis='y', labelcolor=color_cost, labelleft=True)
    else:
        ax1.set_ylabel("")
        ax1.tick_params(axis='y', labelcolor=color_cost, labelleft=False)
        
    ax1.plot(df[param_col], y_vals_1e6, color=color_cost, marker='o', linewidth=1.4, markersize=3.8)
    ax1.tick_params(axis='x')
    if ylim_cost is not None:
        ax1.set_ylim(ylim_cost)
        
    ax2 = ax1.twinx()
    color_ms = 'tab:blue'
    if show_ms_label:
        ax2.set_ylabel(r"Optimal Makespan (days)", color=color_ms)
        ax2.tick_params(axis='y', labelcolor=color_ms, labelright=True)
    else:
        ax2.set_ylabel("")
        ax2.tick_params(axis='y', labelcolor=color_ms, labelright=False)
        
    ax2.plot(df[param_col], df['makespan'], color=color_ms, marker='s', linestyle='--', linewidth=1.4, markersize=3.8)
    if ylim_ms is not None:
        ax2.set_ylim(ylim_ms)
        
    ax1.grid(True, linestyle=':', alpha=0.55)
    
    fig.tight_layout()
    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    plt.savefig(out_path, dpi=600, bbox_inches="tight")
    svg_path = os.path.splitext(out_path)[0] + ".svg"
    plt.savefig(svg_path, bbox_inches="tight")
    plt.close(fig)
    print(f"  -> Saved dual-axis OAT plot: {out_path} & .svg")


def plot_2panel_contour_heatmap(df, x_col, y_col, out_path, title_prefix="", x_label=None, y_label=None, is_bonus_penalty=False):
    """
    Plots a unified 2-panel side-by-side square heatmap with 100% A4 width (6.27") and tight horizontal top colorbars.
    - Left: Makespan (Days) with viridis colormap and smoothed white contours
    - Right: Total/Net Cost ($\times 10^6$ USD) with coolwarm colormap and smoothed white contours
    Both subplots enforce aspect=1.0 for exact 1:1 geometric square presentation.
    """
    pivot_makespan = df.pivot(index=y_col, columns=x_col, values='makespan')
    
    cost_col = 'net_cost' if 'net_cost' in df.columns else ('total_cost' if 'total_cost' in df.columns else 'total_crash_cost')
    pivot_cost = df.pivot(index=y_col, columns=x_col, values=cost_col) / 1e6
    
    extent = [
        df[x_col].min(), df[x_col].max(),
        df[y_col].min(), df[y_col].max()
    ]
    
    fig, axes = plt.subplots(1, 2, figsize=(6.27, 3.15), dpi=600)
    
    # Left Panel: Makespan (Exact Square: aspect=1.0)
    im1 = axes[0].imshow(
        pivot_makespan.values, 
        extent=extent, 
        origin='lower', 
        cmap='viridis', 
        aspect=1.0,
        interpolation='bicubic'
    )
    axes[0].set_xlabel(x_label if x_label else x_col)
    axes[0].set_ylabel(y_label if y_label else y_col)
    
    cbar1 = fig.colorbar(im1, ax=axes[0], location='top', pad=0.035, shrink=0.92)
    cbar1.set_label(r"Optimal Makespan (days)", labelpad=4, fontsize=9)
    cbar1.ax.tick_params(labelsize=7.5, pad=2)
    
    # White Contours for Makespan (with coordinate smoothing to eliminate micro-loop artifacts)
    try:
        from scipy.ndimage import gaussian_filter
        Z_ms_smooth = gaussian_filter(pivot_makespan.values, sigma=0.6)
        X, Y = np.meshgrid(pivot_makespan.columns, pivot_makespan.index)
        CS1 = axes[0].contour(X, Y, Z_ms_smooth, colors='white', linewidths=0.85, alpha=0.85)
        axes[0].clabel(CS1, inline=True, fontsize=7.5, fmt='%d')
    except Exception as e:
        pass
        
    # Right Panel: Cost (Exact Square: aspect=1.0 with unified coolwarm colormap)
    im2 = axes[1].imshow(
        pivot_cost.values, 
        extent=extent, 
        origin='lower', 
        cmap='coolwarm', 
        aspect=1.0,
        interpolation='bicubic'
    )
    axes[1].set_xlabel(x_label if x_label else x_col)
    axes[1].set_ylabel(y_label if y_label else y_col)
    
    cbar2 = fig.colorbar(im2, ax=axes[1], location='top', pad=0.035, shrink=0.92)
    cost_label_str = r"Net Project Cost ($\times 10^6$ USD)" if is_bonus_penalty else r"Total Cost ($\times 10^6$ USD)"
    cbar2.set_label(cost_label_str, labelpad=4, fontsize=9)
    cbar2.ax.tick_params(labelsize=7.5, pad=2)
    
    # White Contours for Cost (with coordinate smoothing)
    try:
        from scipy.ndimage import gaussian_filter
        Z_cost_smooth = gaussian_filter(pivot_cost.values, sigma=0.6)
        CS2 = axes[1].contour(X, Y, Z_cost_smooth, colors='white', linewidths=0.85, alpha=0.85)
        axes[1].clabel(CS2, inline=True, fontsize=7.5, fmt='%.2f')
    except Exception as e:
        pass
        
    plt.subplots_adjust(wspace=0.32, hspace=0.25)
    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    plt.savefig(out_path, dpi=600, bbox_inches="tight")
    svg_path = os.path.splitext(out_path)[0] + ".svg"
    plt.savefig(svg_path, bbox_inches="tight")
    plt.close(fig)
    print(f"  -> Saved 2-panel contour heatmap: {out_path} & .svg")


def plot_pareto_shifts(df, param_col, title, out_path, param_label=None, ylim_shared=None, show_ylabel=True):
    """
    Plots standardized 50% A4 width (3.14 x 2.15 inches) multi-objective 2D Pareto Front curves.
    Features sparse markers (markevery=step) on smooth continuous lines, shared Y-scaling, and optional Y-label suppression.
    """
    fig, ax = plt.subplots(figsize=(3.14, 2.15), dpi=600)
    
    colors = ['tab:red', 'tab:green', 'tab:blue', 'tab:purple', 'tab:orange']
    markers = ['o', 's', '^', 'D', 'v']
    
    vals = sorted(df[param_col].unique())
    y_col = 'labor_cost' if 'labor_cost' in df.columns else ('total_cost' if 'total_cost' in df.columns else 'cost')
    
    for i, v in enumerate(vals):
        subset = df[df[param_col] == v].sort_values(by='makespan').reset_index(drop=True)
        if subset.empty:
            continue
        label_str = f"{param_label if param_label else param_col} = {v}"
        y_vals_1e6 = subset[y_col] / 1e6
        step = max(1, len(subset) // 13)
        ax.plot(
            subset['makespan'], y_vals_1e6, 
            marker=markers[i % len(markers)], color=colors[i % len(colors)], 
            linewidth=1.4, markersize=3.8, markevery=step, label=label_str
        )
        
    ax.set_xlabel(r"Optimal Makespan (days)")
    if show_ylabel:
        ax.set_ylabel(r"Labor Cost ($\times 10^6$ USD)" if y_col == 'labor_cost' else r"Total Cost ($\times 10^6$ USD)")
        ax.tick_params(axis='y', labelleft=True)
    else:
        ax.set_ylabel("")
        ax.tick_params(axis='y', labelleft=False)
        
    if ylim_shared is not None:
        ax.set_ylim(ylim_shared)
        
    ax.legend(loc='upper right', frameon=True, facecolor="white", edgecolor="none")
    ax.grid(True, linestyle=':', alpha=0.55)
    
    fig.tight_layout()
    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    plt.savefig(out_path, dpi=600, bbox_inches="tight")
    svg_path = os.path.splitext(out_path)[0] + ".svg"
    plt.savefig(svg_path, bbox_inches="tight")
    plt.close(fig)
    print(f"  -> Saved Pareto shift plot: {out_path} & .svg")
