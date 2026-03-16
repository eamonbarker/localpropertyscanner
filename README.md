# Local Property Scanner

Headless investment property research tool for South-East Queensland. Scrapes live listings from Domain.com.au, enriches them with rental appraisals, flood/bushfire overlay data, tenancy status, and build-year depreciation, then generates an interactive single-file HTML dashboard with 10-year financial projections and a live scenario planner.

---

## What it does

1. **Scrapes Domain.com.au** — searches 11 SEQ suburbs for 4-bedroom houses/townhouses in the $850k–$1M range
2. **Visits each listing page** — extracts the rental appraisal, build year, land size, features, and tenancy status directly from the agent's listing description
3. **Checks property.com.au** — pulls flood overlay, bushfire overlay, PropTrack estimate, and rental history
4. **Runs a 10-year financial model** per property — IRR, NPV, after-tax cash flow, depreciation (Div 43 + Div 40), CGT on exit
5. **Builds a single-file HTML dashboard** — five tabs covering overview, projections, deep-dive, risk overlays, and a live scenario planner

All enrichment runs across **5 parallel browser tabs** simultaneously, keeping a full run under ~2 minutes for 25 properties.

---

## Suburbs searched

| Region | Suburbs |
|---|---|
| Gold Coast (Northern Corridor) | Pimpama · Coomera · Upper Coomera · Ormeau · Helensvale · Hope Island |
| Ipswich Growth Corridor | Ripley · Deebing Heights · Redbank Plains |
| Logan | Yarrabilba · Loganlea |

To change the suburbs, edit the `DOMAIN_URL` constant at the top of `scraper_full.py`.

---

## Dashboard tabs

**Overview** — Summary cards (best IRR, top equity, overlay flags), ranked shortlist table sorted by 10-year IRR, and four comparison charts.

**10-Year Projections** — Line/bar charts for all properties: value vs loan balance, equity growth, cumulative after-tax cash flow, total wealth created.

**Property Deep-Dive** — Select any property for its year-by-year table, individual charts (value, cash flow $/week, equity, depreciation breakdown), and full acquisition/exit cost breakdown.

**Risk & Overlays** — Flood and bushfire planning overlay flags from property.com.au, with risk scores and summary charts.

**Scenario Planner** — Adjust any assumption (interest rate, deposit %, capital growth, rental growth, vacancy, PM fee, inflation, tax rates) or override the rent and purchase price per property. All results recalculate instantly in the browser — no re-scraping needed.

---

## Financial model

| Assumption | Default |
|---|---|
| Loan type | Interest-only, 30-year term |
| Interest rate | 6.20% p.a. |
| Deposit | 20% |
| Capital growth | 7.0% p.a. |
| Rental growth | 4.0% p.a. |
| Vacancy allowance | 4% (~2 weeks/year) |
| Property management | 8.5% of gross rent |
| Maintenance reserve | 0.8% of purchase price p.a. |
| Eamon's marginal tax rate | 47% (income >$190k incl. Medicare) |
| Nadeene's marginal tax rate | 45% |
| CGT treatment | 50% discount, split 50/50, taxed at individual rates |
| Selling costs on exit | 2.5% |
| Ownership structure | 50/50 Tenants in Common |

QLD stamp duty is calculated using the investor (non-FHOG) tiered rates. Division 43 and Division 40 depreciation are modelled from the estimated build year. All assumptions can be changed at runtime via the Scenario Planner tab.

### Rent data priority

1. **Domain rental appraisal** — parsed from the agent's listing description (most accurate)
2. **property.com.au rental history** — recent leased prices from PropTrack data
3. **Fallback estimate** — 4.2% gross yield on purchase price

The source used is stored in the `rent_source` field of each property in `property_data.json`.

---

## Requirements

```
pip install playwright numpy_financial
python -m playwright install chromium --with-deps
```

Python 3.9+

---

## Running

```bash
python3 scraper_full.py
```

This scrapes Domain.com.au headlessly (no browser window opens), enriches all properties in parallel across 5 Chromium tabs, writes `property_data.json`, then builds `property_analysis.html`. Open that file in any browser.

Output paths are set at the top of `scraper_full.py`:

```python
BASE_DIR  = Path('/your/output/directory')
DATA_PATH = BASE_DIR / 'property_data.json'
SITE_PATH = BASE_DIR / 'property_analysis.html'
```

To rebuild the dashboard from existing data without re-scraping:

```bash
python3 build_site_v2.py property_data.json property_analysis.html
```

---

## Files

| File | Purpose |
|---|---|
| `scraper_full.py` | Main scraper — Playwright headless Chromium, 5-tab parallel enrichment |
| `build_site_v2.py` | Generates the HTML dashboard from `property_data.json` |
| `property_data.json` | Generated output — enriched properties + financial model results |
| `property_analysis.html` | Generated output — the interactive dashboard |

`property_data.json` and `property_analysis.html` are excluded from version control (see `.gitignore`) as they're rebuilt on every run.

---

## Nightly automation

The scraper runs nightly at 11pm via Claude Desktop's scheduled task system. The dashboard is refreshed with live listings and ready to review each morning.

---

## Disclaimer

For personal research only. All projections are estimates based on modelled assumptions and historical averages. Not financial advice — consult a licensed financial adviser before making any investment decision.
