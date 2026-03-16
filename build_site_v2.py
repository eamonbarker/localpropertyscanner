#!/usr/bin/env python3
"""Build the HTML dashboard from property_data.json (v2 — full enriched data)."""
import json, sys, os
from pathlib import Path

# Accept args: data_path output_path
data_path = sys.argv[1] if len(sys.argv) > 1 else '/sessions/stoic-elegant-wright/property_data.json'
out_path  = sys.argv[2] if len(sys.argv) > 2 else '/sessions/stoic-elegant-wright/mnt/Investment Properties/property_analysis.html'

with open(data_path) as f:
    raw = json.load(f)

# Support both old format (list) and new format (dict with meta/properties)
if isinstance(raw, list):
    props_data = raw
    meta = {'generated_display': 'March 2026', 'total_found': len(raw), 'suburbs_searched': ['Pimpama','Upper Coomera']}
    assump = {'deposit_pct':0.20,'interest_rate':0.062,'cap_growth_rate':0.07,'rental_growth':0.04,
              'vacancy_rate':0.04,'pm_rate':0.085,'marginal_rate_eamon':0.47,'marginal_rate_nadeene':0.45,
              'avg_marginal':0.46,'cgt_discount':0.50,'selling_costs_pct':0.025,
              'buyers':'Eamon & Nadeene','structure':'50/50 Tenants in Common'}
    output = {'meta': meta, 'assumptions': assump, 'properties': props_data}
else:
    output = raw
    props_data = raw.get('properties', [])
    meta = raw.get('meta', {})
    assump = raw.get('assumptions', {})

data_json = json.dumps(output, indent=None, separators=(',',':'), default=str)

html = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Investment Property Analysis — Northern Gold Coast 2026</title>
<script src="https://cdnjs.cloudflare.com/ajax/libs/Chart.js/4.4.1/chart.umd.min.js"></script>
<style>
  :root {{
    --navy:#1F3864; --blue:#2E75B6; --lblue:#D5E8F0; --lgrey:#f4f5f7;
    --green:#1a7a4a; --lgreen:#e2efda; --amber:#b8860b; --lamber:#fff3cd;
    --red:#c0392b; --lred:#fde8e6; --white:#fff; --text:#1a1a2e;
    --border:#dde1e7; --radius:10px; --shadow:0 2px 12px rgba(0,0,0,.08);
  }}
  * {{ box-sizing:border-box; margin:0; padding:0; }}
  body {{ font-family:'Segoe UI',Arial,sans-serif; background:#f0f2f5; color:var(--text); font-size:14px; }}

  .site-header {{ background:var(--navy); color:white; padding:16px 32px; display:flex; align-items:center; justify-content:space-between; flex-wrap:wrap; gap:8px; }}
  .site-header .title {{ font-size:20px; font-weight:700; }}
  .site-header .sub {{ font-size:12px; opacity:.7; margin-top:2px; }}
  .badge {{ background:var(--blue); padding:4px 12px; border-radius:20px; font-size:12px; font-weight:600; }}
  .updated {{ font-size:11px; opacity:.55; margin-top:3px; }}

  .nav {{ background:white; border-bottom:2px solid var(--border); display:flex; padding:0 24px; gap:0; overflow-x:auto; position:sticky; top:0; z-index:100; }}
  .nav-btn {{ padding:13px 18px; border:none; background:none; cursor:pointer; font-size:13px; font-weight:500; color:#666; border-bottom:3px solid transparent; transition:all .2s; white-space:nowrap; }}
  .nav-btn:hover {{ color:var(--blue); }}
  .nav-btn.active {{ color:var(--navy); border-bottom-color:var(--blue); font-weight:700; }}

  .content {{ max-width:1500px; margin:24px auto; padding:0 24px; }}
  .page {{ display:none; }}
  .page.active {{ display:block; }}

  .cards {{ display:grid; grid-template-columns:repeat(auto-fit,minmax(190px,1fr)); gap:14px; margin-bottom:24px; }}
  .card {{ background:white; border-radius:var(--radius); padding:18px 20px; box-shadow:var(--shadow); border-top:4px solid var(--blue); }}
  .card.green {{ border-top-color:var(--green); }}
  .card.amber {{ border-top-color:var(--amber); }}
  .card.red   {{ border-top-color:var(--red); }}
  .card.navy  {{ border-top-color:var(--navy); }}
  .card-label {{ font-size:10px; font-weight:700; text-transform:uppercase; letter-spacing:.8px; color:#888; margin-bottom:5px; }}
  .card-value {{ font-size:24px; font-weight:700; color:var(--navy); line-height:1.1; }}
  .card-sub   {{ font-size:11px; color:#777; margin-top:5px; }}
  .card-value.pos {{ color:var(--green); }} .card-value.neg {{ color:var(--red); }}

  .section-title {{ font-size:17px; font-weight:700; color:var(--navy); margin:24px 0 12px; padding-bottom:7px; border-bottom:2px solid var(--lblue); display:flex; align-items:center; gap:10px; }}
  .section-title .pill {{ font-size:10px; font-weight:700; background:var(--lblue); color:var(--blue); padding:2px 10px; border-radius:12px; text-transform:uppercase; letter-spacing:.4px; }}

  .tbl-wrap {{ overflow-x:auto; border-radius:var(--radius); box-shadow:var(--shadow); background:white; margin-bottom:24px; }}
  table {{ width:100%; border-collapse:collapse; }}
  th {{ background:var(--navy); color:white; padding:10px 12px; text-align:left; font-size:11px; font-weight:700; letter-spacing:.4px; white-space:nowrap; }}
  th.c, td.c {{ text-align:center; }}
  td {{ padding:9px 12px; border-bottom:1px solid var(--border); font-size:12px; white-space:nowrap; }}
  tr:hover td {{ background:#f8f9ff; }}
  tr:last-child td {{ border-bottom:none; }}
  .sec-row td {{ background:var(--blue); color:white; font-weight:700; font-size:10px; text-transform:uppercase; letter-spacing:.5px; padding:6px 12px; }}
  .hi-row td {{ background:var(--lgreen); font-weight:600; }}
  .hi-row.am td {{ background:var(--lamber); }}
  .sub-row td {{ background:var(--lblue); font-weight:600; }}

  .chip {{ display:inline-flex; align-items:center; gap:4px; padding:2px 8px; border-radius:10px; font-size:11px; font-weight:700; }}
  .chip.g {{ background:var(--lgreen); color:var(--green); }}
  .chip.a {{ background:var(--lamber); color:var(--amber); }}
  .chip.r {{ background:var(--lred); color:var(--red); }}
  .chip.b {{ background:var(--lblue); color:var(--blue); }}
  .chip.n {{ background:var(--navy); color:white; }}
  .chip.gr {{ background:#e8e8e8; color:#555; }}

  .risk-dot {{ width:8px; height:8px; border-radius:50%; display:inline-block; margin-right:3px; }}
  .risk-low {{ background:var(--green); }} .risk-mod {{ background:var(--amber); }} .risk-high {{ background:var(--red); }}

  .chart-grid {{ display:grid; grid-template-columns:1fr 1fr; gap:18px; margin-bottom:24px; }}
  .chart-grid.w {{ grid-template-columns:1fr; }}
  .chart-box {{ background:white; border-radius:var(--radius); padding:18px; box-shadow:var(--shadow); }}
  .chart-box h3 {{ font-size:13px; font-weight:700; color:var(--navy); margin-bottom:14px; }}
  .chart-box canvas {{ max-height:280px; }}

  .inner-tabs {{ display:flex; gap:4px; margin-bottom:18px; flex-wrap:wrap; }}
  .inner-tab {{ padding:7px 16px; border-radius:8px; border:none; cursor:pointer; font-size:12px; font-weight:600; background:white; color:#666; transition:all .15s; box-shadow:0 1px 4px rgba(0,0,0,.08); }}
  .inner-tab.active {{ background:var(--blue); color:white; }}
  .inner-tab:hover:not(.active) {{ background:var(--lblue); }}

  .prop-header {{ background:white; border-radius:var(--radius); padding:20px 24px; box-shadow:var(--shadow); margin-bottom:20px; }}
  .prop-header .row1 {{ display:flex; align-items:flex-start; justify-content:space-between; flex-wrap:wrap; gap:12px; }}
  .prop-header h2 {{ font-size:20px; font-weight:700; color:var(--navy); margin:8px 0 3px; }}
  .prop-header .meta {{ font-size:13px; color:#666; }}
  .prop-header .pills {{ display:flex; gap:6px; flex-wrap:wrap; margin-top:8px; }}
  .domain-btn {{ background:var(--blue); color:white; padding:9px 18px; border-radius:8px; text-decoration:none; font-weight:600; font-size:12px; display:inline-block; }}
  .domain-btn:hover {{ background:var(--navy); }}

  .risk-banner {{ border-radius:8px; padding:10px 16px; margin-bottom:16px; font-size:13px; font-weight:600; display:flex; align-items:center; gap:10px; }}
  .risk-banner.low {{ background:var(--lgreen); color:var(--green); border-left:4px solid var(--green); }}
  .risk-banner.mod {{ background:var(--lamber); color:var(--amber); border-left:4px solid var(--amber); }}
  .risk-banner.high {{ background:var(--lred); color:var(--red); border-left:4px solid var(--red); }}

  .assump-note {{ background:var(--lamber); border-left:4px solid var(--amber); padding:10px 14px; border-radius:0 8px 8px 0; font-size:12px; color:#555; margin-bottom:18px; }}

  .sens-grid {{ display:grid; grid-template-columns:repeat(auto-fill,minmax(150px,1fr)); gap:10px; margin:12px 0 24px; }}
  .sens-cell {{ background:white; border-radius:8px; padding:12px; box-shadow:var(--shadow); text-align:center; }}
  .sens-cell.base {{ border:2px solid var(--blue); }}
  .sens-cell .s-label {{ font-size:10px; color:#888; margin-bottom:3px; }}
  .sens-cell .s-val {{ font-size:17px; font-weight:700; }}

  select {{ padding:7px 11px; border-radius:8px; border:1px solid var(--border); font-size:13px; color:var(--text); background:white; cursor:pointer; }}

  .desc-box {{ background:var(--lgrey); border-radius:8px; padding:12px 16px; font-size:12px; color:#444; line-height:1.6; margin:12px 0; border-left:3px solid var(--blue); }}

  .sticky-col {{ position:sticky; left:0; background:white; z-index:1; }}
  tr:hover .sticky-col {{ background:#f8f9ff; }}

  .new-badge {{ background:#e8f5e9; color:#1a7a4a; border:1px solid #a5d6a7; padding:1px 6px; border-radius:8px; font-size:10px; font-weight:700; margin-left:4px; }}

  @media(max-width:768px) {{ .chart-grid {{ grid-template-columns:1fr; }} .cards {{ grid-template-columns:1fr 1fr; }} .content {{ padding:0 10px; }} }}

  /* ── Filter bar ── */
  .filter-bar {{ background:white; border-radius:var(--radius); padding:14px 20px; box-shadow:var(--shadow); margin-bottom:18px; display:flex; flex-wrap:wrap; gap:16px; align-items:flex-end; }}
  .f-item {{ display:flex; flex-direction:column; gap:5px; }}
  .f-item > label {{ font-size:10px; font-weight:700; text-transform:uppercase; letter-spacing:.7px; color:#888; }}
  .f-range-row {{ display:flex; align-items:center; gap:8px; }}
  .f-range-row input[type=range] {{ accent-color:var(--blue); width:130px; cursor:pointer; }}
  .f-val {{ font-size:13px; font-weight:700; color:var(--navy); min-width:52px; }}
  .f-item select {{ padding:6px 10px; border-radius:8px; border:1px solid var(--border); font-size:13px; color:var(--text); background:white; cursor:pointer; }}
  .suburb-pills {{ display:flex; flex-wrap:wrap; gap:4px; max-width:520px; }}
  .s-pill {{ background:var(--lgrey); border:1.5px solid var(--border); border-radius:12px; padding:3px 10px; font-size:11px; font-weight:600; cursor:pointer; user-select:none; transition:all .15s; }}
  .s-pill.on {{ background:var(--blue); color:white; border-color:var(--blue); }}
  .f-count {{ font-size:12px; color:#888; white-space:nowrap; padding-bottom:2px; }}
  .f-reset {{ background:none; border:1.5px solid var(--border); border-radius:8px; padding:6px 14px; font-size:12px; font-weight:600; color:#666; cursor:pointer; transition:all .15s; white-space:nowrap; }}
  .f-reset:hover {{ background:var(--lgrey); color:var(--navy); }}

  .sc-control {{ background:white; border-radius:var(--radius); padding:16px 18px; box-shadow:var(--shadow); }}
  .sc-control label {{ display:block; font-size:11px; font-weight:700; text-transform:uppercase; letter-spacing:.6px; color:#888; margin-bottom:6px; }}
  .sc-control .sc-row {{ display:flex; align-items:center; gap:10px; }}
  .sc-control input[type=range] {{ flex:1; accent-color:var(--blue); }}
  .sc-control .sc-val {{ font-size:15px; font-weight:700; color:var(--navy); min-width:60px; text-align:right; }}
  .sc-control input[type=number] {{ width:110px; padding:6px 10px; border-radius:6px; border:1px solid var(--border); font-size:14px; font-weight:600; color:var(--navy); }}
  .prop-override-row {{ display:grid; grid-template-columns:220px 1fr 1fr; gap:12px; align-items:center; background:white; border-radius:8px; padding:12px 16px; box-shadow:var(--shadow); margin-bottom:8px; }}
  .prop-override-row .pname {{ font-size:13px; font-weight:700; color:var(--navy); }}
  .prop-override-row .psuburb {{ font-size:11px; color:#888; }}
  .override-field {{ display:flex; flex-direction:column; gap:4px; }}
  .override-field label {{ font-size:10px; font-weight:700; text-transform:uppercase; letter-spacing:.5px; color:#888; }}
  .override-field input {{ padding:6px 10px; border-radius:6px; border:1px solid var(--border); font-size:14px; font-weight:600; color:var(--navy); width:140px; }}
</style>
</head>
<body>

<header class="site-header">
  <div>
    <div class="title">🏠 Investment Property Analysis</div>
    <div class="sub">Gold Coast · Ipswich · Logan — Pimpama · Coomera · Ormeau · Helensvale · Ripley · Yarrabilba · Redbank Plains + more</div>
  </div>
  <div style="text-align:right">
    <div class="badge">Eamon &amp; Nadeene · 50/50 TIC</div>
    <div class="updated" id="lastUpdated">Loading...</div>
  </div>
</header>

<nav class="nav" id="mainNav">
  <button class="nav-btn active" onclick="showPage('overview',this)">📊 Overview</button>
  <button class="nav-btn" onclick="showPage('comparison',this)">📈 10-Year Projections</button>
  <button class="nav-btn" onclick="showPage('detail',this)">🏡 Property Deep-Dive</button>
  <button class="nav-btn" onclick="showPage('risk',this)">⚠️ Risk &amp; Overlays</button>
  <button class="nav-btn" onclick="showPage('assumptions',this)">⚙️ Assumptions</button>
  <button class="nav-btn" onclick="showPage('scenario',this)">🎛 Scenario Planner</button>
</nav>

<div class="content">

<!-- ═══════════════════════════════════════ OVERVIEW ═══ -->
<div id="page-overview" class="page active">
  <div class="cards" id="overviewCards"></div>
  <div id="filterBar" class="filter-bar"></div>
  <div class="section-title">Ranked Shortlist <span class="pill" id="rankingPill">Sorted by 10-Year IRR · Click property name to deep-dive</span></div>
  <div class="tbl-wrap"><table id="rankingTable"></table></div>
  <div class="chart-grid">
    <div class="chart-box"><h3>10-Year IRR by Property</h3><canvas id="irrChart"></canvas></div>
    <div class="chart-box"><h3>After-Tax Holding Cost ($/week, Year 1)</h3><canvas id="cfChart"></canvas></div>
  </div>
  <div class="chart-grid">
    <div class="chart-box"><h3>Year-10 Equity vs Loan Balance</h3><canvas id="equityChart"></canvas></div>
    <div class="chart-box"><h3>Gross vs Net Yield</h3><canvas id="yieldChart"></canvas></div>
  </div>
</div>

<!-- ══════════════════════════════ 10-YEAR PROJECTIONS ═══ -->
<div id="page-comparison" class="page">
  <div class="section-title">All Properties — 10-Year Projections</div>
  <div class="chart-grid w">
    <div class="chart-box"><h3>Property Value vs Loan Balance (I/O stays flat)</h3><canvas id="valueChart" style="max-height:340px"></canvas></div>
  </div>
  <div class="chart-grid">
    <div class="chart-box"><h3>Equity Growth</h3><canvas id="eqLineChart"></canvas></div>
    <div class="chart-box"><h3>Cumulative After-Tax Cash Flow</h3><canvas id="cumCFChart"></canvas></div>
  </div>
  <div class="chart-grid">
    <div class="chart-box"><h3>Total Wealth Created (Equity + Cumulative Cash)</h3><canvas id="wealthChart"></canvas></div>
    <div class="chart-box"><h3>Annual After-Tax Cash Flow ($/year)</h3><canvas id="annCFChart"></canvas></div>
  </div>
</div>

<!-- ═════════════════════════════════════ DEEP-DIVE ═══ -->
<div id="page-detail" class="page">
  <div style="margin-bottom:16px;display:flex;align-items:center;gap:12px;flex-wrap:wrap;">
    <label style="font-weight:700;color:var(--navy)">Select Property:</label>
    <select id="propSelector" onchange="renderDetail()"></select>
  </div>
  <div id="detailContent"></div>
</div>

<!-- ═══════════════════════════════════════ RISK ═══ -->
<div id="page-risk" class="page">
  <div class="section-title">Risk &amp; Overlay Analysis <span class="pill">Data from property.com.au</span></div>
  <div class="assump-note">⚠️ Flood and bushfire overlays indicate a <strong>planning overlay exists</strong> — it does not necessarily mean the property is likely to flood or burn. Always obtain a full flood report from Gold Coast City Council before purchasing.</div>
  <div class="tbl-wrap"><table id="riskTable"></table></div>
  <div class="chart-grid">
    <div class="chart-box"><h3>Risk Score by Property (higher = more overlays)</h3><canvas id="riskChart"></canvas></div>
    <div class="chart-box"><h3>Flood &amp; Bushfire Exposure Summary</h3><canvas id="riskPieChart"></canvas></div>
  </div>
</div>

<!-- ══════════════════════════════ SCENARIO PLANNER ═══ -->
<div id="page-scenario" class="page">
  <div class="assump-note">Adjust any input below — all charts, tables and IRR figures recalculate instantly in the browser. Changes don't affect the underlying scraped data.</div>

  <div class="section-title">🌐 Global Assumptions</div>
  <div style="display:grid;grid-template-columns:repeat(auto-fill,minmax(260px,1fr));gap:14px;margin-bottom:24px" id="globalControls"></div>

  <div class="section-title">🏠 Per-Property Overrides <span class="pill">Overrides weekly rent and purchase price for each property</span></div>
  <div id="propOverrides"></div>

  <div style="display:flex;gap:12px;margin:18px 0">
    <button onclick="applyScenario()" style="background:var(--blue);color:white;border:none;padding:11px 28px;border-radius:8px;font-size:14px;font-weight:700;cursor:pointer">▶ Apply &amp; Recalculate</button>
    <button onclick="resetScenario()" style="background:white;color:var(--navy);border:2px solid var(--border);padding:11px 22px;border-radius:8px;font-size:14px;font-weight:600;cursor:pointer">↺ Reset to Defaults</button>
  </div>

  <div class="section-title">📊 Scenario Results</div>
  <div class="tbl-wrap"><table id="scenarioTable"></table></div>
  <div class="chart-grid">
    <div class="chart-box"><h3>Scenario IRR Comparison</h3><canvas id="scIrrChart"></canvas></div>
    <div class="chart-box"><h3>Scenario $/Week After Tax (Year 1)</h3><canvas id="scCfChart"></canvas></div>
  </div>
  <div class="chart-grid">
    <div class="chart-box"><h3>Scenario Equity at Year 10</h3><canvas id="scEqChart"></canvas></div>
    <div class="chart-box"><h3>Scenario Total Wealth at Year 10</h3><canvas id="scWealthChart"></canvas></div>
  </div>
</div>

<!-- ════════════════════════════════ ASSUMPTIONS ═══ -->
<div id="page-assumptions" class="page">
  <div class="assump-note">All projections are estimates. This is not financial advice — consult a licensed adviser before investing.</div>
  <div class="section-title">Model Assumptions</div>
  <div class="tbl-wrap" id="assumpTable"></div>
  <div class="section-title">Interest Rate Sensitivity <span class="pill">Effect on Year-1 After-Tax $/week — best ranked property</span></div>
  <div id="rateSens"></div>
  <div class="section-title">Capital Growth Sensitivity <span class="pill">Effect on 10-Year IRR — best ranked property</span></div>
  <div id="growthSens"></div>
</div>

</div>

<script>
const DATA = {data_json};
const props   = DATA.properties;
const assump  = DATA.assumptions;
const meta    = DATA.meta || {{}};

const COLOURS = ['#2E75B6','#1a7a4a','#e67e22','#8e44ad','#c0392b','#16a085','#d35400','#2980b9'];
const labels10 = ['Yr1','Yr2','Yr3','Yr4','Yr5','Yr6','Yr7','Yr8','Yr9','Yr10'];

// ─── helpers ─────────────────────────────────────────────────────────────────
const fmt  = (n,p='$',d=0) => {{
  if(n==null||n===undefined) return '—';
  const abs = Math.abs(n).toLocaleString('en-AU',{{minimumFractionDigits:d,maximumFractionDigits:d}});
  return (n<0?'-':'')+p+abs;
}};
const pct  = (n,d=2) => n==null?'—':Number(n).toFixed(d)+'%';
const sAddr= a => String(a).replace('Crescent','Cres').replace('Street','St').replace('Court','Ct').replace('Drive','Dr').replace('Avenue','Ave');
const cfColor = v => v >= -50 ? '#1a7a4a' : v >= -100 ? '#b8860b' : '#c0392b';
const cfBg    = v => v >= -50 ? '#e2efda' : v >= -100 ? '#fff3cd' : '#fde8e6';

const ranked = [...props].sort((a,b) => (b.irr||0)-(a.irr||0));
const rankOf = addr => ranked.findIndex(p=>p.address===addr)+1;

let compDone = false, riskDone = false;
let detCharts = {{}};
let ovCharts = {{}};
let filterReady = false;

// ─── update header ────────────────────────────────────────────────────────────
document.getElementById('lastUpdated').textContent =
  'Last updated: '+(meta.generated_display||new Date().toLocaleDateString('en-AU'))+
  ' · '+props.length+' properties';

// ─── nav ─────────────────────────────────────────────────────────────────────
function showPage(id, btn) {{
  document.querySelectorAll('.page').forEach(p=>p.classList.remove('active'));
  document.querySelectorAll('.nav-btn').forEach(b=>b.classList.remove('active'));
  document.getElementById('page-'+id).classList.add('active');
  btn.classList.add('active');
  if(id==='comparison'&&!compDone){{ renderComparison(); compDone=true; }}
  if(id==='detail'){{ populateSelector(); renderDetail(); }}
  if(id==='risk'&&!riskDone){{ renderRisk(); riskDone=true; }}
  if(id==='assumptions') renderAssumptions();
  if(id==='scenario') {{ buildScenarioControls(); if(!scDone) applyScenario(); }}
}}

// ─── FILTERS ─────────────────────────────────────────────────────────────────
const fState = {{ minLand:0, minBeds:0, tenancy:'all', minIRR:0, risk:'all', suburbs:new Set() }};

function getFilteredRanked() {{
  return ranked.filter(p => {{
    const land = p.land_size_m2 || p.land_size_listed || 0;
    if (fState.minLand > 0 && land > 0 && land < fState.minLand) return false;
    if (fState.minBeds > 0 && p.bedrooms > 0 && p.bedrooms < fState.minBeds) return false;
    if (fState.tenancy === 'tenanted' && p.currently_tenanted !== true) return false;
    if (fState.tenancy === 'vacant'   && p.currently_tenanted !== false) return false;
    if (fState.minIRR > 0 && (p.irr||0) < fState.minIRR) return false;
    if (fState.risk !== 'all' && p.risk_label !== fState.risk) return false;
    if (fState.suburbs.size > 0 && !fState.suburbs.has(p.suburb)) return false;
    return true;
  }});
}}

function applyFilters() {{
  const filtered = getFilteredRanked();
  document.getElementById('filterCount').textContent =
    filtered.length === ranked.length ? `${{ranked.length}} properties` : `${{filtered.length}} of ${{ranked.length}} shown`;
  document.getElementById('rankingPill').textContent =
    filtered.length === ranked.length ? 'Sorted by 10-Year IRR · Click property name to deep-dive'
    : `${{filtered.length}} filtered · Sorted by 10-Year IRR`;
  renderRankingTable(filtered);
  renderOverviewCharts(filtered);
}}

function _suburbToggle(name, el) {{
  el.classList.toggle('on');
  const allPills = document.querySelectorAll('#suburbPills .s-pill');
  const onPills  = document.querySelectorAll('#suburbPills .s-pill.on');
  if (onPills.length === allPills.length) {{
    fState.suburbs = new Set(); // all on = no filter
  }} else if (onPills.length === 0) {{
    fState.suburbs = new Set(['__none__']); // none on = show nothing
  }} else {{
    fState.suburbs = new Set([...onPills].map(p=>p.dataset.s));
  }}
  applyFilters();
}}

function _allSuburbs() {{
  const allPills = document.querySelectorAll('#suburbPills .s-pill');
  const onPills  = document.querySelectorAll('#suburbPills .s-pill.on');
  const turnOn   = onPills.length < allPills.length;
  allPills.forEach(p => turnOn ? p.classList.add('on') : p.classList.remove('on'));
  fState.suburbs = turnOn ? new Set() : new Set(['__none__']);
  document.getElementById('subAllBtn').textContent = turnOn ? 'Clear all' : 'Select all';
  applyFilters();
}}

function resetFilters() {{
  fState.minLand=0; fState.minBeds=0; fState.tenancy='all';
  fState.minIRR=0; fState.risk='all'; fState.suburbs=new Set();
  document.getElementById('fLand').value=0;
  document.getElementById('fLandVal').textContent='Any';
  document.getElementById('fBeds').value='0';
  document.getElementById('fTenancy').value='all';
  document.getElementById('fIRR').value=0;
  document.getElementById('fIRRVal').textContent='Any';
  document.getElementById('fRisk').value='all';
  document.querySelectorAll('#suburbPills .s-pill').forEach(p=>p.classList.add('on'));
  document.getElementById('subAllBtn').textContent='Clear all';
  applyFilters();
}}

function buildFilterBar() {{
  const suburbs = [...new Set(ranked.map(p=>p.suburb).filter(Boolean))].sort();
  const maxLand = Math.max(...ranked.map(p=>p.land_size_m2||p.land_size_listed||0));
  const landMax = Math.min(Math.ceil(maxLand/100)*100+100, 1500);
  document.getElementById('filterBar').innerHTML = `
    <div class="f-item">
      <label>Min Land Size</label>
      <div class="f-range-row">
        <input type="range" id="fLand" min="0" max="${{landMax}}" step="50" value="0"
          oninput="fState.minLand=+this.value;document.getElementById('fLandVal').textContent=+this.value===0?'Any':this.value+'m²';applyFilters()">
        <span class="f-val" id="fLandVal">Any</span>
      </div>
    </div>
    <div class="f-item">
      <label>Min Beds</label>
      <select id="fBeds" onchange="fState.minBeds=+this.value;applyFilters()">
        <option value="0">Any</option>
        <option value="3">3+</option>
        <option value="4" selected>4+</option>
        <option value="5">5+</option>
      </select>
    </div>
    <div class="f-item">
      <label>Tenancy</label>
      <select id="fTenancy" onchange="fState.tenancy=this.value;applyFilters()">
        <option value="all">All</option>
        <option value="tenanted">Tenanted only</option>
        <option value="vacant">Vacant only</option>
      </select>
    </div>
    <div class="f-item">
      <label>Min IRR</label>
      <div class="f-range-row">
        <input type="range" id="fIRR" min="0" max="20" step="0.5" value="0"
          oninput="fState.minIRR=+this.value;document.getElementById('fIRRVal').textContent=+this.value===0?'Any':this.value+'%';applyFilters()">
        <span class="f-val" id="fIRRVal">Any</span>
      </div>
    </div>
    <div class="f-item">
      <label>Risk</label>
      <select id="fRisk" onchange="fState.risk=this.value;applyFilters()">
        <option value="all">Any</option>
        <option value="Low">Low only</option>
        <option value="Moderate">≤ Moderate</option>
      </select>
    </div>
    <div class="f-item">
      <label>Suburbs <button id="subAllBtn" class="f-reset" style="padding:2px 8px;font-size:10px;margin-left:4px" onclick="_allSuburbs()">Clear all</button></label>
      <div class="suburb-pills" id="suburbPills">
        ${{suburbs.map(s=>`<span class="s-pill on" data-s="${{s}}" onclick="_suburbToggle('${{s}}',this)">${{s}}</span>`).join('')}}
      </div>
    </div>
    <div class="f-item" style="margin-left:auto;justify-content:flex-end;gap:6px">
      <span class="f-count" id="filterCount"></span>
      <button class="f-reset" onclick="resetFilters()">↺ Reset filters</button>
    </div>
  `;
  // Initialise fState.minBeds to 4 to match the default selected option
  fState.minBeds = 4;
  applyFilters();
}}

// ─── OVERVIEW ────────────────────────────────────────────────────────────────
function renderRankingTable(list) {{
  const tbl = document.getElementById('rankingTable');
  if (!list.length) {{
    tbl.innerHTML = '<thead><tr><th colspan="17">No properties match current filters</th></tr></thead><tbody><tr><td colspan="17" style="text-align:center;padding:30px;color:#999">Try adjusting the filters above</td></tr></tbody>';
    return;
  }}
  tbl.innerHTML = `<thead><tr>
    <th>Rank</th><th>Address</th><th>Suburb</th><th class="c">Price</th>
    <th class="c">Beds</th><th class="c">Land m²</th><th class="c">Build Yr</th>
    <th class="c">PropTrack</th><th class="c">Rent/Wk</th><th class="c">Gross Yld</th>
    <th class="c">$/Wk (AT)</th><th class="c">IRR</th><th class="c">10yr Equity</th>
    <th class="c">NPV@7%</th><th class="c">Tenanted</th><th class="c">Risk</th><th class="c">Action</th>
  </tr></thead><tbody>${{list.map((p,i)=>{{
    const v = p.yr1_aftertax_cashflow_pw||0;
    const rowCls = i===0?'hi-row':i===1?'hi-row am':'';
    const rLabel = p.risk_label||'—';
    const rCls = rLabel==='Low'?'g':rLabel==='Moderate'?'a':'r';
    const tenanted = p.currently_tenanted===true?'<span class="chip g">✓ Tenanted</span>':
                     p.currently_tenanted===false?'<span class="chip gr">Vacant</span>':
                     '<span class="chip b">Unknown</span>';
    const ptGap = p.proptrack_gap;
    const ptStr = ptGap!=null ? fmt(p.proptrack_estimate)+(ptGap>0?` <span style="color:var(--green);font-size:10px">+${{(ptGap/1000).toFixed(0)}}k</span>`:'') : '—';
    const beds = p.bedrooms != null ? p.bedrooms : '—';
    const land = p.land_size_m2 != null ? p.land_size_m2+'m²' : (p.land_size_listed != null ? p.land_size_listed+'m²' : '—');
    const buildYr = p.build_year_est || p.build_year_domain || '—';
    return `<tr class="${{rowCls}}">
      <td><span class="chip ${{i===0?'n':i===1?'b':'gr'}}">#${{i+1}}${{i===0?' ★':''}}</span></td>
      <td><a href="#" onclick="jumpDetail('${{p.address}}');return false"
         style="color:var(--blue);font-weight:600;text-decoration:none">${{sAddr(p.address)}}</a></td>
      <td>${{p.suburb||''}}</td>
      <td class="c">${{fmt(p.purchase_price||p.purchase_price_assumed)}}</td>
      <td class="c">${{beds}}</td>
      <td class="c">${{land}}</td>
      <td class="c">${{buildYr}}</td>
      <td class="c">${{ptStr}}</td>
      <td class="c">$${{p.weekly_rent||p.weekly_rent_est||'—'}}/wk</td>
      <td class="c">${{pct(p.gross_yield||p.gross_yield_pct)}}</td>
      <td class="c"><span class="chip" style="background:${{cfBg(v)}};color:${{cfColor(v)}}">${{v>=0?'+':''}}$${{v}}/wk</span></td>
      <td class="c"><strong>${{pct(p.irr||p.irr_10yr_pct)}}</strong></td>
      <td class="c">${{fmt(p.total_equity_yr10)}}</td>
      <td class="c">${{fmt(p.npv_7pct||p.npv_at_7pct)}}</td>
      <td class="c">${{tenanted}}</td>
      <td class="c"><span class="chip ${{rCls}}">${{rLabel}}</span></td>
      <td class="c"><a href="#" onclick="jumpDetail('${{p.address}}');return false" style="color:var(--blue);font-size:12px;font-weight:600">Deep-Dive →</a></td>
    </tr>`;
  }}).join('')}}</tbody>`;
}}

function renderOverviewCharts(list) {{
  Object.values(ovCharts).forEach(c=>{{ try{{c.destroy()}}catch(e){{}} }});
  ovCharts = {{}};
  if (!list.length) return;
  const labs = list.map(p=>sAddr(p.address));
  ovCharts.irr = new Chart(document.getElementById('irrChart'),{{
    type:'bar',
    data:{{labels:labs, datasets:[{{data:list.map(p=>p.irr||p.irr_10yr_pct||0),backgroundColor:COLOURS,borderRadius:5}}]}},
    options:{{plugins:{{legend:{{display:false}}}},scales:{{y:{{title:{{display:true,text:'IRR %'}}}}}},indexAxis:'y',responsive:true,maintainAspectRatio:true}}
  }});
  ovCharts.cf = new Chart(document.getElementById('cfChart'),{{
    type:'bar',
    data:{{labels:labs, datasets:[{{data:list.map(p=>p.yr1_aftertax_cashflow_pw||0),
      backgroundColor:list.map(p=>cfBg(p.yr1_aftertax_cashflow_pw||0)),
      borderColor:list.map(p=>cfColor(p.yr1_aftertax_cashflow_pw||0)),borderWidth:2,borderRadius:5}}]}},
    options:{{plugins:{{legend:{{display:false}}}},scales:{{y:{{title:{{display:true,text:'$/week'}}}}}},indexAxis:'y',responsive:true}}
  }});
  ovCharts.equity = new Chart(document.getElementById('equityChart'),{{
    type:'bar',
    data:{{labels:labs, datasets:[
      {{label:'Loan Balance',data:list.map(p=>p.loan_amount||0),backgroundColor:'#e0e0e0',borderRadius:3}},
      {{label:'Equity Yr10',data:list.map(p=>p.total_equity_yr10||0),backgroundColor:COLOURS,borderRadius:3}}
    ]}},
    options:{{plugins:{{legend:{{position:'top'}}}},scales:{{x:{{stacked:true}},y:{{stacked:true,title:{{display:true,text:'$'}}}}}},indexAxis:'y',responsive:true}}
  }});
  ovCharts.yield = new Chart(document.getElementById('yieldChart'),{{
    type:'bar',
    data:{{labels:labs, datasets:[
      {{label:'Gross Yield',data:list.map(p=>p.gross_yield||p.gross_yield_pct||0),backgroundColor:'#2E75B6cc',borderRadius:3}},
      {{label:'Net Yield',data:list.map(p=>p.net_yield||p.net_yield_pct||0),backgroundColor:'#1a7a4acc',borderRadius:3}}
    ]}},
    options:{{plugins:{{legend:{{position:'top'}}}},scales:{{y:{{title:{{display:true,text:'%'}}}}}},indexAxis:'y',responsive:true}}
  }});
}}

function renderOverview() {{
  const top = ranked[0];
  const v = top.yr1_aftertax_cashflow_pw||top.weekly_net_aftertax||0;
  document.getElementById('overviewCards').innerHTML = `
    <div class="card navy"><div class="card-label">Properties Found</div>
      <div class="card-value">${{props.length}}</div>
      <div class="card-sub">${{(meta.suburbs_searched||[]).join(' · ')}}</div></div>
    <div class="card green"><div class="card-label">Best 10-yr IRR</div>
      <div class="card-value pos">${{pct(top.irr)}}</div>
      <div class="card-sub">${{sAddr(top.address)}}</div></div>
    <div class="card"><div class="card-label">Best $/Week (after tax)</div>
      <div class="card-value" style="color:${{cfColor(v)}}">${{v>=0?'+':''}}$${{v}}/wk</div>
      <div class="card-sub">Year 1 incl. depreciation tax benefit</div></div>
    <div class="card amber"><div class="card-label">Budget</div>
      <div class="card-value">$850k–$1M</div>
      <div class="card-sub">20% deposit · I/O @ 6.20%</div></div>
    <div class="card green"><div class="card-label">Top 10-yr Equity</div>
      <div class="card-value pos">${{fmt(Math.max(...props.map(p=>p.total_equity_yr10||0)))}}</div>
      <div class="card-sub">Property value minus loan balance</div></div>
    <div class="card ${{props.filter(p=>p.flood_overlay||p.bushfire_overlay).length>0?'amber':'green'}}">
      <div class="card-label">Overlay Flags</div>
      <div class="card-value">${{props.filter(p=>p.flood_overlay||p.bushfire_overlay).length}} / ${{props.length}}</div>
      <div class="card-sub">Properties with flood or bushfire overlay</div></div>
  `;
  buildFilterBar(); // builds filter UI, then calls applyFilters() → renderRankingTable + renderOverviewCharts
}}

// ─── COMPARISON ───────────────────────────────────────────────────────────────
function renderComparison() {{
  const years = ['Purchase',...labels10];
  const propWithYearly = props.filter(p=>p.yearly&&p.yearly.length>0);
  if(!propWithYearly.length) {{
    document.querySelector('#page-comparison').innerHTML = '<p style="padding:40px;color:#888">Year-by-year data not available for these properties.</p>';
    return;
  }}
  // Value chart
  const vDatasets = propWithYearly.map((p,i)=>{{
    const price = p.purchase_price||p.purchase_price_assumed||0;
    return {{label:sAddr(p.address),data:[price,...p.yearly.map(y=>y.prop_value)],
      borderColor:COLOURS[i],backgroundColor:'transparent',tension:.4,borderWidth:2,pointRadius:3}};
  }});
  vDatasets.push({{label:'Loan Balance',data:[propWithYearly[0].loan_amount,...propWithYearly[0].yearly.map(y=>y.loan_balance)],
    borderColor:'#bbb',backgroundColor:'transparent',borderDash:[5,3],borderWidth:2,pointRadius:0}});
  new Chart(document.getElementById('valueChart'),{{
    type:'line',data:{{labels:years,datasets:vDatasets}},
    options:{{plugins:{{legend:{{position:'bottom',labels:{{boxWidth:12}}}}}},scales:{{y:{{title:{{display:true,text:'$'}}}}}},responsive:true,maintainAspectRatio:false}}
  }});

  const mkLine = (canvasId, fn, ytitle, fill=false) => new Chart(document.getElementById(canvasId),{{
    type:'line',
    data:{{labels:labels10,datasets:propWithYearly.map((p,i)=>{{
      const ydata = p.yearly.map(fn);
      return {{label:sAddr(p.address),data:ydata,borderColor:COLOURS[i],
        backgroundColor:fill?COLOURS[i]+'22':'transparent',tension:.4,fill,borderWidth:2,pointRadius:3}};
    }})}},
    options:{{plugins:{{legend:{{position:'bottom',labels:{{boxWidth:12}}}}}},scales:{{y:{{title:{{display:true,text:ytitle}}}}}},responsive:true}}
  }});
  mkLine('eqLineChart',y=>y.equity,'$');
  mkLine('cumCFChart', y=>y.cumulative_aftertax_cashflow,'$');
  mkLine('wealthChart',y=>y.total_wealth_created,'$',true);
  new Chart(document.getElementById('annCFChart'),{{
    type:'bar',
    data:{{labels:labels10,datasets:propWithYearly.map((p,i)=>{{
      return {{label:sAddr(p.address),data:p.yearly.map(y=>y.aftertax_cashflow),backgroundColor:COLOURS[i]+'cc',borderRadius:3}};
    }})}},
    options:{{plugins:{{legend:{{position:'bottom',labels:{{boxWidth:12}}}}}},scales:{{y:{{title:{{display:true,text:'$/year'}}}}}},responsive:true}}
  }});
}}

// ─── DETAIL ───────────────────────────────────────────────────────────────────
let detTab = 'table';
function populateSelector() {{
  const sel = document.getElementById('propSelector');
  if(sel.options.length>0) return;
  ranked.forEach((p,i)=>{{
    const o = document.createElement('option');
    o.value = p.address;
    o.text = `#${{i+1}} — ${{sAddr(p.address)}}, ${{p.suburb}} (IRR ${{pct(p.irr||p.irr_10yr_pct)}})`;
    sel.appendChild(o);
  }});
}}
function jumpDetail(addr) {{
  showPage('detail', document.querySelectorAll('.nav-btn')[2]);
  populateSelector();
  document.getElementById('propSelector').value = addr;
  renderDetail();
}}
function renderDetail() {{
  const addr = document.getElementById('propSelector').value;
  const p = props.find(x=>x.address===addr)||ranked[0];
  const rank = rankOf(p.address);
  const v = p.yr1_aftertax_cashflow_pw||0;

  Object.values(detCharts).forEach(c=>c.destroy()); detCharts={{}};

  const rLabel = p.risk_label||'—';
  const rCls = rLabel==='Low'?'low':rLabel==='Moderate'?'mod':'high';

  const tenanted = p.currently_tenanted===true ? '✓ Currently Tenanted' :
                   p.currently_tenanted===false ? 'Vacant at Settlement' : 'Tenancy Status Unknown';
  const tenantedChip = p.currently_tenanted===true?'g':p.currently_tenanted===false?'gr':'b';

  const flood = p.flood_overlay===true?'<span class="chip r">⚠ Flood Overlay</span>':
                p.flood_overlay===false?'<span class="chip g">✓ No Flood</span>':'<span class="chip gr">Flood: Unknown</span>';
  const bush  = p.bushfire_overlay===true?'<span class="chip a">⚠ Bushfire Overlay</span>':
                p.bushfire_overlay===false?'<span class="chip g">✓ No Bushfire</span>':'<span class="chip gr">Bushfire: Unknown</span>';

  const rankLabels = ['★ #1 Top Pick','#2 Runner-Up','#3','#4','#5','#6','#7','#8'];
  const hasYearly = p.yearly && p.yearly.length > 0;

  document.getElementById('detailContent').innerHTML = `
    <div class="prop-header">
      <div class="row1">
        <div class="info">
          <div class="pills">
            <span class="chip ${{rank<=2?'n':'b'}}">${{rankLabels[rank-1]||'#'+rank}}</span>
            <span class="chip" style="background:${{cfBg(v)}};color:${{cfColor(v)}}">${{v>=0?'+':''}}$${{v}}/wk after tax</span>
            <span class="chip b">${{pct(p.irr||p.irr_10yr_pct)}} 10-yr IRR</span>
            <span class="chip ${{tenantedChip}}">${{tenanted}}</span>
          </div>
          <h2>${{p.address}}</h2>
          <div class="meta">${{p.suburb}} QLD ${{p.postcode||'4209'}} · Built ~${{p.build_year_est||'?'}} · Listed: ${{p.listing_price||p.listing_price_str||'—'}}</div>
          <div class="pills" style="margin-top:6px">
            ${{flood}} ${{bush}}
            ${{p.land_size_m2||p.land_size_listed?`<span class="chip b">🏡 ${{p.land_size_m2||p.land_size_listed}}m²</span>`:''}};
            ${{p.building_size_m2?`<span class="chip b">🏗 ${{p.building_size_m2}}m² built</span>`:''}};
            ${{p.nbn_type?`<span class="chip g">📡 ${{p.nbn_type}}</span>`:''}};
            ${{p.ground_elevation_m?`<span class="chip b">⛰ ${{p.ground_elevation_m}}m elev</span>`:''}};
          </div>
        </div>
        <div>
          <a href="${{p.domain_url}}" target="_blank" class="domain-btn">View on Domain ↗</a>
          ${{p.property_com_url?`<br><br><a href="${{p.property_com_url}}" target="_blank" class="domain-btn" style="background:#555;font-size:11px">property.com.au ↗</a>`:''}};
        </div>
      </div>
      ${{p.description?`<div class="desc-box" style="margin-top:12px"><strong>Listing description:</strong> ${{p.description.slice(0,400)}}${{p.description.length>400?'...':''}}</div>`:''}}
    </div>

    <div class="cards">
      <div class="card navy"><div class="card-label">Purchase Price</div><div class="card-value">${{fmt(p.purchase_price||p.purchase_price_assumed)}}</div>
        <div class="card-sub">PropTrack: ${{fmt(p.proptrack_estimate)}} (${{p.proptrack_gap>0?'+':''}}${{Math.round((p.proptrack_gap||0)/1000)}}k)</div></div>
      <div class="card"><div class="card-label">Total Upfront Cash</div><div class="card-value">${{fmt(p.total_upfront)}}</div>
        <div class="card-sub">${{fmt(p.deposit)}} deposit + ${{fmt(p.stamp_duty)}} stamp duty</div></div>
      <div class="card"><div class="card-label">Weekly Rent (Est.)</div><div class="card-value">$${{p.weekly_rent||p.weekly_rent_est}}/wk</div>
        <div class="card-sub">Gross ${{pct(p.gross_yield||p.gross_yield_pct)}} · Net ${{pct(p.net_yield||p.net_yield_pct)}}</div></div>
      <div class="card ${{v>=-50?'green':v>=-100?'amber':'red'}}"><div class="card-label">After-Tax $/Week (Yr1)</div>
        <div class="card-value" style="color:${{cfColor(v)}}">${{v>=0?'+':''}}$${{v}}/wk</div>
        <div class="card-sub">Incl. depreciation tax benefit at blended 46%</div></div>
      <div class="card green"><div class="card-label">10-Year IRR</div><div class="card-value pos">${{pct(p.irr||p.irr_10yr_pct)}}</div>
        <div class="card-sub">NPV at 7% = ${{fmt(p.npv_7pct||p.npv_at_7pct)}}</div></div>
      <div class="card navy"><div class="card-label">Equity at Year 10</div><div class="card-value">${{fmt(p.total_equity_yr10)}}</div>
        <div class="card-sub">${{fmt(p.exit_value)}} value − ${{fmt(p.loan_amount)}} loan</div></div>
    </div>

    ${{(p.flood_overlay||p.bushfire_overlay)?
      `<div class="risk-banner high">⚠️ This property has planning overlays: ${{p.flood_overlay?'Flood':''}}&nbsp;${{p.bushfire_overlay?'Bushfire':''}}. This warrants further due diligence — request a detailed overlay report from Gold Coast City Council before proceeding.</div>`:
      `<div class="risk-banner low">✅ No major planning overlays detected for this property.</div>`}}

    ${{p.rental_history&&p.rental_history.length>0?
      `<div class="desc-box"><strong>Rental History:</strong> ${{p.rental_history.map(r=>'$'+r+'/wk').join(' → ')}} (most recent first)</div>`:''}}

    <div class="inner-tabs">
      <button class="inner-tab ${{detTab==='table'?'active':''}}" onclick="switchDT('table',this)">📋 Year-by-Year Table</button>
      <button class="inner-tab ${{detTab==='charts'?'active':''}}" onclick="switchDT('charts',this)">📈 Charts</button>
      <button class="inner-tab ${{detTab==='acquisition'?'active':''}}" onclick="switchDT('acquisition',this)">💰 Acquisition &amp; Exit</button>
    </div>

    <div id="dt-table" style="${{detTab!=='table'?'display:none':''}}">
      ${{hasYearly ? buildYearlyTable(p) : '<p style="color:#888;padding:20px">Year-by-year data not available.</p>'}}
    </div>
    <div id="dt-charts" style="${{detTab!=='charts'?'display:none':''}}">
      ${{hasYearly ? `
      <div class="chart-grid">
        <div class="chart-box"><h3>Property Value vs Loan Balance</h3><canvas id="d_val"></canvas></div>
        <div class="chart-box"><h3>After-Tax Cash Flow ($/week)</h3><canvas id="d_cf"></canvas></div>
      </div>
      <div class="chart-grid">
        <div class="chart-box"><h3>Equity Growth</h3><canvas id="d_eq"></canvas></div>
        <div class="chart-box"><h3>Depreciation (Div 43 vs Div 40)</h3><canvas id="d_dep"></canvas></div>
      </div>` : '<p style="color:#888;padding:20px">Chart data not available.</p>'}}
    </div>
    <div id="dt-acquisition" style="${{detTab!=='acquisition'?'display:none':''}}">
      ${{buildAcquisitionPanel(p)}}
    </div>
  `;

  if(detTab==='charts' && hasYearly) renderDetailCharts(p);
}}

function buildYearlyTable(p) {{
  return `<div class="tbl-wrap"><table>
    <thead><tr>
      <th class="sticky-col">Year</th>
      <th class="c">Value</th><th class="c">Equity</th>
      <th class="c">Gross Rent</th><th class="c">Eff. Rent</th>
      <th class="c">Interest</th><th class="c">Other Exp</th>
      <th class="c">Div 43</th><th class="c">Div 40</th>
      <th class="c">Taxable Inc</th><th class="c">Tax Impact</th>
      <th class="c">Pre-Tax CF</th><th class="c">AT CF/yr</th>
      <th class="c">AT $/wk</th><th class="c">Cum AT CF</th><th class="c">Total Wealth</th>
    </tr></thead>
    <tbody>
    ${{p.yearly.map(y=>{{
      const pw = y.aftertax_cashflow_pw;
      return `<tr>
        <td class="sticky-col"><strong>Yr ${{y.year}}</strong></td>
        <td class="c">${{fmt(y.prop_value)}}</td>
        <td class="c"><strong>${{fmt(y.equity)}}</strong></td>
        <td class="c">${{fmt(y.gross_rent)}}</td>
        <td class="c">${{fmt(y.effective_rent)}}</td>
        <td class="c">${{fmt(y.interest)}}</td>
        <td class="c">${{fmt((y.pm_fee||0)+(y.council_water_insurance||0)+(y.maintenance||0))}}</td>
        <td class="c">${{fmt(y.div43)}}</td>
        <td class="c">${{fmt(y.div40)}}</td>
        <td class="c" style="color:${{y.taxable_income<0?'var(--green)':'var(--red)'}}">${{fmt(y.taxable_income)}}</td>
        <td class="c" style="color:var(--green)">+${{fmt(y.tax_impact)}}</td>
        <td class="c" style="color:${{y.pretax_cashflow>=0?'var(--green)':'var(--red)'}}">${{fmt(y.pretax_cashflow)}}</td>
        <td class="c" style="color:${{y.aftertax_cashflow>=0?'var(--green)':'var(--red)'}}">${{fmt(y.aftertax_cashflow)}}</td>
        <td class="c"><span class="chip" style="background:${{cfBg(pw)}};color:${{cfColor(pw)}}">${{pw>=0?'+':''}}$${{pw}}/wk</span></td>
        <td class="c" style="color:${{y.cumulative_aftertax_cashflow>=0?'var(--green)':'var(--red)'}}">${{fmt(y.cumulative_aftertax_cashflow)}}</td>
        <td class="c"><strong>${{fmt(y.total_wealth_created)}}</strong></td>
      </tr>`;
    }}).join('')}}
    <tr style="background:var(--lblue);font-weight:700">
      <td class="sticky-col">EXIT Yr10</td>
      <td class="c">${{fmt(p.exit_value)}}</td>
      <td class="c">${{fmt(p.total_equity_yr10)}}</td>
      <td colspan="10" class="c" style="color:#555;font-style:italic">Selling costs ${{fmt(p.selling_costs_exit||0,'')}} · CGT ${{fmt(p.cgt_payable||0,'')}} · Net proceeds ${{fmt(p.net_proceeds||0)}}</td>
      <td colspan="2" class="c"><strong>${{fmt(p.total_wealth_yr10)}}</strong></td>
    </tr>
    </tbody></table></div>`;
}}

function buildAcquisitionPanel(p) {{
  const hasYearly = p.yearly&&p.yearly.length>0;
  return `<div style="display:grid;grid-template-columns:1fr 1fr;gap:18px;flex-wrap:wrap">
    <div>
      <div class="section-title" style="margin-top:0">Acquisition Costs</div>
      <div class="tbl-wrap"><table>
        <thead><tr><th>Component</th><th class="c">Amount</th></tr></thead>
        <tbody>
          <tr><td>20% Deposit</td><td class="c">${{fmt(p.deposit)}}</td></tr>
          <tr><td>QLD Stamp Duty (Investor, no FHOG)</td><td class="c">${{fmt(p.stamp_duty)}}</td></tr>
          <tr><td>Legal / Conveyancing</td><td class="c">${{fmt(p.legal_costs)}}</td></tr>
          <tr class="sub-row"><td><strong>Total Upfront Cash</strong></td><td class="c"><strong>${{fmt(p.total_upfront)}}</strong></td></tr>
          <tr><td>I/O Loan Amount (6.20% p.a.)</td><td class="c">${{fmt(p.loan_amount)}}</td></tr>
          <tr><td>Annual Interest Cost</td><td class="c">${{fmt(p.annual_interest)}}</td></tr>
        </tbody>
      </table></div>
      <div class="section-title" style="margin-top:16px">Year 1 Depreciation</div>
      <div class="tbl-wrap"><table>
        <thead><tr><th>Type</th><th class="c">Amount</th></tr></thead>
        <tbody>
          <tr><td>Div 43 — Building (2.5%/yr on 55% of price)</td><td class="c">${{fmt(p.yr1_div43)}}</td></tr>
          <tr><td>Div 40 — Plant &amp; Equipment</td><td class="c">${{fmt(p.yr1_div40)}}</td></tr>
          <tr class="sub-row"><td><strong>Total Depreciation</strong></td><td class="c"><strong>${{fmt(p.yr1_depreciation||p.yr1_depreciation)}}</strong></td></tr>
          <tr><td>Tax saving @ blended 46%</td><td class="c" style="color:var(--green)">+${{fmt(p.yr1_tax_impact)}}</td></tr>
        </tbody>
      </table></div>
    </div>
    <div>
      <div class="section-title" style="margin-top:0">10-Year Exit</div>
      ${{(()=>{{
        const inf  = assump.inflation_rate || 0.025;
        const yrs  = 10;
        const base = p.purchase_price || 1;
        const ev   = p.exit_value || 0;
        const nomAnn  = (Math.pow(ev/base, 1/yrs) - 1) * 100;
        const nomTot  = (ev/base - 1) * 100;
        const realAnn = ((Math.pow(ev/base, 1/yrs) / (1+inf)) - 1) * 100;
        const realTot = ((ev/base) / Math.pow(1+inf, yrs) - 1) * 100;
        const inflAdj = Math.round(ev / Math.pow(1+inf, yrs));
        return `<div style="display:flex;gap:10px;margin-bottom:10px;flex-wrap:wrap">
          <div class="card" style="flex:1;min-width:140px;border-top-color:var(--green)">
            <div class="card-label">Nominal Growth</div>
            <div class="card-value pos" style="font-size:20px">${{nomAnn.toFixed(1)}}%/yr</div>
            <div class="card-sub">${{nomTot.toFixed(0)}}% total over 10 yrs</div>
          </div>
          <div class="card" style="flex:1;min-width:140px;border-top-color:var(--blue)">
            <div class="card-label">Real Growth (after ${{(inf*100).toFixed(1)}}% inflation)</div>
            <div class="card-value" style="font-size:20px;color:var(--blue)">${{realAnn.toFixed(1)}}%/yr</div>
            <div class="card-sub">${{realTot.toFixed(0)}}% real total · ${{fmt(inflAdj)}} in today's $</div>
          </div>
        </div>`;
      }})()}}
      <div class="tbl-wrap"><table>
        <thead><tr><th>Component</th><th class="c">Amount</th></tr></thead>
        <tbody>
          <tr><td>Exit Value @ 7% p.a. growth</td><td class="c"><strong>${{fmt(p.exit_value)}}</strong></td></tr>
          <tr><td>Gross Capital Gain</td><td class="c" style="color:var(--green)">${{fmt(p.gross_capital_gain)}}</td></tr>
          <tr><td>Selling Costs (2.5%)</td><td class="c" style="color:var(--red)">−${{fmt(p.selling_costs_exit||0,'')}}</td></tr>
          <tr><td>CGT (50% disc, 47%/45%)</td><td class="c" style="color:var(--red)">−${{fmt(p.cgt_payable||0,'')}}</td></tr>
          <tr><td>Loan Repayment (I/O)</td><td class="c" style="color:var(--red)">−${{fmt(p.loan_amount||0,'')}}</td></tr>
          <tr class="sub-row"><td><strong>Net Cash-in-Pocket</strong></td><td class="c"><strong>${{fmt(p.net_proceeds||0)}}</strong></td></tr>
        </tbody>
      </table></div>
      ${{hasYearly?`
      <div class="section-title" style="margin-top:16px">If-Sold-Now Scenarios</div>
      <div class="tbl-wrap"><table>
        <thead><tr>
          <th class="c">Year</th><th class="c">Value</th>
          <th class="c">Growth %/yr</th><th class="c">Total Growth</th>
          <th class="c">Real %/yr<br><span style="font-weight:400;font-size:10px">after inflation</span></th>
          <th class="c">Real Total<br><span style="font-weight:400;font-size:10px">in today's $</span></th>
          <th class="c">Equity</th><th class="c">Net Proceeds</th>
        </tr></thead>
        <tbody>
          ${{p.yearly.filter((_,i)=>[0,2,4,6,9].includes(i)).map(y=>{{
            const inf2 = assump.inflation_rate || 0.025;
            const base2 = p.purchase_price || 1;
            const nomA = (Math.pow(y.prop_value/base2, 1/y.year) - 1) * 100;
            const nomT = (y.prop_value/base2 - 1) * 100;
            const realA = ((Math.pow(y.prop_value/base2, 1/y.year) / (1+inf2)) - 1) * 100;
            const realT = (y.prop_value/base2 / Math.pow(1+inf2, y.year) - 1) * 100;
            const today = Math.round(y.prop_value / Math.pow(1+inf2, y.year));
            return `<tr>
              <td class="c">Yr ${{y.year}}</td>
              <td class="c">${{fmt(y.prop_value)}}</td>
              <td class="c" style="color:var(--green)">${{nomA.toFixed(1)}}%</td>
              <td class="c" style="color:var(--green)">${{nomT.toFixed(0)}}%</td>
              <td class="c" style="color:var(--blue)">${{realA.toFixed(1)}}%</td>
              <td class="c" style="color:var(--blue)">${{realT.toFixed(0)}}% (${{fmt(today)}})</td>
              <td class="c">${{fmt(y.equity)}}</td>
              <td class="c"><strong>${{fmt(y.net_proceeds_if_sold)}}</strong></td>
            </tr>`;
          }}).join('')}}
        </tbody>
      </table></div>`:''}}
    </div>
  </div>`;
}}

function switchDT(tab, btn) {{
  detTab = tab;
  document.querySelectorAll('.inner-tab').forEach(b=>b.classList.remove('active'));
  btn.classList.add('active');
  ['table','charts','acquisition'].forEach(t=>{{
    const el = document.getElementById('dt-'+t);
    if(el) el.style.display = t===tab?'':'none';
  }});
  if(tab==='charts') {{
    const addr = document.getElementById('propSelector').value;
    const p = props.find(x=>x.address===addr)||ranked[0];
    if(p.yearly&&p.yearly.length>0) renderDetailCharts(p);
  }}
}}

function renderDetailCharts(p) {{
  const yrs = ['Purchase',...labels10];
  const price = p.purchase_price||p.purchase_price_assumed||0;
  const vals = [price,...p.yearly.map(y=>y.prop_value)];
  const loan  = [p.loan_amount,...p.yearly.map(y=>y.loan_balance)];
  const eq    = [p.deposit,...p.yearly.map(y=>y.equity)];

  if(detCharts.val) detCharts.val.destroy();
  detCharts.val = new Chart(document.getElementById('d_val'),{{
    type:'line',data:{{labels:yrs,datasets:[
      {{label:'Property Value',data:vals,borderColor:'#2E75B6',backgroundColor:'#2E75B622',fill:true,tension:.4,borderWidth:2}},
      {{label:'Loan Balance',  data:loan, borderColor:'#bbb',backgroundColor:'transparent',borderDash:[5,3],borderWidth:2,pointRadius:0}}
    ]}},
    options:{{plugins:{{legend:{{position:'top'}}}},scales:{{y:{{title:{{display:true,text:'$'}}}}}},responsive:true}}
  }});
  if(detCharts.cf) detCharts.cf.destroy();
  detCharts.cf = new Chart(document.getElementById('d_cf'),{{
    type:'bar',data:{{labels:labels10,datasets:[{{
      data:p.yearly.map(y=>y.aftertax_cashflow_pw),
      backgroundColor:p.yearly.map(y=>cfBg(y.aftertax_cashflow_pw)),
      borderColor:p.yearly.map(y=>cfColor(y.aftertax_cashflow_pw)),
      borderWidth:2,borderRadius:5
    }}]}},
    options:{{plugins:{{legend:{{display:false}}}},scales:{{y:{{title:{{display:true,text:'$/week'}}}}}},responsive:true}}
  }});
  if(detCharts.eq) detCharts.eq.destroy();
  detCharts.eq = new Chart(document.getElementById('d_eq'),{{
    type:'line',data:{{labels:yrs,datasets:[{{
      label:'Equity',data:eq,borderColor:'#1a7a4a',backgroundColor:'#1a7a4a22',fill:true,tension:.4,borderWidth:2
    }}]}},
    options:{{plugins:{{legend:{{display:false}}}},scales:{{y:{{title:{{display:true,text:'$'}}}}}},responsive:true}}
  }});
  if(detCharts.dep) detCharts.dep.destroy();
  detCharts.dep = new Chart(document.getElementById('d_dep'),{{
    type:'bar',data:{{labels:labels10,datasets:[
      {{label:'Div 43 (Building)',data:p.yearly.map(y=>y.div43),backgroundColor:'#2E75B6cc',borderRadius:3}},
      {{label:'Div 40 (Plant)',   data:p.yearly.map(y=>y.div40),backgroundColor:'#1a7a4acc',borderRadius:3}}
    ]}},
    options:{{plugins:{{legend:{{position:'top'}}}},scales:{{x:{{stacked:true}},y:{{stacked:true,title:{{display:true,text:'$/year'}}}}}},responsive:true}}
  }});
}}

// ─── RISK ─────────────────────────────────────────────────────────────────────
function renderRisk() {{
  const tbl = document.getElementById('riskTable');
  tbl.innerHTML = `<table><thead><tr>
    <th>Property</th><th>Suburb</th><th class="c">Flood Overlay</th>
    <th class="c">Bushfire Overlay</th><th class="c">Heritage</th>
    <th class="c">Elevation</th><th class="c">Land m²</th>
    <th class="c">NBN</th><th class="c">Risk Score</th>
  </tr></thead><tbody>
  ${{ranked.map(p=>{{
    const fl = p.flood_overlay===true?'<span class="chip r">⚠ Found</span>':p.flood_overlay===false?'<span class="chip g">✓ Clear</span>':'<span class="chip gr">Unknown</span>';
    const bf = p.bushfire_overlay===true?'<span class="chip a">⚠ Found</span>':p.bushfire_overlay===false?'<span class="chip g">✓ Clear</span>':'<span class="chip gr">Unknown</span>';
    const her= p.heritage_overlay===false?'<span class="chip g">✓ None</span>':p.heritage_overlay===true?'<span class="chip a">Found</span>':'<span class="chip gr">Unknown</span>';
    const risk = p.risk_label||'—';
    return `<tr>
      <td><strong>${{sAddr(p.address)}}</strong></td><td>${{p.suburb}}</td>
      <td class="c">${{fl}}</td><td class="c">${{bf}}</td><td class="c">${{her}}</td>
      <td class="c">${{p.ground_elevation_m!=null?p.ground_elevation_m+'m':'—'}}</td>
      <td class="c">${{p.land_size_m2||'—'}}</td>
      <td class="c">${{p.nbn_type||'—'}}</td>
      <td class="c"><span class="chip ${{risk==='Low'?'g':risk==='Moderate'?'a':'r'}}">${{risk}}</span></td>
    </tr>`;
  }}).join('')}}
  </tbody></table>`;

  const flood_count = props.filter(p=>p.flood_overlay===true).length;
  const bush_count  = props.filter(p=>p.bushfire_overlay===true).length;
  const clear_count = props.filter(p=>p.flood_overlay===false&&p.bushfire_overlay===false).length;
  const unknown_count= props.filter(p=>p.flood_overlay==null&&p.bushfire_overlay==null).length;

  new Chart(document.getElementById('riskChart'),{{
    type:'bar',
    data:{{labels:ranked.map(p=>sAddr(p.address)),
      datasets:[{{data:ranked.map(p=>p.risk_score||0),backgroundColor:ranked.map(p=>{{
        const s=p.risk_score||0; return s===0?'#1a7a4a':s===1?'#b8860b':'#c0392b';
      }}),borderRadius:5}}]}},
    options:{{plugins:{{legend:{{display:false}}}},scales:{{y:{{max:3,ticks:{{stepSize:1}},title:{{display:true,text:'Risk Score'}}}}}},indexAxis:'y',responsive:true}}
  }});
  new Chart(document.getElementById('riskPieChart'),{{
    type:'doughnut',
    data:{{labels:['Flood Overlay','Bushfire Only','Both Overlays','All Clear','Unknown'],
      datasets:[{{data:[flood_count-Math.min(flood_count,bush_count), bush_count-Math.min(flood_count,bush_count), Math.min(flood_count,bush_count), clear_count, unknown_count],
        backgroundColor:['#e74c3c','#f39c12','#c0392b','#1a7a4a','#95a5a6']}}]}},
    options:{{plugins:{{legend:{{position:'bottom'}}}},responsive:true}}
  }});
}}

// ─── ASSUMPTIONS ──────────────────────────────────────────────────────────────
function renderAssumptions() {{
  const rows = [
    ['Loan Type','Interest-Only (I/O), 30-year term'],
    ['Investor Rate',(assump.interest_rate*100).toFixed(2)+'% p.a.'],
    ['Deposit',(assump.deposit_pct*100)+'%'],
    ['Capital Growth Rate',(assump.cap_growth_rate*100).toFixed(0)+'% p.a. (corridor hist. avg ~8–10%)'],
    ['Rental Growth Rate',(assump.rental_growth*100).toFixed(0)+'% p.a.'],
    ['Vacancy Allowance',(assump.vacancy_rate*100).toFixed(0)+'% (~2 weeks/year)'],
    ['Property Management',(assump.pm_rate*100).toFixed(1)+'% of gross rent'],
    ['Maintenance Reserve','0.8% of purchase price p.a.'],
    ["Eamon's Marginal Rate",(assump.marginal_rate_eamon*100)+'% (>$190k, incl Medicare)'],
    ["Nadeene's Marginal Rate",(assump.marginal_rate_nadeene*100)+'% (~$150–190k)'],
    ['CGT Treatment','50% discount; split 50/50; taxed at respective rates'],
    ['Selling Costs on Exit',(assump.selling_costs_pct*100).toFixed(1)+'% of sale price'],
  ];
  document.getElementById('assumpTable').innerHTML = `<table>
    <thead><tr><th style="width:38%">Assumption</th><th>Value</th></tr></thead>
    <tbody>${{rows.map((r,i)=>`<tr ${{i%2?'style="background:var(--lgrey)"':''}}>
      <td><strong>${{r[0]}}</strong></td><td>${{r[1]}}</td></tr>`).join('')}}
    </tbody></table>`;

  // Rate sensitivity
  const top = ranked[0];
  const rates = [5.50,5.75,6.00,6.20,6.45,6.75,7.00,7.50];
  document.getElementById('rateSens').innerHTML = `
    <p style="margin-bottom:10px;font-size:12px;color:#555">Based on <strong>${{sAddr(top.address)}}</strong> (price ${{fmt(top.purchase_price||top.purchase_price_assumed)}}, rent $${{top.weekly_rent||top.weekly_rent_est}}/wk)</p>
    <div class="sens-grid">${{rates.map(r=>{{
      const loan=(top.purchase_price||top.purchase_price_assumed)*(1-assump.deposit_pct);
      const intC=loan*r/100;
      const ar=(top.weekly_rent||top.weekly_rent_est)*52;
      const eff=ar*(1-assump.vacancy_rate);
      const other=ar*assump.pm_rate+ar*assump.vacancy_rate+2500+1200+1900+(top.purchase_price||top.purchase_price_assumed)*0.008;
      const depr=(top.yr1_div43||0)+(top.yr1_div40||0);
      const taxable=eff-other-intC-depr;
      const tax=-taxable*assump.avg_marginal;
      const pw=Math.round((eff-other-intC+tax)/52);
      const isBase=r===6.20;
      return `<div class="sens-cell ${{isBase?'base':''}}">
        <div class="s-label">${{r.toFixed(2)}}%${{isBase?' ◀':''}}</div>
        <div class="s-val" style="color:${{cfColor(pw)}}">${{pw>=0?'+':''}}$${{pw}}/wk</div>
      </div>`;
    }}).join('')}}</div>`;

  // Growth sensitivity
  const growths = [4,5,6,7,8,9,10];
  document.getElementById('growthSens').innerHTML = `
    <div class="sens-grid">${{growths.map(g=>{{
      const price=top.purchase_price||top.purchase_price_assumed;
      const loan=price*(1-assump.deposit_pct);
      const upfront=-(top.total_upfront);
      let cfs=[upfront]; let rw=top.weekly_rent||top.weekly_rent_est;
      for(let yr=1;yr<=10;yr++){{
        const ar=rw*52;const eff=ar*(1-assump.vacancy_rate);
        const other=ar*assump.pm_rate+ar*assump.vacancy_rate+2500+1200+1900+price*0.008;
        const intC=loan*assump.interest_rate;
        const depr=(top.yr1_div43||12000)+(top.yr1_div40||8000)*(0.8**(yr-1));
        const tax=-(eff-other-intC-depr)*assump.avg_marginal;
        cfs.push(Math.round(eff-other-intC+tax));
        rw*=(1+assump.rental_growth);
      }}
      const ev10=price*Math.pow(1+g/100,10);
      const cgt=(ev10-price)*assump.cgt_discount*0.5*(assump.marginal_rate_eamon+assump.marginal_rate_nadeeen||0.92);
      cfs[10]+=ev10-loan-ev10*assump.selling_costs_pct-cgt;
      let lo=-0.5,hi=1,irr=0.1;
      for(let i=0;i<80;i++){{const mid=(lo+hi)/2;const n=cfs.reduce((s,c,t)=>s+c/Math.pow(1+mid,t),0);if(Math.abs(n)<100){{irr=mid;break;}}n>0?lo=mid:hi=mid;irr=mid;}}
      const isBase=g===7;
      return `<div class="sens-cell ${{isBase?'base':''}}">
        <div class="s-label">${{g}}% p.a.${{isBase?' ◀':''}}</div>
        <div class="s-val" style="color:var(--navy)">${{(irr*100).toFixed(1)}}% IRR</div>
      </div>`;
    }}).join('')}}</div>`;
}}

// ─── SCENARIO PLANNER ────────────────────────────────────────────────────────
let scCharts = {{}};

// Default scenario values from loaded assumptions
const SC_DEFAULTS = {{
  interest_rate:    assump.interest_rate   || 0.062,
  deposit_pct:      assump.deposit_pct     || 0.20,
  cap_growth_rate:  assump.cap_growth_rate || 0.07,
  rental_growth:    assump.rental_growth   || 0.04,
  vacancy_rate:     assump.vacancy_rate    || 0.04,
  pm_rate:          assump.pm_rate         || 0.085,
  inflation:        0.03,
  marginal_rate_e:  assump.marginal_rate_eamon || 0.47,
  marginal_rate_n:  assump.marginal_rate_nadeene || 0.45,
}};

let scGlobal = Object.assign({{}}, SC_DEFAULTS);

function buildScenarioControls() {{
  const sliders = [
    {{ key:'interest_rate',   label:'Interest Rate (I/O)',   min:3,   max:10,  step:0.05, fmt: v=>(v*100).toFixed(2)+'%' }},
    {{ key:'deposit_pct',     label:'Deposit %',             min:10,  max:30,  step:1,    fmt: v=>(v*100).toFixed(0)+'%' }},
    {{ key:'cap_growth_rate', label:'Capital Growth Rate',   min:2,   max:12,  step:0.5,  fmt: v=>(v*100).toFixed(1)+'%' }},
    {{ key:'rental_growth',   label:'Annual Rent Growth',    min:0,   max:8,   step:0.5,  fmt: v=>(v*100).toFixed(1)+'%' }},
    {{ key:'vacancy_rate',    label:'Vacancy Allowance',     min:0,   max:10,  step:0.5,  fmt: v=>(v*100).toFixed(1)+'%' }},
    {{ key:'pm_rate',         label:'Property Mgmt Fee',     min:5,   max:12,  step:0.5,  fmt: v=>(v*100).toFixed(1)+'%' }},
    {{ key:'inflation',       label:'Inflation (CPI)',        min:1,   max:6,   step:0.25, fmt: v=>(v*100).toFixed(2)+'%' }},
    {{ key:'marginal_rate_e', label:"Eamon's Tax Rate",      min:30,  max:50,  step:1,    fmt: v=>(v*100).toFixed(0)+'%' }},
    {{ key:'marginal_rate_n', label:"Nadeene's Tax Rate",    min:30,  max:50,  step:1,    fmt: v=>(v*100).toFixed(0)+'%' }},
  ];
  const container = document.getElementById('globalControls');
  container.innerHTML = sliders.map(s => {{
    const rawVal = scGlobal[s.key];
    const sliderVal = s.key.endsWith('_rate')||s.key==='deposit_pct'||s.key==='pm_rate'||s.key==='inflation' ? rawVal*100 : rawVal*100;
    return `<div class="sc-control">
      <label>${{s.label}}</label>
      <div class="sc-row">
        <input type="range" id="sl_${{s.key}}" min="${{s.min}}" max="${{s.max}}" step="${{s.step}}"
          value="${{(rawVal*100).toFixed(4)}}"
          oninput="document.getElementById('sv_${{s.key}}').textContent=s.fmt?s.fmt(this.value/100):this.value+'%'; scGlobal['${{s.key}}']=parseFloat(this.value)/100">
        <span class="sc-val" id="sv_${{s.key}}">${{s.fmt(rawVal)}}</span>
      </div>
    </div>`;
  }}).join('');

  // Per-property overrides
  const po = document.getElementById('propOverrides');
  po.innerHTML = ranked.map((p,i) => {{
    const addr = p.address;
    const rent = p.weekly_rent || p.weekly_rent_est || 700;
    const price = p.purchase_price || p.purchase_price_assumed || 900000;
    return `<div class="prop-override-row">
      <div><div class="pname">${{sAddr(addr)}}</div><div class="psuburb">${{p.suburb}} · IRR ${{pct(p.irr||0)}} (original)</div></div>
      <div class="override-field">
        <label>Weekly Rent ($)</label>
        <input type="number" id="or_rent_${{i}}" value="${{rent}}" min="300" max="2000" step="10" data-addr="${{addr}}">
      </div>
      <div class="override-field">
        <label>Purchase Price ($)</label>
        <input type="number" id="or_price_${{i}}" value="${{price}}" min="500000" max="2000000" step="5000" data-addr="${{addr}}">
      </div>
    </div>`;
  }}).join('');
}}

function qlStampDuty(price) {{
  if(price<=5000)       return 0;
  if(price<=75000)      return 1.5*(price-5000)/100;
  if(price<=540000)     return 1050+3.5*(price-75000)/100;
  if(price<=1000000)    return 17325+4.5*(price-540000)/100;
  return 38025+5.75*(price-1000000)/100;
}}

function scDepreciation(buildYear, price, yr) {{
  const age = 2026 - (buildYear||2015);
  const div43 = ((40-age-(yr-1))>0) ? Math.round(price*0.55*0.025) : 0;
  let base40 = age<=3?12000:age<=7?8000:age<=12?4500:2000;
  const div40 = Math.round(base40*Math.pow(0.8,yr-1));
  return {{div43, div40}};
}}

function scIRR(cashflows) {{
  let lo=-0.9, hi=5, irr=0.1;
  for(let i=0;i<120;i++) {{
    const mid=(lo+hi)/2;
    const npv=cashflows.reduce((s,c,t)=>s+c/Math.pow(1+mid,t),0);
    if(Math.abs(npv)<1) {{ irr=mid; break; }}
    npv>0 ? lo=mid : hi=mid;
    irr=mid;
  }}
  return isFinite(irr)?irr:null;
}}

function scModel(p, g) {{
  const price  = parseFloat(p._scPrice  || p.purchase_price || p.purchase_price_assumed);
  const rentWk = parseFloat(p._scRent   || p.weekly_rent || p.weekly_rent_est || 700);
  const build  = p.build_year_est || 2015;
  const stamp  = qlStampDuty(price);
  const upfront= price*g.deposit_pct + stamp + 2400;
  const loan   = price*(1-g.deposit_pct);
  const intAnn = loan*g.interest_rate;
  const avgMarg= (g.marginal_rate_e+g.marginal_rate_n)/2;

  const yearly=[]; const cfs=[-upfront]; let cum=0; let rw=rentWk;
  for(let yr=1;yr<=10;yr++) {{
    const ar=rw*52, eff=ar*(1-g.vacancy_rate), pm=ar*g.pm_rate;
    const vacloss=ar*g.vacancy_rate, maint=price*0.008;
    const other=pm+vacloss+2500+1200+1900+maint;
    const {{div43,div40}}=scDepreciation(build,price,yr);
    const depr=div43+div40;
    const taxable=eff-other-intAnn-depr;
    const tax=-taxable*avgMarg;
    const pretax=eff-other-intAnn;
    const at=pretax+tax; cum+=at;
    const pv=Math.round(price*Math.pow(1+g.cap_growth_rate,yr));
    const equity=pv-loan;
    const sc=pv*0.025;
    const gg=pv-price;
    const cgt=gg>0?Math.round((gg*0.5*0.5*g.marginal_rate_e)+(gg*0.5*0.5*g.marginal_rate_n)):0;
    const netSold=Math.round(pv-loan-sc-cgt);
    yearly.push({{year:yr,prop_value:pv,equity:Math.round(equity),gross_rent:Math.round(ar),
      effective_rent:Math.round(eff),interest:Math.round(intAnn),
      div43,div40,total_depreciation:depr,taxable_income:Math.round(taxable),
      tax_impact:Math.round(tax),pretax_cashflow:Math.round(pretax),
      aftertax_cashflow:Math.round(at),aftertax_cashflow_pw:Math.round(at/52),
      cumulative_aftertax_cashflow:Math.round(cum),net_proceeds_if_sold:netSold,
      total_wealth_created:Math.round(equity+cum)}});
    cfs.push(Math.round(at)); rw*=(1+g.rental_growth);
  }}
  const ev10=yearly[9].prop_value, sc10=Math.round(ev10*0.025);
  const gg10=ev10-price;
  const cgt10=gg10>0?Math.round((gg10*0.5*0.5*g.marginal_rate_e)+(gg10*0.5*0.5*g.marginal_rate_n)):0;
  const net10=Math.round(ev10-loan-sc10-cgt10);
  cfs[10]+=net10;
  const irr=scIRR(cfs);
  const npv7=cfs.reduce((s,c,t)=>s+c/Math.pow(1.07,t),0);
  const gYield=Math.round(rentWk*52/price*10000)/100;
  const nYield=Math.round(rentWk*52*(1-g.vacancy_rate)/price*10000)/100;
  return {{
    ...p, _scApplied:true,
    purchase_price:price, weekly_rent:rentWk,
    deposit:Math.round(price*g.deposit_pct),
    stamp_duty:Math.round(stamp), total_upfront:Math.round(upfront),
    loan_amount:Math.round(loan), annual_interest:Math.round(intAnn),
    gross_yield:gYield, net_yield:nYield,
    yr1_aftertax_cashflow_pw:yearly[0].aftertax_cashflow_pw,
    yr1_div43:yearly[0].div43, yr1_div40:yearly[0].div40,
    yr1_tax_impact:yearly[0].tax_impact,
    irr:irr?Math.round(irr*10000)/100:null, npv_7pct:Math.round(npv7),
    total_equity_yr10:yearly[9].equity, exit_value:ev10,
    gross_capital_gain:gg10, selling_costs_exit:sc10, cgt_payable:cgt10,
    net_proceeds:net10, total_wealth_yr10:yearly[9].total_wealth_created,
    yearly,
  }};
}}

let scResults = null;
let scDone = false;

function applyScenario() {{
  // Read per-property overrides
  ranked.forEach((p,i) => {{
    const rentEl  = document.getElementById('or_rent_'+i);
    const priceEl = document.getElementById('or_price_'+i);
    if(rentEl)  p._scRent  = parseFloat(rentEl.value)  || (p.weekly_rent||700);
    if(priceEl) p._scPrice = parseFloat(priceEl.value) || (p.purchase_price||900000);
  }});
  scResults = ranked.map(p => scModel(p, scGlobal));
  scResults.sort((a,b)=>(b.irr||0)-(a.irr||0));
  renderScenarioResults();
  scDone = true;
}}

function resetScenario() {{
  scGlobal = Object.assign({{}}, SC_DEFAULTS);
  ranked.forEach(p => {{ delete p._scRent; delete p._scPrice; }});
  buildScenarioControls();
  // Reset sliders display
  Object.keys(SC_DEFAULTS).forEach(k => {{
    const sl = document.getElementById('sl_'+k);
    const sv = document.getElementById('sv_'+k);
    if(sl) sl.value = (SC_DEFAULTS[k]*100).toFixed(4);
  }});
  applyScenario();
}}

function renderScenarioResults() {{
  if(!scResults) return;
  const res = scResults;

  // Table
  const tbl = document.getElementById('scenarioTable');
  tbl.innerHTML = `<thead><tr>
    <th>Rank</th><th>Address</th><th>Suburb</th>
    <th class="c">Price</th><th class="c">Beds</th><th class="c">Land m²</th><th class="c">Build Yr</th>
    <th class="c">Rent/Wk</th><th class="c">Gross Yld</th><th class="c">$/Wk (AT)</th>
    <th class="c">IRR</th><th class="c">10yr Equity</th>
    <th class="c">NPV@7%</th><th class="c">Total Wealth Yr10</th>
  </tr></thead><tbody>${{res.map((p,i)=>{{
    const v = p.yr1_aftertax_cashflow_pw||0;
    const beds = p.bedrooms != null ? p.bedrooms : '—';
    const land = p.land_size_m2 != null ? p.land_size_m2 + 'm²' : (p.land_size_listed != null ? p.land_size_listed + 'm²' : '—');
    const buildYr = p.build_year_est || p.build_year_domain || '—';
    return `<tr class="${{i===0?'hi-row':i===1?'hi-row am':''}}">
      <td><span class="chip ${{i===0?'n':i===1?'b':'gr'}}">#${{i+1}}${{i===0?' ★':''}}</span></td>
      <td><strong>${{sAddr(p.address)}}</strong></td><td>${{p.suburb}}</td>
      <td class="c">${{fmt(p.purchase_price)}}</td>
      <td class="c">${{beds}}</td>
      <td class="c">${{land}}</td>
      <td class="c">${{buildYr}}</td>
      <td class="c">$${{p.weekly_rent}}/wk</td>
      <td class="c">${{pct(p.gross_yield)}}</td>
      <td class="c"><span class="chip" style="background:${{cfBg(v)}};color:${{cfColor(v)}}">${{v>=0?'+':''}}$${{v}}/wk</span></td>
      <td class="c"><strong>${{pct(p.irr)}}</strong></td>
      <td class="c">${{fmt(p.total_equity_yr10)}}</td>
      <td class="c">${{fmt(p.npv_7pct)}}</td>
      <td class="c"><strong>${{fmt(p.total_wealth_yr10)}}</strong></td>
    </tr>`;
  }}).join('')}}</tbody>`;

  // Charts
  Object.values(scCharts).forEach(c=>c.destroy()); scCharts={{}};
  const labs = res.map(p=>sAddr(p.address));

  scCharts.irr = new Chart(document.getElementById('scIrrChart'),{{
    type:'bar',
    data:{{labels:labs,datasets:[
      {{label:'Scenario IRR',data:res.map(p=>p.irr||0),backgroundColor:COLOURS,borderRadius:5}},
      {{label:'Original IRR',data:res.map(p=>{{const orig=props.find(x=>x.address===p.address);return orig?(orig.irr||0):0;}}),backgroundColor:'#bbbbbb66',borderRadius:5}}
    ]}},
    options:{{plugins:{{legend:{{position:'top'}}}},scales:{{y:{{title:{{display:true,text:'IRR %'}}}}}},indexAxis:'y',responsive:true}}
  }});
  scCharts.cf = new Chart(document.getElementById('scCfChart'),{{
    type:'bar',
    data:{{labels:labs,datasets:[{{
      data:res.map(p=>p.yr1_aftertax_cashflow_pw||0),
      backgroundColor:res.map(p=>cfBg(p.yr1_aftertax_cashflow_pw||0)),
      borderColor:res.map(p=>cfColor(p.yr1_aftertax_cashflow_pw||0)),
      borderWidth:2,borderRadius:5
    }}]}},
    options:{{plugins:{{legend:{{display:false}}}},scales:{{y:{{title:{{display:true,text:'$/week'}}}}}},indexAxis:'y',responsive:true}}
  }});
  scCharts.eq = new Chart(document.getElementById('scEqChart'),{{
    type:'bar',
    data:{{labels:labs,datasets:[
      {{label:'Loan Balance',data:res.map(p=>p.loan_amount||0),backgroundColor:'#e0e0e0',borderRadius:3}},
      {{label:'Equity Yr10', data:res.map(p=>p.total_equity_yr10||0),backgroundColor:COLOURS,borderRadius:3}}
    ]}},
    options:{{plugins:{{legend:{{position:'top'}}}},scales:{{x:{{stacked:true}},y:{{stacked:true,title:{{display:true,text:'$'}}}}}},indexAxis:'y',responsive:true}}
  }});
  scCharts.wealth = new Chart(document.getElementById('scWealthChart'),{{
    type:'bar',
    data:{{labels:labs,datasets:[{{
      label:'Total Wealth Yr10',data:res.map(p=>p.total_wealth_yr10||0),
      backgroundColor:COLOURS,borderRadius:5
    }}]}},
    options:{{plugins:{{legend:{{display:false}}}},scales:{{y:{{title:{{display:true,text:'$'}}}}}},indexAxis:'y',responsive:true}}
  }});
}}

// ─── INIT ─────────────────────────────────────────────────────────────────────
renderOverview();
</script>
</body>
</html>
"""

with open(out_path, 'w') as f:
    f.write(html)

size_kb = len(html)//1024
print(f"✓ Site v2 written ({size_kb}KB) → {out_path}")
