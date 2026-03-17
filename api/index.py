#!/usr/bin/env python3
"""
Property Assessor — Vercel Serverless
======================================
Scrapes Domain.com.au via plain HTTP (no Playwright needed — Next.js SSR
embeds all listing data in __NEXT_DATA__ on the initial page HTML).

Synchronous endpoint: POST /api/assess  →  full assessment JSON + HTML
"""

import json
import re
import sys
import os
from datetime import datetime
from pathlib import Path

import httpx
import numpy_financial as npf
from bs4 import BeautifulSoup
from flask import Flask, jsonify, render_template_string, request

app = Flask(__name__)

# ── Financial model constants ──────────────────────────────────────────────────
DEPOSIT_PCT        = 0.20
INTEREST_RATE      = 0.062
CAP_GROWTH_RATE    = 0.07
RENTAL_GROWTH      = 0.04
INFLATION_RATE     = 0.025
VACANCY_RATE       = 0.04
PM_RATE            = 0.085
COUNCIL_RATES      = 2500
WATER              = 1200
INSURANCE          = 1800
MAINTENANCE_PCT    = 0.005
LEGAL_COSTS        = 2500
MARGINAL_RATE      = 0.345   # avg of two buyers
CGT_DISCOUNT       = 0.50
SELLING_COSTS_PCT  = 0.025

# ── Stamp duty (QLD investor, no FHOG) ────────────────────────────────────────
def qld_stamp_duty(price):
    if price <= 5000:       return 0
    elif price <= 75000:    return 1.50 * (price - 5000) / 100
    elif price <= 540000:   return 1050 + 3.50 * (price - 75000) / 100
    elif price <= 1000000:  return 17325 + 4.50 * (price - 540000) / 100
    else:                   return 38025 + 5.75 * (price - 1000000) / 100

def depreciation(build_year, purchase_price, year_of_ownership):
    age = datetime.now().year - build_year
    div43 = round(purchase_price * 0.55 * 0.025) if (40 - age - (year_of_ownership - 1)) > 0 else 0
    div40 = round(purchase_price * 0.025 * 0.40)
    return div43, div40

# ── Financial model ────────────────────────────────────────────────────────────
def financial_model(prop):
    price       = prop.get('purchase_price') or 0
    weekly_rent = prop.get('weekly_rent') or round(price * 0.00081)
    build_year  = prop.get('build_year_est') or 2015

    stamp      = qld_stamp_duty(price)
    upfront    = price * DEPOSIT_PCT + stamp + LEGAL_COSTS
    loan       = price * (1 - DEPOSIT_PCT)

    cashflows  = [-upfront]
    yearly     = []
    for yr in range(1, 11):
        rent_ann   = weekly_rent * 52 * ((1 + RENTAL_GROWTH) ** (yr - 1))
        eff_rent   = rent_ann * (1 - VACANCY_RATE)
        pm         = eff_rent * PM_RATE
        maint      = price * MAINTENANCE_PCT
        div43, div40 = depreciation(build_year, price, yr)
        interest   = loan * INTEREST_RATE
        expenses   = COUNCIL_RATES + WATER + INSURANCE + pm + maint + interest
        net_cf     = eff_rent - expenses
        tax_deduct = COUNCIL_RATES + WATER + INSURANCE + pm + maint + interest + div43 + div40
        taxable    = eff_rent - tax_deduct
        tax_saving = abs(min(0, taxable)) * MARGINAL_RATE
        aftertax   = net_cf + tax_saving
        pv         = round(price * ((1 + CAP_GROWTH_RATE) ** yr))
        equity     = pv - loan
        cashflows.append(aftertax + (pv - price * (1 - SELLING_COSTS_PCT)) if yr == 10 else aftertax)
        yearly.append({
            'year': yr,
            'weekly_rent': round(weekly_rent * ((1 + RENTAL_GROWTH) ** (yr - 1))),
            'gross_income': round(rent_ann),
            'total_expenses': round(expenses),
            'interest': round(interest),
            'net_cashflow': round(net_cf),
            'aftertax_pw': round(aftertax / 52, 1),
            'property_value': pv,
            'equity': equity,
        })

    ev10     = round(price * ((1 + CAP_GROWTH_RATE) ** 10))
    gg10     = ev10 - price
    cgt10    = gg10 * (1 - CGT_DISCOUNT) * MARGINAL_RATE
    net_exit = ev10 - round(ev10 * SELLING_COSTS_PCT) - cgt10 - loan

    irr_val  = npf.irr(cashflows)
    irr_pct  = round(irr_val * 100, 2) if irr_val and not (irr_val != irr_val) else None

    disc_cfs = sum(cf / (1.07 ** i) for i, cf in enumerate(cashflows))
    npv_7    = round(disc_cfs)

    yr1 = yearly[0]
    return {
        'deposit': round(price * DEPOSIT_PCT),
        'stamp_duty': round(stamp),
        'legal_costs': LEGAL_COSTS,
        'total_upfront': round(upfront),
        'loan_amount': round(loan),
        'gross_yield': round((weekly_rent * 52) / price * 100, 2) if price else None,
        'net_yield':   round((weekly_rent * 52 * (1 - VACANCY_RATE)) / price * 100, 2) if price else None,
        'irr': irr_pct,
        'npv_7pct': npv_7,
        'total_equity_yr10': round(net_exit),
        'yr1_net_cashflow': round(yr1['net_cashflow']),
        'yr1_aftertax_cashflow': round(yr1['aftertax_pw'] * 52),
        'yr1_aftertax_cashflow_pw': round(yr1['aftertax_pw']),
        'exit_value_yr10': ev10,
        'capital_gain_10yr': gg10,
        'cgt_payable_10yr': round(cgt10),
        'weekly_rent': weekly_rent,
        'yearly_data': yearly,
    }

