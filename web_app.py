#!/usr/bin/env python3
"""
Property Assessment Web App
============================
A lightweight Flask web interface for on-demand property assessment.
Paste any Domain.com.au URL → full financial analysis in ~60 seconds.

Deploy to Railway (or any Docker host):
  railway up

Local:
  PROPERTY_DATA_DIR=/tmp/propdata python3 web_app.py
"""

import asyncio
import json
import os
import sys
import threading
import uuid
from datetime import datetime
from pathlib import Path

from flask import Flask, jsonify, render_template_string, request

# ── Configure data dir ────────────────────────────────────────────────────────
os.environ.setdefault('PROPERTY_DATA_DIR', '/tmp/propdata')
Path(os.environ['PROPERTY_DATA_DIR']).mkdir(parents=True, exist_ok=True)

# PERSIST_ASSESSMENTS=true  → ad-hoc assessments save to JSON + rebuild dashboard (NAS/Docker)
# PERSIST_ASSESSMENTS=false → stateless, results returned only (Railway/Vercel)
PERSIST = os.environ.get('PERSIST_ASSESSMENTS', 'false').lower() == 'true'

# Import the scraper (BASE_DIR now reads from env var set above)
sys.path.insert(0, str(Path(__file__).parent))
import scraper_full  # noqa: E402

app = Flask(__name__)

# In-memory job store (sufficient for single-instance deployments)
jobs: dict[str, dict] = {}

