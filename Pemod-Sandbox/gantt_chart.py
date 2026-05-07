import matplotlib.pyplot as plt
import matplotlib.dates as mdates
from datetime import datetime
import pandas as pd
import numpy as np

df = pd.read_csv('Schedules_CSV/Task_Table.csv')

df['Start_dt'] = pd.to_datetime(df['Start'], format='%d %B %Y %I:%M %p')
df['Finish_dt'] = pd.to_datetime(df['Finish'], format='%d %B %Y %I:%M %p')

level_colors = {
    0: '#1f77b4',
    1: '#2ca02c',
    2: '#ff7f0e'
}

fig, ax = plt.subplots(figsize=(24, 40))

for idx, row in df.iterrows():
    level = row['Outline Level']
    color = level_colors.get(level, '#9467bd')
    
    duration = (row['Finish_dt'] - row['Start_dt']).days
    
    ax.barh(idx, duration, left=row['Start_dt'], color=color, height=0.6, edgecolor='black', linewidth=0.3)
    
    if level == 0:
        ax.barh(idx, duration, left=row['Start_dt'], color='none', height=0.6, edgecolor='black', linewidth=2)

ax.set_yticks(range(len(df)))
ax.set_yticklabels(df['Name'], fontsize=8)

ax.xaxis.set_major_formatter(mdates.DateFormatter('%b %Y'))
ax.xaxis.set_major_locator(mdates.MonthLocator(interval=2))
plt.xticks(rotation=45, ha='right')

ax.set_xlabel('Date', fontsize=12)
ax.set_ylabel('Task', fontsize=12)
ax.set_title('Construction Project Gantt Chart\n(Colors: Level 0=Blue, Level 1=Green, Level 2=Orange)', fontsize=16)

ax.set_xlim(df['Start_dt'].min() - pd.Timedelta(days=10), df['Finish_dt'].max() + pd.Timedelta(days=10))

legend_elements = [
    plt.Rectangle((0, 0), 1, 1, facecolor=level_colors[0], edgecolor='black', label='Outline Level 0'),
    plt.Rectangle((0, 0), 1, 1, facecolor=level_colors[1], edgecolor='black', label='Outline Level 1'),
    plt.Rectangle((0, 0), 1, 1, facecolor=level_colors[2], edgecolor='black', label='Outline Level 2'),
]
ax.legend(handles=legend_elements, loc='upper right')

ax.grid(axis='x', alpha=0.3)

plt.tight_layout()
plt.savefig('gantt_chart.png', dpi=150, bbox_inches='tight')
plt.savefig('gantt_chart.pdf', bbox_inches='tight')
print("Gantt chart saved as gantt_chart.png and gantt_chart.pdf")
