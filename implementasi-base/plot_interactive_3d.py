import os
import pandas as pd
import numpy as np
import plotly.graph_objects as go

base_dir = os.path.dirname(os.path.abspath(__file__))
csv_path = os.path.join(base_dir, "../outputs/sensitivity_analysis/grid_base_bonus_penalty_100x100.csv")
out_dir = os.path.join(base_dir, "../outputs/sensitivity_analysis")

if not os.path.exists(csv_path):
    raise FileNotFoundError(f"Data file not found: {csv_path}")

print(f"Loading data from {csv_path}...")
df = pd.read_csv(csv_path)

# Pivot results for 3D surface plotting
pivot_makespan = df.pivot(index='c_late', columns='c_early', values='makespan')
pivot_crash_cost = df.pivot(index='c_late', columns='c_early', values='total_crash_cost')
pivot_net_cost = df.pivot(index='c_late', columns='c_early', values='net_cost')

# Coordinates
x_early = pivot_makespan.columns.values
y_late = pivot_makespan.index.values

# Create interactive 3D plot
fig = go.Figure()

# Add Surface for Makespan (visible by default)
fig.add_trace(go.Surface(
    z=pivot_makespan.values,
    x=x_early,
    y=y_late,
    colorscale='Viridis',
    colorbar=dict(title="Days", x=-0.1),
    name='Makespan',
    visible=True
))

# Add Surface for Total Crash Cost (hidden by default)
fig.add_trace(go.Surface(take
    z=pivot_crash_cost.values,
    x=x_early,
    y=y_late,
    colorscale='Plasma',
    colorbar=dict(title="Cost ($)", x=-0.1),
    name='Total Crash Cost',
    visible=False
))

# Add Surface for Net Project Cost (hidden by default)
fig.add_trace(go.Surface(
    z=pivot_net_cost.values,
    x=x_early,
    y=y_late,
    colorscale='RdBu',
    reversescale=True,
    colorbar=dict(title="Net Cost ($)", x=-0.1),
    name='Net Project Cost',
    visible=False
))

# Update layout with dropdown and axis titles
fig.update_layout(
    title='Interactive 3D Sensitivity Analysis (Base Model)',
    scene=dict(
        xaxis_title='Early Bonus (c_early)',
        yaxis_title='Late Penalty (c_late)',
        zaxis_title='Makespan (days)',
        camera=dict(
            eye=dict(x=1.8, y=1.8, z=1.2)
        )
    ),
    updatemenus=[
        dict(
            active=0,
            buttons=list([
                dict(
                    label="Makespan (Days)",
                    method="update",
                    args=[{"visible": [True, False, False]},
                          {"scene.zaxis.title.text": "Makespan (days)"}]
                ),
                dict(
                    label="Total Crash Cost ($)",
                    method="update",
                    args=[{"visible": [False, True, False]},
                          {"scene.zaxis.title.text": "Crash Cost ($)"}]
                ),
                dict(
                    label="Net Project Cost ($)",
                    method="update",
                    args=[{"visible": [False, False, True]},
                          {"scene.zaxis.title.text": "Net Cost ($)"}]
                ),
            ]),
            direction="down",
            pad={"r": 10, "t": 10},
            showactive=True,
            x=0.1,
            xanchor="left",
            y=1.15,
            yanchor="top"
        ),
    ],
    width=1000,
    height=800
)

html_path = os.path.join(out_dir, "grid_base_bonus_penalty_3d.html")
fig.write_html(html_path)
print(f"Interactive 3D Plotly chart saved to {html_path}")
