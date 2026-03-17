# Local Property Scanner

Headless investment property research tool for South-East Queensland. Scrapes live listings from Domain.com.au, enriches them with rental appraisals, flood/bushfire overlay data, tenancy status, and build-year depreciation, then generates an interactive single-file HTML dashboard with 10-year financial projections and a live scenario planner.

---

## What it does

1. **Scrapes Domain.com.au** — searches SEQ suburbs for 4-bedroom houses/townhouses in a configured price range
2. **Visits each listing page** — extracts the rental appraisal, build year, land size, features, and tenancy status directly from the agent's listing description
3. **Checks property.com.au** — pulls flood overlay, bushfire overlay, PropTrack estimate, and rental history
4. **Runs a 10-year financial model** per property — IRR, NPV, after-tax cash flow, depreciation (Div 43 + Div 40), CGT on exit
5. **Builds a single-file HTML dashboard** — five tabs covering overview, projections, deep-dive, risk overlays, and a live scenario planner
6. **Caches results** — properties already scraped within 7 days are reused, keeping nightly re-runs fast
7. **Ad-hoc single-URL assessment** — paste any Domain.com.au listing URL to assess it on demand and add it to the dashboard

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
| Buyer 1 marginal tax rate | Configurable (default 47%) |
| Buyer 2 marginal tax rate | Configurable (default 45%) |
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

## Caching

Results are cached in `property_data.json`. On each run the scraper checks whether a property was scraped within the last 7 days (`CACHE_TTL_DAYS`). If so, the cached result is reused and the browser is never launched for that property, cutting nightly run time significantly.

Properties that were cached recently but no longer appear in the search results (e.g. under offer) are retained in the JSON until their cache entry expires.

---

## Requirements

```
pip install playwright numpy_financial flask
python -m playwright install chromium --with-deps
```

Python 3.9+

---

## Running

### Local — full nightly scrape

```bash
python3 scraper_full.py
```

Scrapes Domain.com.au headlessly, enriches all properties in parallel across 5 Chromium tabs, writes `property_data.json`, then builds `property_analysis.html`. Open that file in any browser.

### Local — assess a single listing

```bash
python3 scraper_full.py https://www.domain.com.au/<listing-id>
```

Scrapes the single URL, runs the full financial model, upserts the result into `property_data.json`, and rebuilds `property_analysis.html`.

### Local — rebuild dashboard from existing data

```bash
python3 build_site_v2.py property_data.json property_analysis.html
```

### Local — serve dashboard with ad-hoc assessment UI

```bash
python3 serve.py
```

Starts a local server on `http://localhost:8787`. The dashboard loads in the browser with a URL input bar at the top — paste any Domain.com.au listing URL and click **Assess** to run a full assessment and add it to the dashboard. The ✕ button in each row removes that property from the dashboard.

### Docker / NAS deployment

Build and run with Docker Compose:

```bash
docker compose up -d --build
```

The container:
- Runs `web_app.py` (Flask) on port 8787 — full Playwright-based assessment with streaming logs
- Runs a cron job nightly at 11 PM (`TZ=Australia/Brisbane`) to refresh the full property list
- Persists `property_data.json` and the built HTML to a `./data` volume

Environment variables (set in `docker-compose.yml`):

| Variable | Default | Description |
|---|---|---|
| `PROPERTY_DATA_DIR` | `/data` | Path inside the container where JSON and HTML are stored |
| `PERSIST_ASSESSMENTS` | `true` | Save ad-hoc assessments to JSON and rebuild HTML |
| `PORT` | `8787` | Port the Flask app listens on |
| `TZ` | `Australia/Brisbane` | Timezone for cron schedule |

To pull the latest code and rebuild on a running NAS:

```bash
cd /volume1/docker/property-scanner
sudo git pull
sudo docker compose up -d --build
```

### Vercel (serverless, no Playwright)

The `api/` directory contains a self-contained serverless version for Vercel. It uses `httpx` + `BeautifulSoup` to parse Domain.com.au's server-side rendered HTML without a browser. Overlay data (PropTrack, flood/bushfire) is not available in this mode.

Deploy via the Vercel CLI or connect the GitHub repo in the Vercel dashboard. No additional configuration is required — Vercel auto-detects the Python function in `api/index.py`.

---

## Files

| File | Purpose |
|---|---|
| `scraper_full.py` | Main scraper — Playwright headless Chromium, 5-tab parallel enrichment, caching, single-URL mode |
| `build_site_v2.py` | Generates the HTML dashboard from `property_data.json` |
| `serve.py` | Lightweight local HTTP server with ad-hoc assess and delete endpoints |
| `web_app.py` | Flask app for Docker/NAS deployment — streaming Playwright assessments, nightly cron integration |
| `Dockerfile` | Docker image based on the official Playwright Python image |
| `docker-compose.yml` | Compose config with persistent data volume, cron, and timezone |
| `entrypoint.sh` | Container entrypoint — starts cron then the Flask server |
| `api/index.py` | Vercel serverless function — requests-based (no Playwright), full financial model |
| `api/requirements.txt` | Python deps for the Vercel function |
| `vercel.json` | Vercel routing config |
| `requirements.txt` | Python deps for local and Docker use |
| `property_data.json` | Generated output — enriched properties + financial model results |
| `property_analysis.html` | Generated output — the interactive dashboard |

`property_data.json` and `property_analysis.html` are excluded from version control (see `.gitignore`) as they're rebuilt on every run.

---

## Disclaimer

For personal research only. All projections are estimates based on modelled assumptions and historical averages. Not financial advice — consult a licensed financial adviser before making any investment decision.