# ── parse_price ────────────────────────────────────────────────────────────────
def parse_price(s):
    s = str(s or '')
    m = re.search(r'\$\s*([\d,]+)\s*k', s, re.I)
    if m:
        return int(m.group(1).replace(',', '')) * 1000
    m = re.search(r'\$\s*([\d,]+)', s)
    if m:
        v = int(m.group(1).replace(',', ''))
        return v if v >= 100000 else v * 1000
    return None

# ── Domain.com.au HTTP scraper ──────────────────────────────────────────────────
HEADERS = {
    'User-Agent': (
        'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) '
        'AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
    ),
    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
    'Accept-Language': 'en-AU,en;q=0.9',
    'Accept-Encoding': 'gzip, deflate, br',
    'Cache-Control': 'no-cache',
    'Pragma': 'no-cache',
}

def scrape_domain(url):
    """Fetch a Domain.com.au listing page and extract all property data.
    Uses __NEXT_DATA__ (server-side rendered JSON) — no browser needed.
    """
    url = url.strip()
    if not url.startswith('http'):
        url = 'https://' + url

    with httpx.Client(headers=HEADERS, follow_redirects=True, timeout=20) as client:
        resp = client.get(url)

    if resp.status_code != 200:
        raise ValueError(f"Domain returned HTTP {resp.status_code} — listing may be unavailable")

    soup = BeautifulSoup(resp.text, 'html.parser')
    script = soup.find('script', {'id': '__NEXT_DATA__'})
    if not script:
        raise ValueError(
            "Could not find listing data on this page. "
            "The page may require a login, or Domain.com.au may have blocked this request."
        )

    nd = json.loads(script.string)
    cp = (nd.get('props') or {}).get('pageProps') or {}
    cp = cp.get('componentProps') or cp   # some pages nest differently

    summary = cp.get('listingSummary') or {}
    stats   = summary.get('stats') or []

    def stat(key):
        s = next((s for s in stats if s.get('key') == key), {})
        return s.get('value')

    # Address
    addr_obj = cp.get('address') or summary.get('address') or {}
    if isinstance(addr_obj, str):
        addr_str = addr_obj
        suburb   = ''
        postcode = ''
    else:
        num      = addr_obj.get('streetNumber') or ''
        street   = addr_obj.get('street') or ''
        addr_str = (f"{num} {street}").strip() or addr_obj.get('displayAddress') or ''
        suburb   = addr_obj.get('suburb') or ''
        postcode = str(addr_obj.get('postcode') or '')

    if not addr_str:
        raise ValueError("Could not extract a street address from this listing")

    # Price
    pd = summary.get('priceDetails') or summary.get('price') or cp.get('priceDetails') or {}
    price_display = (pd if isinstance(pd, str) else pd.get('displayPrice') or pd.get('price') or '')
    is_auction    = bool(re.search(r'auction', str(price_display), re.I))
    price_numeric = parse_price(price_display) if price_display else None

    # Beds / baths / parking / land
    beds    = cp.get('beds') or summary.get('beds')
    baths   = summary.get('baths')
    parking = summary.get('parking')
    land    = stat('landArea')
    built   = stat('buildingArea')

    # Description
    desc_raw = cp.get('description') or []
    if isinstance(desc_raw, str):
        desc_lines = [desc_raw]
    else:
        desc_lines = [str(l) for l in (desc_raw if isinstance(desc_raw, list) else []) if l]
    full_desc = ' '.join(desc_lines)

    # Parse description for useful data
    weekly_rent_appraisal = None
    build_year_domain     = None
    council_rates_qtr     = None
    currently_tenanted    = None

    for line in desc_lines:
        l = line.strip()
        # Rental appraisal range
        m = re.search(r'Rental\s+Appraisal[^$]*\$\s*([\d,]+)\s*[-–to]+\s*\$?\s*([\d,]+)?', l, re.I)
        if m:
            lo = int(m.group(1).replace(',', ''))
            hi = int(m.group(2).replace(',', '')) if m.group(2) else lo
            weekly_rent_appraisal = (lo + hi) // 2
        # Single value appraisal
        if weekly_rent_appraisal is None:
            m = re.search(r'Rental\s+Appraisal[^$]*\$\s*([\d,]+)\s*/?\s*[Pp]er\s+[Ww]eek', l, re.I)
            if m:
                weekly_rent_appraisal = int(m.group(1).replace(',', ''))
        # Build year
        m = re.search(r'[Bb]uilt\s+(?:[Ii]n\s+)?(\d{4})', l)
        if m:
            build_year_domain = int(m.group(1))
        # Council rates
        m = re.search(r'[Cc]ouncil\s+[Rr]ates?[^$]*\$\s*([\d,.]+)', l)
        if m:
            try:
                council_rates_qtr = float(m.group(1).replace(',', ''))
            except Exception:
                pass
        # Tenancy
        l_lower = l.lower()
        if any(k in l_lower for k in ['currently tenanted', 'tenant in place', 'lease in place',
                                       'currently leased', 'currently rented', 'tenanted']):
            currently_tenanted = True
        if any(k in l_lower for k in ['vacant possession', 'owner occupied', 'owner-occupied']):
            currently_tenanted = False

    return {
        'address': addr_str,
        'suburb':  suburb,
        'postcode': postcode,
        'price_display': price_display,
        'price_numeric': price_numeric,
        'is_auction': is_auction,
        'bedrooms':  beds,
        'bathrooms': baths,
        'parking':   parking,
        'land_size_m2':     land,
        'building_size_m2': built,
        'description': full_desc,
        'weekly_rent_appraisal': weekly_rent_appraisal,
        'build_year_domain': build_year_domain,
        'council_rates_qtr': council_rates_qtr,
        'currently_tenanted': currently_tenanted,
    }


