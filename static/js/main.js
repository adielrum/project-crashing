// Pre-computed trade-off curve (from optimization_results_v2.json)
window._staticTradeoff = {
  data: [{
    type: 'scatter', mode: 'lines+markers',
    name: 'Crash extra cost (pre-computed)',
    x: [379,384,389,394,399,404,409,414,419,424,429],
    y: [37517,29275,23053,17780,13080,10554,9033,7644,6402,5240,4064],
    hovertemplate: 'T=%{x}, cost=$%{y:,.0f}<extra></extra>',
    line: {color: '#636efa'},
    marker: {size: 8}
  }],
  layout: {
    title: 'Time-Cost Trade-off Curve (pre-computed, α=0.7, β=0.7)',
    xaxis: {title: 'Target Project End Day'},
    yaxis: {title: 'Crash Extra Cost ($)'},
    height: 500,
    annotations: [{
      text: 'Pre-computed with default parameters. Enable "Build trade-off curve" for live data.',
      xref: 'paper', yref: 'paper', x: 0.5, y: -0.15,
      showarrow: false, font: {size: 11, color: '#888'}
    }]
  }
};

// Tabs
document.querySelectorAll('.tab').forEach(btn => {
  btn.addEventListener('click', () => {
    document.querySelectorAll('.tab').forEach(b => b.classList.remove('active'));
    document.querySelectorAll('.tab-panel').forEach(p => p.classList.remove('active'));
    btn.classList.add('active');
    document.getElementById(btn.dataset.tab).classList.add('active');
    // Re-trigger plotly resize
    window.dispatchEvent(new Event('resize'));
  });
});

// Render static tradeoff on page load
if (window._staticTradeoff) {
  Plotly.newPlot('tradeoff-chart', window._staticTradeoff.data,
                 window._staticTradeoff.layout, {responsive: true});
}

// Fetch original Gantt on page load
async function fetchOriginalGantt() {
  try {
    const res = await fetch('/original_gantt');
    const data = await res.json();
    if (data.success && data.original_gantt_fig) {
      Plotly.newPlot('original-gantt-chart', data.original_gantt_fig.data, data.original_gantt_fig.layout,
                     {responsive: true});
    }
  } catch (err) {
    console.error("Failed to fetch original Gantt:", err);
  }
}
fetchOriginalGantt();

const form = document.getElementById('opt-form');
const status = document.getElementById('status');
const runBtn = document.getElementById('run-btn');

form.addEventListener('submit', async (e) => {
  e.preventDefault();
  const fd = new FormData(form);
  const payload = {};
  for (const [k, v] of fd.entries()) payload[k] = v;
  payload.hard_deadline = fd.has('hard_deadline');
  payload.tradeoff = fd.has('tradeoff');

  runBtn.disabled = true;
  runBtn.textContent = 'Running...';
  status.textContent = 'Solving...';
  const t0 = performance.now();

  try {
    const res = await fetch('/run', {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify(payload)
    });
    const data = await res.json();
    const elapsed = ((performance.now() - t0) / 1000).toFixed(1);

    if (!data.success) {
      status.textContent = `FAILED (${elapsed}s)\n${data.error || data.status || ''}`;
      return;
    }

    status.textContent = `OK (${elapsed}s)\nSolver: ${data.solver}\nMakespan: ${data.makespan.toFixed(1)}d`;

    // Metrics
    const metrics = document.getElementById('metrics');
    metrics.innerHTML = '';
    const fmtMoney = v => '$' + (v||0).toLocaleString('en-US', {maximumFractionDigits: 0});
    const cards = [
      ['Solver', data.solver],
      ['Makespan', `${data.makespan.toFixed(1)} d`],
      ['Baseline cost', fmtMoney(data.baseline_cost)],
      ['Crash extra', fmtMoney(data.crash_cost)],
      ['Late', `${(data.I_late||0).toFixed(1)} d`],
      ['Early', `${(data.I_early||0).toFixed(1)} d`],
      ['Deadline term', fmtMoney(data.deadline_term||0)],
      ['Crashed tasks', Object.keys(data.crash_plan||{}).length],
    ];
    for (const [l, v] of cards) {
      const div = document.createElement('div');
      div.className = 'metric';
      div.innerHTML = `<div class="label">${l}</div><div class="value">${v}</div>`;
      metrics.appendChild(div);
    }

    // Gantt
    if (data.gantt_fig) {
      Plotly.newPlot('gantt-chart', data.gantt_fig.data, data.gantt_fig.layout,
                     {responsive: true});
    }

    // Tradeoff
    if (data.tradeoff_fig) {
      Plotly.newPlot('tradeoff-chart', data.tradeoff_fig.data, data.tradeoff_fig.layout,
                     {responsive: true});
    } else if (window._staticTradeoff) {
      Plotly.newPlot('tradeoff-chart', window._staticTradeoff.data,
                     window._staticTradeoff.layout, {responsive: true});
    } else {
      document.getElementById('tradeoff-chart').innerHTML =
        '<p style="color:#888;">Trade-off curve not computed. Enable the option or see the pre-computed curve above.</p>';
    }

    // Crash plan table
    const cc = document.getElementById('crash-content');
    if (data.crash_plan && Object.keys(data.crash_plan).length) {
      let html = '<table class="crash-table"><thead><tr>'
        + '<th>Task</th><th>Resource</th><th>x</th><th>τ (h)</th>'
        + '<th>+Cost</th><th>Days saved</th></tr></thead><tbody>';
      for (const [task, entries] of Object.entries(data.crash_plan)) {
        for (const e of entries) {
          html += `<tr><td>${task}</td><td>${e.resource}</td>`
            + `<td>${e.x}</td><td>${e.tau}</td>`
            + `<td>${fmtMoney(e.cost_delta)}</td>`
            + `<td>${e.duration_saved.toFixed(1)}</td></tr>`;
        }
      }
      html += '</tbody></table>';
      cc.innerHTML = html;
    } else {
      cc.innerHTML = '<p style="color:#888;">No crashing applied.</p>';
    }

    // Resource load
    if (data.resload_fig) {
      Plotly.newPlot('resload-chart', data.resload_fig.data, data.resload_fig.layout,
                     {responsive: true});
    }

  } catch (err) {
    status.textContent = `ERROR\n${err.message}`;
  } finally {
    runBtn.disabled = false;
    runBtn.textContent = '▶ Run optimizer';
  }
});