# ── HTML template ─────────────────────────────────────────────────────────────
HTML = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Property Assessor</title>
<style>
  :root {
    --blue:#1a73e8; --navy:#0d2137; --green:#1e8449; --red:#c0392b;
    --amber:#d4680a; --lgrey:#f5f6f8; --border:#e2e6ea; --radius:12px;
    --shadow:0 2px 10px rgba(0,0,0,.08);
  }
  * { box-sizing:border-box; margin:0; padding:0; }
  body { font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif;
         background:var(--lgrey); color:#1a1a2e; min-height:100vh; }
  .header { background:var(--navy); color:white; padding:18px 32px;
            display:flex; align-items:center; gap:14px; }
  .header h1 { font-size:20px; font-weight:700; letter-spacing:-.3px; }
  .header span { font-size:13px; color:rgba(255,255,255,.6); }
  .content { max-width:900px; margin:32px auto; padding:0 20px; }
  .card { background:white; border-radius:var(--radius); box-shadow:var(--shadow);
          padding:28px 32px; margin-bottom:20px; }
  .card h2 { font-size:16px; font-weight:700; color:var(--navy);
             margin-bottom:16px; }
  .input-row { display:flex; gap:10px; }
  .input-row input { flex:1; padding:12px 16px; border-radius:8px;
                     border:1.5px solid var(--border); font-size:14px; }
  .input-row input:focus { outline:none; border-color:var(--blue); }
  .btn { background:var(--blue); color:white; border:none; border-radius:8px;
         padding:12px 24px; font-size:14px; font-weight:700; cursor:pointer;
         white-space:nowrap; transition:background .15s; }
  .btn:hover:not(:disabled) { background:#1557b0; }
  .btn:disabled { background:#aaa; cursor:default; }
  .btn.danger { background:var(--red); }
  /* progress */
  .progress { margin-top:18px; display:none; }
  .spinner { display:inline-block; width:16px; height:16px; border:2px solid #ccc;
             border-top-color:var(--blue); border-radius:50%;
             animation:spin .7s linear infinite; vertical-align:middle; margin-right:8px; }
  @keyframes spin { to { transform:rotate(360deg); } }
  .log-box { background:var(--lgrey); border-radius:8px; padding:14px 16px;
             font-family:monospace; font-size:12px; white-space:pre-wrap;
             max-height:160px; overflow-y:auto; margin-top:12px; color:#444; }
  /* result */
  #result { display:none; }
  .result-header { display:flex; justify-content:space-between; align-items:flex-start;
                   margin-bottom:20px; flex-wrap:wrap; gap:12px; }
  .result-title { font-size:22px; font-weight:800; color:var(--navy); }
  .result-sub { font-size:14px; color:#666; margin-top:4px; }
  .metrics { display:grid; grid-template-columns:repeat(auto-fill,minmax(160px,1fr));
             gap:12px; margin-bottom:20px; }
  .metric { background:var(--lgrey); border-radius:10px; padding:14px 16px; }
  .metric .label { font-size:10px; font-weight:700; text-transform:uppercase;
                   letter-spacing:.7px; color:#888; margin-bottom:5px; }
  .metric .value { font-size:22px; font-weight:800; color:var(--navy); }
  .metric .sub { font-size:11px; color:#888; margin-top:3px; }
  .metric.hi { background:#e8f4fd; }
  .metric.hi .value { color:var(--blue); }
  .metric.good { background:#eafaf1; }
  .metric.good .value { color:var(--green); }
  .metric.warn { background:#fef9e7; }
  .metric.warn .value { color:var(--amber); }
  .metric.bad { background:#fdedec; }
  .metric.bad .value { color:var(--red); }
  .tags { display:flex; flex-wrap:wrap; gap:8px; margin-bottom:18px; }
  .tag { border-radius:20px; padding:4px 12px; font-size:12px; font-weight:600; }
  .tag.g  { background:#d5f5e3; color:#1e8449; }
  .tag.r  { background:#fadbd8; color:#922b21; }
  .tag.a  { background:#fdebd0; color:#935116; }
  .tag.b  { background:#d6eaf8; color:#1a5276; }
  .tag.gr { background:#eaecee; color:#566573; }
  table { width:100%; border-collapse:collapse; font-size:13px; }
  th { background:var(--navy); color:white; padding:9px 12px;
       text-align:left; font-weight:600; }
  td { padding:8px 12px; border-bottom:1px solid var(--border); }
  tr:nth-child(even) td { background:#fafbfc; }
  .c { text-align:right; }
  .domain-link { color:var(--blue); text-decoration:none; font-weight:600;
                 font-size:13px; }
  .domain-link:hover { text-decoration:underline; }
  .error-box { background:#fdedec; border-radius:10px; padding:18px 20px;
               color:var(--red); font-size:14px; margin-top:16px; display:none; }
  @media(max-width:600px) {
    .content { padding:0 12px; }
    .card { padding:20px 16px; }
    .input-row { flex-direction:column; }
  }
</style>
</head>
<body>

<div class="header">
  <div>
    <h1>🏠 Property Assessor</h1>
    <span>Instant financial analysis for Australian investment properties</span>
  </div>
</div>

<div class="content">

  <!-- Input card -->
  <div class="card">
    <h2>Assess a Property</h2>
    <div class="input-row">
      <input type="url" id="urlInput"
             placeholder="Paste a Domain.com.au listing URL  e.g. https://www.domain.com.au/2020685507"
             onkeydown="if(event.key==='Enter') assess()">
      <button class="btn" id="assessBtn" onclick="assess()">Assess →</button>
    </div>
    <div class="progress" id="progress">
      <span class="spinner"></span>
      <span id="progressMsg">Scraping Domain.com.au and property.com.au — usually takes 30–60 seconds…</span>
      <div class="log-box" id="logBox"></div>
    </div>
    <div class="error-box" id="errorBox"></div>
  </div>

  <!-- Result card -->
  <div class="card" id="result">
    <div class="result-header">
      <div>
        <div class="result-title" id="rAddress"></div>
        <div class="result-sub" id="rSub"></div>
      </div>
      <a id="rLink" href="#" target="_blank" class="domain-link">View on Domain.com.au ↗</a>
    </div>

    <div class="tags" id="rTags"></div>
    <div class="metrics" id="rMetrics"></div>

    <h2 style="margin-bottom:12px">Year-by-Year Cash Flow</h2>
    <div style="overflow-x:auto">
      <table id="rTable">
        <thead>
          <tr>
            <th>Year</th>
            <th class="c">Rent/Wk</th>
            <th class="c">Gross Income</th>
            <th class="c">Expenses</th>
            <th class="c">Interest</th>
            <th class="c">Net Cash</th>
            <th class="c">After-Tax $/Wk</th>
            <th class="c">Property Value</th>
            <th class="c">Equity</th>
          </tr>
        </thead>
        <tbody id="rTableBody"></tbody>
      </table>
    </div>
  </div>

</div>

<script>
let pollTimer = null;

function fmt(n) {
  if (n == null) return '—';
  return '$' + Math.round(n).toLocaleString();
}
function pct(n) {
  if (n == null) return '—';
  return n.toFixed(2) + '%';
}

async function assess() {
  const url = document.getElementById('urlInput').value.trim();
  if (!url) { alert('Please paste a Domain.com.au URL'); return; }

  document.getElementById('assessBtn').disabled = true;
  document.getElementById('progress').style.display = 'block';
  document.getElementById('result').style.display = 'none';
  document.getElementById('errorBox').style.display = 'none';
  document.getElementById('logBox').textContent = '';

  let resp, data;
  try {
    resp = await fetch('/assess', {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({url})
    });
    data = await resp.json();
  } catch(e) {
    showError('Network error: ' + e.message);
    return;
  }

  if (!data.job_id) { showError(data.error || 'Unknown error'); return; }
  pollResult(data.job_id);
}

function pollResult(jobId) {
  clearTimeout(pollTimer);
  pollTimer = setInterval(async () => {
    try {
      const r = await fetch('/result/' + jobId);
      const d = await r.json();
      if (d.log) document.getElementById('logBox').textContent = d.log;
      if (d.status === 'done') {
        clearInterval(pollTimer);
        showResult(d.result);
      } else if (d.status === 'error') {
        clearInterval(pollTimer);
        showError(d.error || 'Assessment failed');
      }
    } catch(e) { /* keep polling */ }
  }, 3000);
}

function showError(msg) {
  document.getElementById('assessBtn').disabled = false;
  document.getElementById('progress').style.display = 'none';
  const box = document.getElementById('errorBox');
  box.style.display = 'block';
  box.textContent = '✗ ' + msg;
}

function showResult(p) {
  document.getElementById('assessBtn').disabled = false;
  document.getElementById('progress').style.display = 'none';
  document.getElementById('result').style.display = 'block';

  // Header
  document.getElementById('rAddress').textContent = p.address + ', ' + (p.suburb || '');
  document.getElementById('rSub').textContent =
    [p.bedrooms && p.bedrooms + ' bed',
     p.bathrooms && p.bathrooms + ' bath',
     p.land_size_m2 && p.land_size_m2 + 'm²',
     p.build_year_est && 'Built ' + p.build_year_est]
    .filter(Boolean).join('  ·  ');
  const link = document.getElementById('rLink');
  link.href = p.domain_url || '#';

  // Tags
  const tags = [];
  const risk = p.risk_label || 'Unknown';
  const riskCls = risk === 'Low' ? 'g' : risk === 'Moderate' ? 'a' : 'r';
  tags.push([risk + ' Risk', riskCls]);
  if (p.currently_tenanted === true)  tags.push(['✓ Tenanted', 'g']);
  if (p.currently_tenanted === false) tags.push(['Vacant', 'gr']);
  if (p.flood_overlay)    tags.push(['Flood Overlay', 'r']);
  if (p.bushfire_overlay) tags.push(['Bushfire Overlay', 'a']);
  if (p.nbn_available)    tags.push(['NBN Available', 'g']);
  if (p.rent_source === 'domain_appraisal') tags.push(['Rent Appraised', 'g']);
  if (p.manually_added)   tags.push(['Manual Entry', 'b']);
  document.getElementById('rTags').innerHTML =
    tags.map(([t, c]) => `<span class="tag ${c}">${t}</span>`).join('');

  // Metric cards
  const v = p.yr1_aftertax_cashflow_pw || 0;
  const cfCls = v >= 0 ? 'good' : v > -50 ? 'warn' : 'bad';
  const irr = p.irr || 0;
  const irrCls = irr >= 12 ? 'good' : irr >= 9 ? 'hi' : irr >= 6 ? 'warn' : 'bad';
  const metrics = [
    ['Purchase Price', fmt(p.purchase_price), p.price_display || '', 'hi'],
    ['PropTrack Est.', fmt(p.proptrack_estimate),
     p.proptrack_gap > 0 ? '+' + fmt(p.proptrack_gap) + ' above ask' :
     p.proptrack_gap < 0 ? fmt(Math.abs(p.proptrack_gap)) + ' below ask' : '', 'hi'],
    ['Weekly Rent', '$' + (p.weekly_rent || '—') + '/wk',
     p.rent_source?.replace(/_/g,' ') || '', 'hi'],
    ['Gross Yield', pct(p.gross_yield), 'before vacancies', ''],
    ['10-Yr IRR', pct(irr), 'annualised total return', irrCls],
    ['After-Tax $/Wk', (v >= 0 ? '+$' : '-$') + Math.abs(v) + '/wk',
     'Year 1 holding cost', cfCls],
    ['10-Yr Equity', fmt(p.total_equity_yr10), 'at ' + (p.cap_growth_rate_used || 7) + '% growth', 'good'],
    ['NPV @ 7%', fmt(p.npv_7pct || p.npv_at_7pct), 'net present value', ''],
    ['Total Upfront', fmt(p.total_upfront), 'deposit + stamp duty + legal', ''],
  ];
  document.getElementById('rMetrics').innerHTML = metrics.map(([lbl, val, sub, cls]) =>
    `<div class="metric ${cls}">
       <div class="label">${lbl}</div>
       <div class="value">${val}</div>
       ${sub ? `<div class="sub">${sub}</div>` : ''}
     </div>`
  ).join('');

  // Year-by-year table
  const yrs = p.yearly_data || [];
  document.getElementById('rTableBody').innerHTML = yrs.map(y => `
    <tr>
      <td>${y.year}</td>
      <td class="c">$${Math.round(y.weekly_rent || 0)}</td>
      <td class="c">${fmt(y.gross_income)}</td>
      <td class="c">${fmt(y.total_expenses)}</td>
      <td class="c">${fmt(y.interest)}</td>
      <td class="c">${fmt(y.net_cashflow)}</td>
      <td class="c">${(y.aftertax_pw >= 0 ? '+$' : '-$') + Math.abs(Math.round(y.aftertax_pw || 0))}/wk</td>
      <td class="c">${fmt(y.property_value)}</td>
      <td class="c">${fmt(y.equity)}</td>
    </tr>`).join('');

  document.getElementById('result').scrollIntoView({behavior:'smooth', block:'start'});
}
</script>
</body>
</html>"""


# ── Routes ─────────────────────────────────────────────────────────────────────

@app.route('/')
def index():
    return render_template_string(HTML)


@app.route('/assess', methods=['POST'])
def assess():
    body = request.get_json(silent=True) or {}
    url = (body.get('url') or '').strip()
    if not url:
        return jsonify({'error': 'url is required'}), 400

    job_id = str(uuid.uuid4())
    jobs[job_id] = {
        'status': 'running',
        'result': None,
        'error': None,
        'log': '',
        'started': datetime.now().isoformat(),
    }

    def worker():
        # Capture log output via the log_sink hook in scraper_full
        log_lines = []

        def capture_log(line):
            log_lines.append(line)
            jobs[job_id]['log'] = '\n'.join(log_lines)

        scraper_full.log_sink = capture_log
        try:
            result = asyncio.run(scraper_full.run_single(url, persist=PERSIST))
            jobs[job_id].update({'status': 'done', 'result': result,
                                  'log': '\n'.join(log_lines)})
        except Exception as e:
            jobs[job_id].update({'status': 'error', 'error': str(e),
                                  'log': '\n'.join(log_lines)})
        finally:
            scraper_full.log_sink = None

    threading.Thread(target=worker, daemon=True).start()
    return jsonify({'job_id': job_id})


@app.route('/result/<job_id>')
def result(job_id):
    job = jobs.get(job_id)
    if not job:
        return jsonify({'error': 'Job not found'}), 404
    return jsonify(job)


@app.route('/health')
def health():
    return jsonify({'ok': True, 'time': datetime.now().isoformat()})


# ── Entry point ────────────────────────────────────────────────────────────────
if __name__ == '__main__':
    port = int(os.environ.get('PORT', 8080))
    debug = os.environ.get('FLASK_DEBUG', '0') == '1'
    print(f'\nProperty Assessor  →  http://localhost:{port}\n')
    app.run(host='0.0.0.0', port=port, debug=debug, threaded=True)