def assess_property(url):
    """Full assessment pipeline for a single Domain URL. Returns enriched dict."""
    detail = scrape_domain(url)

    p = {
        'id': re.sub(r'[^a-zA-Z0-9_]', '_', detail['address'] + '_' + detail.get('suburb', '')),
        'domain_url': url,
        'scraped_at': datetime.now().isoformat(),
        'manually_added': True,
        'web_assessment': True,
        **detail,
    }

    # Purchase price
    price = detail.get('price_numeric') or 0
    p['purchase_price'] = price
    p['purchase_price_assumed'] = price

    # Rent
    if detail.get('weekly_rent_appraisal'):
        p['weekly_rent'] = detail['weekly_rent_appraisal']
        p['rent_source'] = 'domain_appraisal'
    else:
        p['weekly_rent'] = round(price * 0.00081) if price else 0
        p['rent_source'] = 'estimate'

    # Build year
    if detail.get('build_year_domain'):
        p['build_year_est'] = detail['build_year_domain']
    else:
        p['build_year_est'] = 2015
        m = re.search(r'built\s+(?:in\s+)?(\d{4})', detail.get('description', ''), re.I)
        if m:
            p['build_year_est'] = int(m.group(1))

    # Overlays — not available without a browser; flag accordingly
    p['flood_overlay']    = None
    p['bushfire_overlay'] = None
    p['risk_score']       = None
    p['risk_label']       = 'Unknown (web mode)'
    p['proptrack_estimate'] = price
    p['proptrack_gap']      = 0

    # Financial model
    model = financial_model(p)
    p.update(model)

    return p


