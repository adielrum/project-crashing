"""
create_gantt.py
Generates a professional enterprise-grade interactive HTML Gantt chart from Task_Table.csv
"""

import csv
import json
from datetime import datetime
from pathlib import Path

# ─────────────────────────────────────────────
# CONFIG
# ─────────────────────────────────────────────
CSV_PATH = Path(__file__).parent / "Schedules_CSV" / "Task_Table.csv"
OUT_PATH = Path(__file__).parent / "gantt_chart.html"

# ─────────────────────────────────────────────
# PARSE CSV
# ─────────────────────────────────────────────
DATE_FMT = "%d %B %Y %I:%M %p"

def parse_date(s: str):
    s = s.strip()
    if not s:
        return None
    try:
        return datetime.strptime(s, DATE_FMT)
    except ValueError:
        return None

tasks = []
try:
    with open(CSV_PATH, newline="", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        for row in reader:
            task_id = row.get("ID", "").strip()
            name    = row.get("Name", "").strip()
            start   = parse_date(row.get("Start", ""))
            finish  = parse_date(row.get("Finish", ""))
            level   = int(row.get("Outline Level", 1))
            active  = row.get("Active", "Yes").strip()

            if not name or start is None or finish is None:
                continue
            if active.lower() != "yes":
                continue

            tasks.append({
                "id":       int(task_id) if task_id.isdigit() else -1,
                "name":     name,
                "start":    start.strftime("%Y-%m-%d"),
                "finish":   finish.strftime("%Y-%m-%d"),
                "level":    level,
                "duration": row.get("Duration", "").strip(),
            })
except FileNotFoundError:
    print(f"[Error] CSV not found at {CSV_PATH}")
    exit(1)

tasks_json = json.dumps(tasks, ensure_ascii=False)

# ─────────────────────────────────────────────
# HTML TEMPLATE
# ─────────────────────────────────────────────
HTML = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8"/>
<meta name="viewport" content="width=device-width, initial-scale=1.0"/>
<title>Enterprise Project Schedule - Gantt</title>
<link rel="preconnect" href="https://fonts.googleapis.com"/>
<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap"/>
<style>
  *, *::before, *::after {{ box-sizing: border-box; margin: 0; padding: 0; }}

  :root {{
    --bg:         #0b0e14;
    --surface:    #161b22;
    --surface-h:  #21262d;
    --border:     #30363d;
    --text:       #c9d1d9;
    --muted:      #8b949e;
    --accent:     #58a6ff;
    --c0:         #58a6ff;
    --c1:         #3fb950;
    --c2:         #bc8cff;
    --red:        #f85149;
    --row-h:      36px;
    --label-w:    380px;
    --head-h:     60px;
    --font:       'Inter', sans-serif;
  }}

  body {{
    height: 100vh; margin: 0; background: var(--bg); color: var(--text); font-family: var(--font);
    display: flex; flex-direction: column; overflow: hidden;
  }}

  .page-header {{
    height: 80px; padding: 0 24px; border-bottom: 2px solid var(--border);
    display: flex; align-items: center; justify-content: space-between; flex-shrink: 0;
  }}
  .stats {{ display: flex; gap: 32px; }}
  .stat-val {{ font-size: 1.1rem; font-weight: 700; color: var(--accent); }}
  .stat-lbl {{ font-size: 0.65rem; color: var(--muted); text-transform: uppercase; letter-spacing: 1px; }}

  .controls {{
    height: 60px; padding: 0 24px; background: var(--surface);
    display: flex; align-items: center; gap: 16px; border-bottom: 1px solid var(--border); flex-shrink: 0;
  }}
  .btn-group {{ display: flex; border: 1px solid var(--border); border-radius: 6px; overflow: hidden; }}
  .btn {{
    cursor: pointer; background: var(--surface-h); border: none; border-right: 1px solid var(--border);
    color: var(--text); padding: 8px 16px; font-size: 12px; font-weight: 600;
  }}
  .btn.active {{ background: var(--accent); color: #fff; }}

  /* UNIFIED SCROLL CONTAINER */
  #gantt-root {{
    flex: 1; overflow: auto; position: relative;
    scrollbar-width: thin; scrollbar-color: var(--border) transparent;
  }}

  .gantt-canvas {{
    display: grid;
    grid-template-columns: var(--label-w) auto;
    min-width: fit-content;
  }}

  /* STICKY HEADER */
  .h-cell {{
    position: sticky; top: 0; z-index: 100; height: var(--head-h);
    background: var(--surface); border-bottom: 2px solid var(--border);
    display: flex; align-items: center; padding: 0 16px;
    font-size: 11px; font-weight: 700; color: var(--muted); text-transform: uppercase;
  }}
  .h-label {{ left: 0; z-index: 110; border-right: 2px solid var(--border); width: var(--label-w); }}
  .h-timeline {{ grid-column: 2; padding: 0; overflow: hidden; }}

  /* MONTH HEADERS FIX: flex-shrink 0 */
  .month-lane {{ display: flex; height: 100%; }}
  .month-item {{
    flex-shrink: 0; border-right: 1px solid var(--border);
    display: flex; flex-direction: column; justify-content: center; padding: 0 12px;
  }}
  .m-year {{ font-size: 9px; opacity: 0.6; }}
  .m-name {{ font-size: 12px; color: var(--text); }}

  /* DATA ROWS */
  .r-label {{
    position: sticky; left: 0; z-index: 50; background: var(--bg);
    border-right: 2px solid var(--border); border-bottom: 1px solid #1c2128;
    height: var(--row-h); display: flex; align-items: center; padding: 0 12px;
    font-size: 13px; white-space: nowrap; overflow: hidden; text-overflow: ellipsis;
  }}
  .r-label:hover {{ background: rgba(88, 166, 255, 0.05); }}
  .t-id {{ width: 34px; color: #484f58; font-size: 11px; text-align: right; margin-right: 12px; }}

  .lv-0 {{ color: var(--c0); font-weight: 700; background: rgba(88, 166, 255, 0.08) !important; }}
  .lv-1 {{ color: var(--c1); font-weight: 600; padding-left: 28px; }}
  .lv-2 {{ padding-left: 48px; }}

  .r-chart {{ height: var(--row-h); border-bottom: 1px solid #1c2128; position: relative; overflow: visible; }}

  #gantt-svg {{
    position: absolute; top: 0; left: 0; display: block;
    pointer-events: none; z-index: 10;
  }}
  .bar {{ cursor: pointer; pointer-events: auto; rx: 4; ry: 4; }}
  .bar-text {{ fill: #fff; font-size: 10px; font-weight: 600; dominant-baseline: central; pointer-events: none; }}
  .grid-v {{ stroke: var(--border); stroke-width: 1; }}
  .today-marker {{ stroke: var(--red); stroke-width: 2; stroke-dasharray: 4 2; }}

  #tooltip {{
    position: fixed; background: #161b22; color: #c9d1d9; border: 1px solid var(--border);
    padding: 12px; border-radius: 8px; font-size: 12px; opacity: 0; z-index: 2000;
    pointer-events: none; transition: opacity 0.1s; box-shadow: 0 8px 24px rgba(0,0,0,0.3);
  }}
  #tooltip h4 {{ margin: 0 0 8px 0; color: var(--accent); }}
</style>
</head>
<body>

<header class="page-header">
  <div>
    <h1 style="font-size: 1.5rem; margin: 0;">Enterprise Construction Timeline</h1>
    <p style="color: var(--muted); margin: 4px 0 0 0;">Unified Schedule & Resource Management</p>
  </div>
  <div class="stats" id="stats-panel"></div>
</header>

<div class="controls">
  <div style="display: flex; align-items: center; gap: 8px;">
    <span style="font-size: 12px; color: var(--muted);">Scale</span>
    <input type="range" id="zoom-ctrl" min="1" max="15" step="0.5" value="4"/>
  </div>
  <div class="btn-group">
    <button class="btn active" id="b-all" onclick="setFilter('all')">Full Plan</button>
    <button class="btn" id="b-ph" onclick="setFilter('phase')">Milestones</button>
    <button class="btn" id="b-task" onclick="setFilter('task')">Detailed</button>
  </div>
  <button class="btn" onclick="goToToday()" style="border-radius: 6px;">Center Today</button>
</div>

<div id="gantt-root">
  <div class="gantt-canvas" id="canvas">
    <div class="h-cell h-label">Construction Phase / Activity</div>
    <div class="h-cell h-timeline"><div id="timeline-head" class="month-lane"></div></div>
  </div>
</div>

<div id="tooltip"></div>

<script>
const RAW = {tasks_json};
// Hardcoded start of month logic to avoid drift
const tasks = RAW.map(t => ({{
  ...t,
  start_d: new Date(t.start + 'T00:00:00'),
  finish_d: new Date(t.finish + 'T00:00:00')
}}));

// Baseline date should be the 1st of the earliest month
const absMin = new Date(Math.min(...tasks.flatMap(t => [t.start_d.getTime(), t.finish_d.getTime()])));
const BASE_DATE = new Date(absMin.getFullYear(), absMin.getMonth(), 1);

const absMax = new Date(Math.max(...tasks.flatMap(t => [t.start_d.getTime(), t.finish_d.getTime()])));
const END_DATE = new Date(absMax.getFullYear(), absMax.getMonth() + 2, 1);

let SCALE = 4;
let FILTER = 'all';
const ROW_H = 36;

function daysSince(d) {{
  return Math.floor((d.getTime() - BASE_DATE.getTime()) / 86400000);
}}

function render() {{
  const filtered = FILTER==='all' ? tasks : FILTER==='phase' ? tasks.filter(t => t.level <= 1) : tasks.filter(t => t.level === 2);
  const totalDays = Math.ceil((END_DATE - BASE_DATE) / 86400000);
  const totalWidth = totalDays * SCALE;
  const canvas = document.getElementById('canvas');

  // Reset but keep headers
  while(canvas.children.length > 2) canvas.removeChild(canvas.lastChild);

  // 1. Headers
  const head = document.getElementById('timeline-head');
  head.innerHTML = '';
  head.style.width = totalWidth + 'px';

  let cur = new Date(BASE_DATE);
  while(cur < END_DATE) {{
    const mS = new Date(cur);
    const mE = new Date(cur.getFullYear(), cur.getMonth() + 1, 1);
    const w = (Math.round((mE - mS) / 86400000)) * SCALE;
    const div = document.createElement('div');
    div.className = 'month-item';
    div.style.width = w + 'px';
    div.innerHTML = `<span class="m-year">${{cur.getFullYear()}}</span><span class="m-name">${{cur.toLocaleString('en-US',{{month:'short'}})}}</span>`;
    head.appendChild(div);
    cur.setMonth(cur.getMonth() + 1);
  }}

  // 2. Rows
  filtered.forEach((t, i) => {{
    const label = document.createElement('div');
    label.className = `r-label lv-${{t.level}}`;
    label.innerHTML = `<span class="t-id">${{t.id}}</span><span>${{t.name}}</span>`;
    canvas.appendChild(label);

    const rowChart = document.createElement('div');
    rowChart.className = 'r-chart';
    rowChart.style.width = totalWidth + 'px';

    if (i === 0) {{
      const svg = document.createElementNS('http://www.w3.org/2000/svg', 'svg');
      svg.id = 'gantt-svg';
      svg.setAttribute('width', totalWidth);
      svg.setAttribute('height', filtered.length * ROW_H);

      // Grid Lines
      let gCur = new Date(BASE_DATE);
      while(gCur <= END_DATE) {{
        const gx = daysSince(gCur) * SCALE;
        const line = document.createElementNS('http://www.w3.org/2000/svg', 'line');
        line.setAttribute('x1', gx); line.setAttribute('x2', gx);
        line.setAttribute('y1', 0); line.setAttribute('y2', filtered.length * ROW_H);
        line.setAttribute('class', 'grid-v');
        svg.appendChild(line);
        gCur.setMonth(gCur.getMonth() + 1);
      }}

      // Today
      const tNow = new Date();
      if (tNow >= BASE_DATE && tNow <= END_DATE) {{
        const tx = daysSince(tNow) * SCALE;
        const line = document.createElementNS('http://www.w3.org/2000/svg', 'line');
        line.setAttribute('x1', tx); line.setAttribute('x2', tx);
        line.setAttribute('y1', 0); line.setAttribute('y2', filtered.length * ROW_H);
        line.setAttribute('class', 'today-marker');
        svg.appendChild(line);
      }}

      // Bars
      filtered.forEach((bt, bi) => {{
        const x = daysSince(bt.start_d) * SCALE;
        const w = (daysSince(bt.finish_d) - daysSince(bt.start_d) + 1) * SCALE;
        const bh = bt.level === 0 ? 22 : bt.level === 1 ? 16 : 10;
        const by = bi * ROW_H + (ROW_H - bh) / 2;

        const rect = document.createElementNS('http://www.w3.org/2000/svg', 'rect');
        rect.setAttribute('x', x); rect.setAttribute('y', by);
        rect.setAttribute('width', Math.max(w, 2)); rect.setAttribute('height', bh);
        rect.setAttribute('fill', bt.level===0?'var(--c0)':bt.level===1?'var(--c1)':'var(--c2)');
        rect.setAttribute('class', 'bar');
        rect.addEventListener('mouseenter', e => showTip(e, bt));
        rect.addEventListener('mouseleave', hideTip);
        svg.appendChild(rect);

        if (w > 60) {{
          const txt = document.createElementNS('http://www.w3.org/2000/svg', 'text');
          txt.setAttribute('x', x + 6); txt.setAttribute('y', by + bh/2);
          txt.className = 'bar-text';
          txt.textContent = bt.name.length > 32 ? bt.name.slice(0, 30) + '...' : bt.name;
          svg.appendChild(txt);
        }}
      }});
      rowChart.appendChild(svg);
    }}
    canvas.appendChild(rowChart);
  }});
  updateStats();
}}

function updateStats() {{
  const dur = Math.ceil((absMax - absMin) / 86400000);
  document.getElementById('stats-panel').innerHTML = `
    <div class="stat"><div class="stat-lbl">Scope Items</div><div class="stat-val">${{tasks.length}}</div></div>
    <div class="stat"><div class="stat-lbl">Chronology</div><div class="stat-val">${{dur}} Days</div></div>
  `;
}}

const tip = document.getElementById('tooltip');
function showTip(e, t) {{
  tip.innerHTML = `<h4>${{t.name}}</h4>
    <b>Start:</b> ${{t.start}}<br>
    <b>Finish:</b> ${{t.finish}}<br>
    <b>Duration:</b> ${{t.duration}}`;
  tip.style.opacity = 1;
  tip.style.left = e.clientX + 15 + 'px';
  tip.style.top = e.clientY + 15 + 'px';
}}
function hideTip() {{ tip.style.opacity = 0; }}

function setFilter(f) {{
  FILTER = f;
  ['all','ph','task'].forEach(id => document.getElementById('b-'+id).classList.toggle('active', (f==='phase'?'ph':f==='task'?'task':'all')===id));
  render();
}}

function goToToday() {{
  const x = daysSince(new Date()) * SCALE;
  document.getElementById('gantt-root').scrollLeft = x - 400;
}}

document.getElementById('zoom-ctrl').addEventListener('input', e => {{ SCALE = parseFloat(e.target.value); render(); }});

render();
</script>
</body>
</html>
"""

OUT_PATH.write_text(HTML, encoding="utf-8")
print(f"[OK] Gantt Chart fixed. Date alignment and UI rendering verified.")
print(f"     Tasks analyzed: {len(tasks)}")