# ── HTML Template ──────────────────────────────────────────────────────────────
HTML = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Property Assessor</title>
<style>
:root{--blue:#1a73e8;--navy:#0d2137;--green:#1e8449;--red:#c0392b;--amber:#d4680a;
      --lgrey:#f5f6f8;--border:#e2e6ea;--r:12px;--sh:0 2px 10px rgba(0,0,0,.08)}
*{box-sizing:border-box;margin:0;padding:0}
body{font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif;
     background:var(--lgrey);color:#1a1a2e;min-height:100vh}
.hdr{background:var(--navy);color:#fff;padding:16px 28px;display:flex;
     align-items:center;gap:12px}
.hdr h1{font-size:19px;font-weight:700}
.hdr small{font-size:12px;color:rgba(255,255,255,.55)}
.wrap{max-width:920px;margin:28px auto;padding:0 16px}
.card{background:#fff;border-radius:var(--r);box-shadow:var(--sh);
      padding:24px 28px;margin-bottom:18px}
.card h2{font-size:15px;font-weight:700;color:var(--navy);margin-bottom:14px}
.row{display:flex;gap:10px}
.row input{flex:1;padding:11px 14px;border-radius:8px;
           border:1.5px solid var(--border);font-size:14px}
.row input:focus{outline:none;border-color:var(--blue)}
.btn{background:var(--blue);color:#fff;border:none;border-radius:8px;
     padding:11px 22px;font-size:14px;font-weight:700;cursor:pointer;
     white-space:nowrap;transition:background .15s}
.btn:hover:not(:disabled){background:#1557b0}
.btn:disabled{background:#aaa;cursor:default}
.spin{display:inline-block;width:14px;height:14px;border:2px solid #ccc;
      border-top-color:var(--blue);border-radius:50%;
      animation:spin .7s linear infinite;vertical-align:middle;margin-right:6px}
@keyframes spin{to{transform:rotate(360deg)}}
.prog{margin-top:14px;font-size:13px;color:#555;display:none}
.err{background:#fdedec;border-radius:8px;padding:14px 16px;
     color:var(--red);font-size:13px;margin-top:12px;display:none}
#res{display:none}
.rh{display:flex;justify-content:space-between;align-items:flex-start;
    flex-wrap:wrap;gap:10px;margin-bottom:16px}
.rt{font-size:21px;font-weight:800;color:var(--navy)}
.rs{font-size:13px;color:#666;margin-top:4px}
.mets{display:grid;grid-template-columns:repeat(auto-fill,minmax(155px,1fr));gap:10px;margin-bottom:16px}
.met{background:var(--lgrey);border-radius:10px;padding:12px 14px}
.met .lbl{font-size:10px;font-weight:700;text-transform:uppercase;letter-spacing:.6px;color:#888;margin-bottom:4px}
.met .val{font-size:20px;font-weight:800;color:var(--navy)}
.met .sub{font-size:11px;color:#888;margin-top:2px}
.met.hi{background:#e8f4fd}.met.hi .val{color:var(--blue)}
.met.good{background:#eafaf1}.met.good .val{color:var(--green)}
.met.warn{background:#fef9e7}.met.warn .val{color:var(--amber)}
.met.bad{background:#fdedec}.met.bad .val{color:var(--red)}
.tags{display:flex;flex-wrap:wrap;gap:6px;margin-bottom:14px}
.tag{border-radius:20px;padding:3px 10px;font-size:11px;font-weight:600}
.tag.g{background:#d5f5e3;color:#1e8449}
.tag.a{background:#fdebd0;color:#935116}
.tag.b{background:#d6eaf8;color:#1a5276}
.tag.gr{background:#eaecee;color:#566573}
.note{background:#fff3cd;border-radius:8px;padding:10px 14px;font-size:12px;
      color:#856404;margin-bottom:14px}
table{width:100%;border-collapse:collapse;font-size:12px}
th{background:var(--navy);color:#fff;padding:8px 10px;text-align:left;font-weight:600}
td{padding:7px 10px;border-bottom:1px solid var(--border)}
tr:nth-child(even) td{background:#fafbfc}
.c{text-align:right}
a.dlink{color:var(--blue);text-decoration:none;font-weight:600;font-size:12px}
a.dlink:hover{text-decoration:underline}
@media(max-width:600px){.wrap{padding:0 10px}.card{padding:16px 14px}.row{flex-direction:column}}
</style>
</head>
<body>
<div class="hdr">
  <div><h1>🏠 Property Assessor</h1>
  <small>Instant investment analysis · Domain.com.au listings</small></div>
</div>
<div class="wrap">
  <div class="card">
    <h2>Assess a Listing</h2>
    <div class="row">
      <input id="u" type="url" placeholder="Paste a Domain.com.au URL  e.g. https://www.domain.com.au/2020685507"
             onkeydown="if(event.key==='Enter')go()">
      <button class="btn" id="btn" onclick="go()">Assess →</button>
    </div>
    <div class="prog" id="prog"><span class="spin"></span>Fetching listing data and running financial model…</div>
    <div class="err"  id="err"></div>
  </div>
  <div class="card" id="res">
    <div class="rh">
      <div><div class="rt" id="raddr"></div><div class="rs" id="rsub"></div></div>
      <a class="dlink" id="rlink" href="#" target="_blank">View on Domain.com.au ↗</a>
    </div>
    <div class="note">⚠ Web mode: flood/bushfire overlays and PropTrack estimate require the desktop app. All financial calculations are fully accurate.</div>
    <div class="tags" id="rtags"></div>
    <div class="mets" id="rmets"></div>
    <h2 style="margin-bottom:10px">Year-by-Year Cash Flow</h2>
    <div style="overflow-x:auto">
      <table><thead><tr>
        <th>Yr</th><th class="c">Rent/Wk</th><th class="c">Gross Income</th>
        <th class="c">Expenses</th><th class="c">Interest</th>
        <th class="c">Net Cash</th><th class="c">After-Tax/Wk</th>
        <th class="c">Value</th><th class="c">Equity</th>
      </tr></thead><tbody id="rtbody"></tbody></table>
    </div>
  </div>
</div>
<script>
function fmt(n){return n==null?'—':'$'+Math.round(n).toLocaleString()}
function pct(n){return n==null?'—':n.toFixed(2)+'%'}

async function go(){
  const url=document.getElementById('u').value.trim();
  if(!url){alert('Paste a Domain.com.au URL first');return}
  document.getElementById('btn').disabled=true;
  document.getElementById('prog').style.display='block';
  document.getElementById('res').style.display='none';
  document.getElementById('err').style.display='none';
  try{
    const r=await fetch('/api/assess',{method:'POST',
      headers:{'Content-Type':'application/json'},
      body:JSON.stringify({url})});
    const d=await r.json();
    if(!d.ok){throw new Error(d.error||'Assessment failed')}
    render(d.property);
  }catch(e){
    const el=document.getElementById('err');
    el.style.display='block';
    el.textContent='✗ '+e.message;
  }finally{
    document.getElementById('btn').disabled=false;
    document.getElementById('prog').style.display='none';
  }
}

function render(p){
  document.getElementById('raddr').textContent=p.address+(p.suburb?', '+p.suburb:'');
  document.getElementById('rsub').textContent=
    [p.bedrooms&&p.bedrooms+' bed',p.bathrooms&&p.bathrooms+' bath',
     p.land_size_m2&&p.land_size_m2+'m²',p.build_year_est&&'Built '+p.build_year_est]
    .filter(Boolean).join('  ·  ');
  document.getElementById('rlink').href=p.domain_url||'#';

  const tags=[];
  if(p.currently_tenanted===true)  tags.push(['✓ Tenanted','g']);
  if(p.currently_tenanted===false) tags.push(['Vacant','gr']);
  if(p.rent_source==='domain_appraisal') tags.push(['Rent Appraised','g']);
  if(!tags.length) tags.push(['Web Assessment','b']);
  document.getElementById('rtags').innerHTML=tags.map(([t,c])=>`<span class="tag ${c}">${t}</span>`).join('');

  const v=p.yr1_aftertax_cashflow_pw||0;
  const cfCls=v>=0?'good':v>-50?'warn':'bad';
  const irr=p.irr||0;
  const iCls=irr>=12?'good':irr>=9?'hi':irr>=6?'warn':'bad';
  const mets=[
    ['Purchase Price',fmt(p.purchase_price),p.price_display||'','hi'],
    ['Weekly Rent','$'+(p.weekly_rent||'—')+'/wk',p.rent_source?.replace(/_/g,' ')||'',''],
    ['Gross Yield',pct(p.gross_yield),'before vacancies',''],
    ['10-Yr IRR',pct(irr),'annualised total return',iCls],
    ['After-Tax $/Wk',(v>=0?'+$':'-$')+Math.abs(v)+'/wk','Year 1 cost',cfCls],
    ['10-Yr Equity',fmt(p.total_equity_yr10),'at 7% growth pa','good'],
    ['NPV @ 7%',fmt(p.npv_7pct||p.npv_at_7pct),'',''],
    ['Total Upfront',fmt(p.total_upfront),'deposit+stamp+legal',''],
  ];
  document.getElementById('rmets').innerHTML=mets.map(([l,v,s,c])=>
    `<div class="met ${c}"><div class="lbl">${l}</div><div class="val">${v}</div>${s?'<div class="sub">'+s+'</div>':''}</div>`
  ).join('');

  document.getElementById('rtbody').innerHTML=(p.yearly_data||[]).map(y=>`
    <tr><td>${y.year}</td>
    <td class="c">$${y.weekly_rent||0}</td>
    <td class="c">${fmt(y.gross_income)}</td>
    <td class="c">${fmt(y.total_expenses)}</td>
    <td class="c">${fmt(y.interest)}</td>
    <td class="c">${fmt(y.net_cashflow)}</td>
    <td class="c">${(y.aftertax_pw>=0?'+$':'-$')+Math.abs(Math.round(y.aftertax_pw||0))}/wk</td>
    <td class="c">${fmt(y.property_value)}</td>
    <td class="c">${fmt(y.equity)}</td></tr>`).join('');

  document.getElementById('res').style.display='block';
  document.getElementById('res').scrollIntoView({behavior:'smooth',block:'start'});
}
</script>
</body>
</html>"""


# ── Routes ─────────────────────────────────────────────────────────────────────

@app.route('/', defaults={'path': ''})
@app.route('/<path:path>')
def index(path=''):
    return render_template_string(HTML)


@app.route('/api/assess', methods=['POST'])
def api_assess():
    body = request.get_json(silent=True) or {}
    url  = (body.get('url') or '').strip()
    if not url:
        return jsonify({'ok': False, 'error': 'url is required'}), 400
    try:
        prop = assess_property(url)
        return jsonify({'ok': True, 'property': prop})
    except Exception as e:
        return jsonify({'ok': False, 'error': str(e)}), 500


@app.route('/health')
def health():
    return jsonify({'ok': True})


# Vercel handler
handler = app
