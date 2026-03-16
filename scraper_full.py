#!/usr/bin/env python3
"""
Northern Gold Coast Investment Property Scraper
Runs headlessly (no visible browser) via Playwright.
Scrapes Domain.com.au → property.com.au → Financial model → HTML output
"""

import asyncio
import json
import re
import sys
import os
from datetime import datetime
from pathlib import Path

import numpy_financial as npf

# ── Output paths ──────────────────────────────────────────────────────────────
BASE_DIR    = Path('/sessions/stoic-elegant-wright/mnt/Investment Properties')
DATA_PATH   = BASE_DIR / 'property_data.json'
SITE_PATH   = BASE_DIR / 'property_analysis.html'
LOG_PATH    = BASE_DIR / 'scraper_log.txt'

# ── Domain search URL ─────────────────────────────────────────────────────────
DOMAIN_URL = (
    "https://www.domain.com.au/sale/"
    "?suburb=coomera-qld-4209,upper-coomera-qld-4209,ormeau-qld-4208,"
    "pimpama-qld-4209,helensvale-qld-4212,hope-island-qld-4212,"
    "ripley-qld-4306,yarrabilba-qld-4207,deebing-heights-qld-4306,"
    "redbank-plains-qld-4301,loganlea-qld-4131"
    "&bedrooms=4-any&price=850000-1000000"
    "&property-type=house,townhouse"
    "&excludeunderoffer=1&sort=price-asc"
)

# ── Scraper-level property filters ───────────────────────────────────────────
# Properties not meeting these criteria are skipped before running the financial
# model, saving time and keeping the output focused on quality stock.
MIN_LAND_SIZE_M2  = 300   # skip properties with known land size below this
MIN_BEDROOMS      = 4     # skip properties with known bedroom count below this
CACHE_TTL_DAYS    = 7     # re-scrape a property if cached data is older than this many days

# ── Financial model constants ─────────────────────────────────────────────────
DEPOSIT_PCT       = 0.20
INTEREST_RATE     = 0.062
CAP_GROWTH_RATE   = 0.07
RENTAL_GROWTH     = 0.04
VACANCY_RATE      = 0.04
PM_RATE           = 0.085
COUNCIL_RATES     = 2500
WATER             = 1200
INSURANCE         = 1900
MAINTENANCE_PCT   = 0.008
LEGAL_COSTS       = 2400
MARGINAL_RATE_E   = 0.47
MARGINAL_RATE_N   = 0.45
AVG_MARGINAL      = (MARGINAL_RATE_E + MARGINAL_RATE_N) / 2
CGT_DISCOUNT      = 0.50
SELLING_COSTS_PCT = 0.025
INFLATION_RATE    = 0.025   # for real (inflation-adjusted) return calculations

def log(msg):
    ts = datetime.now().strftime('%H:%M:%S')
    line = f"[{ts}] {msg}"
    print(line, flush=True)
    try:
        with open(LOG_PATH, 'a') as f:
            f.write(line + '\n')
    except:
        pass

def qld_stamp_duty(price):
    if price <= 5000:       return 0
    elif price <= 75000:    return 1.50 * (price - 5000) / 100
    elif price <= 540000:   return 1050 + 3.50 * (price - 75000) / 100
    elif price <= 1000000:  return 17325 + 4.50 * (price - 540000) / 100
    else:                   return 38025 + 5.75 * (price - 1000000) / 100

def depreciation(build_year, purchase_price, year_of_ownership):
    age = 2026 - int(build_year)
    div43 = round(purchase_price * 0.55 * 0.025) if (40 - age - (year_of_ownership - 1)) > 0 else 0
    if age <= 3:   base40 = 12000
    elif age <= 7: base40 = 8000
    elif age <= 12:base40 = 4500
    else:           base40 = 2000
    div40 = round(base40 * (0.80 ** (year_of_ownership - 1)))
    return div43, div40

def financial_model(prop):
    price      = prop['purchase_price']
    weekly_rent= prop['weekly_rent']
    build_year = prop.get('build_year_est', 2015)

    stamp      = qld_stamp_duty(price)
    upfront    = price * DEPOSIT_PCT + stamp + LEGAL_COSTS
    loan       = price * (1 - DEPOSIT_PCT)
    annual_int = loan * INTEREST_RATE

    yearly = []
    cash_flows = [-upfront]
    cum_cf = 0
    rent_wk = weekly_rent

    for yr in range(1, 11):
        ar     = rent_wk * 52
        eff    = ar * (1 - VACANCY_RATE)
        pm     = ar * PM_RATE
        vacloss= ar * VACANCY_RATE
        maint  = price * MAINTENANCE_PCT
        other  = pm + vacloss + COUNCIL_RATES + WATER + INSURANCE + maint
        div43, div40 = depreciation(build_year, price, yr)
        depr   = div43 + div40
        taxable= eff - other - annual_int - depr
        tax_im = -taxable * AVG_MARGINAL
        pretax = eff - other - annual_int
        aftertax = pretax + tax_im
        cum_cf += aftertax
        pv     = round(price * ((1 + CAP_GROWTH_RATE) ** yr))
        equity = pv - loan
        sc_sell= pv * SELLING_COSTS_PCT
        gg     = pv - price
        cgt_s  = round((gg * CGT_DISCOUNT * 0.50 * MARGINAL_RATE_E) +
                       (gg * CGT_DISCOUNT * 0.50 * MARGINAL_RATE_N)) if gg > 0 else 0
        net_if_sold = round(pv - loan - sc_sell - cgt_s)
        yearly.append({
            'year': yr, 'prop_value': pv, 'loan_balance': round(loan), 'equity': round(equity),
            'gross_rent': round(ar), 'vacancy_loss': round(vacloss), 'effective_rent': round(eff),
            'interest': round(annual_int), 'pm_fee': round(pm),
            'council_water_insurance': round(COUNCIL_RATES + WATER + INSURANCE),
            'maintenance': round(maint), 'total_cash_expenses': round(other + annual_int),
            'div43': div43, 'div40': div40, 'total_depreciation': depr,
            'taxable_income': round(taxable), 'tax_impact': round(tax_im),
            'pretax_cashflow': round(pretax), 'aftertax_cashflow': round(aftertax),
            'aftertax_cashflow_pw': round(aftertax / 52),
            'cumulative_aftertax_cashflow': round(cum_cf),
            'cgt_if_sold_now': cgt_s, 'selling_costs_if_sold': round(sc_sell),
            'net_proceeds_if_sold': net_if_sold,
            'total_wealth_created': round(equity + cum_cf),
        })
        cash_flows.append(aftertax)
        rent_wk *= (1 + RENTAL_GROWTH)

    ev10  = yearly[9]['prop_value']
    sc10  = round(ev10 * SELLING_COSTS_PCT)
    gg10  = ev10 - price
    cgt10 = round((gg10*CGT_DISCOUNT*0.50*MARGINAL_RATE_E) + (gg10*CGT_DISCOUNT*0.50*MARGINAL_RATE_N))
    net10 = round(ev10 - loan - sc10 - cgt10)
    cash_flows[10] += net10
    try:    irr = round(npf.irr(cash_flows) * 100, 2)
    except: irr = None
    npv7  = round(npf.npv(0.07, cash_flows))

    yr1 = yearly[0]
    return {
        'deposit': round(price * DEPOSIT_PCT), 'stamp_duty': round(stamp),
        'legal_costs': LEGAL_COSTS, 'total_upfront': round(upfront),
        'loan_amount': round(loan), 'annual_interest': round(annual_int),
        'gross_yield': round((weekly_rent * 52) / price * 100, 2),
        'net_yield': round((weekly_rent * 52 * (1 - VACANCY_RATE)) / price * 100, 2),
        'yr1_gross_rent': yr1['gross_rent'], 'yr1_interest': yr1['interest'],
        'yr1_other_expenses': yr1['pm_fee']+yr1['council_water_insurance']+yr1['maintenance'],
        'yr1_depreciation': yr1['total_depreciation'],
        'yr1_div43': yr1['div43'], 'yr1_div40': yr1['div40'],
        'yr1_taxable_income': yr1['taxable_income'], 'yr1_tax_impact': yr1['tax_impact'],
        'yr1_pretax_cashflow': yr1['pretax_cashflow'],
        'yr1_aftertax_cashflow': yr1['aftertax_cashflow'],
        'yr1_aftertax_cashflow_pw': yr1['aftertax_cashflow_pw'],
        'coc_pretax': round(yr1['pretax_cashflow'] / upfront * 100, 2),
        'coc_aftertax': round(yr1['aftertax_cashflow'] / upfront * 100, 2),
        'exit_value': ev10, 'gross_capital_gain': gg10,
        'selling_costs_exit': sc10, 'cgt_payable': cgt10, 'net_proceeds': net10,
        'irr': irr, 'npv_7pct': npv7,
        'total_equity_yr10': yearly[9]['equity'],
        'total_wealth_yr10': yearly[9]['total_wealth_created'],
        'proptrack_gap': prop.get('proptrack_estimate', price) - price,
        'yearly': yearly,
    }

# ── Playwright scraping ───────────────────────────────────────────────────────
async def scrape_domain(page):
    """Scrape Domain.com.au search results page."""
    log(f"Loading Domain search...")
    await page.goto(DOMAIN_URL, wait_until='domcontentloaded', timeout=90000)
    await page.wait_for_timeout(5000)  # Let JS hydrate after DOM load

    # Handle cookie/consent banners
    for sel in ['button:has-text("Accept")', 'button:has-text("I accept")',
                'button:has-text("Got it")', '[data-testid="consent-accept"]']:
        try:
            btn = page.locator(sel).first
            if await btn.is_visible(timeout=2000):
                await btn.click()
                await page.wait_for_timeout(1000)
                break
        except:
            pass

    await page.wait_for_timeout(3000)

    # Extract listings from __NEXT_DATA__ (most reliable)
    listings = await page.evaluate("""() => {
        const results = [];
        try {
            const nd = document.getElementById('__NEXT_DATA__');
            if (!nd) return { error: 'no __NEXT_DATA__', results };
            const data = JSON.parse(nd.textContent);
            const str = JSON.stringify(data);
            // Find listingsMap
            const mapMatch = str.match(/"listingsMap":\\{[^}]+/);
            // Try props.pageProps
            const pp = data.props?.pageProps;
            if (!pp) return { error: 'no pageProps', results };

            // Try several known structures
            const listingsList = pp.listingsMap || pp.listings || pp.searchResults?.listings;
            if (!listingsList) {
                // fallback: stringify search for listing objects
                return { error: 'no listings found in pageProps', keys: Object.keys(pp), results };
            }
            const arr = Array.isArray(listingsList) ? listingsList : Object.values(listingsList);
            arr.slice(0, 30).forEach(item => {
                const l = item.listing || item;
                const addr = l.address || l.addressParts;
                const price = l.priceDetails?.displayPrice || l.price || '';
                const url = 'https://www.domain.com.au' + (l.listingSlug || l.url || '');
                results.push({
                    address: typeof addr === 'object' ?
                        ((addr.streetNumber||'') +' '+(addr.street||'')).trim() : String(addr),
                    suburb: typeof addr === 'object' ? (addr.suburb || '') : '',
                    postcode: typeof addr === 'object' ? (addr.postcode || '') : '',
                    state: typeof addr === 'object' ? (addr.state || 'QLD') : 'QLD',
                    price_display: String(price),
                    bedrooms: l.features?.beds || l.bedrooms || null,
                    bathrooms: l.features?.baths || l.bathrooms || null,
                    car_spaces: l.features?.carSpaces || l.carSpaces || null,
                    land_size: l.features?.landArea || l.landSize || null,
                    building_size: l.features?.buildingArea || null,
                    url: url,
                    listing_id: String(l.id || l.listingId || ''),
                    property_type: l.propertyTypes?.[0] || l.propertyType || 'house',
                    description: (l.summaryDescription || l.headline || '').slice(0, 500),
                    agent: l.advertiser?.name || '',
                    days_listed: l.daysListed || null,
                });
            });
        } catch(e) {
            return { error: String(e), results };
        }
        return { results };
    }""")

    if isinstance(listings, dict) and 'error' in listings:
        log(f"  __NEXT_DATA__ parse issue: {listings.get('error')} — falling back to DOM")
        # DOM fallback — collect only listing URLs + display prices from the search page.
        # Address/suburb/beds are fetched later from each listing's own componentProps.
        listings = await page.evaluate("""() => {
            const results = [];
            // Domain individual listing slugs always contain: -qld-POSTCODE-LISTINGID
            // Use this pattern to find unique listing hrefs and avoid nav/agent links.
            const seen = new Set();
            document.querySelectorAll('a[href]').forEach(a => {
                const href = a.getAttribute('href') || '';
                if (!/\\-qld\\-\\d{4}\\-\\d{5,}$/.test(href)) return;
                if (seen.has(href)) return;
                seen.add(href);

                // Walk up the DOM tree to find the nearest card ancestor that
                // contains a price — limit to 10 levels to avoid over-reaching.
                let card = a.parentElement;
                for (let i = 0; i < 10 && card; i++) {
                    if (/\\$[\\d,]|Auction|Offers|Price Guide/i.test(card.innerText || '')) break;
                    card = card.parentElement;
                }
                const cardText = (card || a).innerText || '';
                // Extract price line from card text
                const priceMatch = cardText.match(/\\$[\\s\\d,]+(?:k)?|Auction|Contact Agent|Price Guide[^\\n]*/i);
                const fullUrl = href.startsWith('http') ? href : 'https://www.domain.com.au' + href;
                results.push({
                    address: '',          // filled in from listing page componentProps
                    suburb: '',
                    postcode: '',
                    price_display: priceMatch ? priceMatch[0].trim() : '',
                    url: fullUrl,
                    description: '',
                });
            });
            return { results };
        }""")

    raw = listings.get('results', []) if isinstance(listings, dict) else []
    log(f"  Found {len(raw)} raw listings from Domain")
    return raw

def parse_price(price_str):
    """Extract a numeric price from display string."""
    s = str(price_str)
    # Direct price: $950,000
    m = re.search(r'\$\s*([\d,]+)', s.replace(' ',''))
    if m:
        return int(m.group(1).replace(',',''))
    # "Offers Over $850,000"
    m = re.search(r'over\s*\$\s*([\d,]+)', s, re.I)
    if m:
        return int(m.group(1).replace(',','')) + 15000
    # Range: take midpoint
    m = re.findall(r'\$\s*([\d,]+)', s)
    if len(m) >= 2:
        a, b = int(m[0].replace(',','')), int(m[1].replace(',',''))
        return (a + b) // 2
    return None

def is_tenanted(description, timeline_text):
    """Check if property is currently tenanted from description or timeline."""
    combined = (description + ' ' + timeline_text).lower()
    tenanted_signals  = ['currently rented', 'currently tenanted', 'tenant in place',
                         'lease in place', 'existing lease', 'tenanted', 'investor ready',
                         'currently leased', 'rental income', 'current lease']
    vacant_signals    = ['vacant possession', 'vacant at settlement', 'owner occupied',
                         'owner-occupied', 'no tenant', 'move in ready', 'vacant']
    score = 0
    for s in tenanted_signals:
        if s in combined: score += 1
    for s in vacant_signals:
        if s in combined: score -= 1
    if score > 0: return True
    if score < 0: return False
    return None  # Unknown

async def scrape_domain_listing(page, url):
    """Visit an individual Domain.com.au listing page and extract:
    - Full description (for rental appraisal, build year, tenancy, council rates)
    - Land size (from listingSummary stats)
    - Features
    - Beds/baths/parking
    Returns a dict of parsed fields.
    """
    result = {
        'weekly_rent_appraisal': None,
        'build_year_domain': None,
        'land_size_m2': None,
        'building_size_m2': None,
        'council_rates_qtr': None,
        'currently_tenanted': None,
        'lease_end_date': None,
        'full_description': '',
        'features_domain': [],
        'address_full': None,
        'suburb': None,
        'postcode': None,
        'bedrooms': None,
        'bathrooms': None,
        'parking': None,
    }
    if not url or 'domain.com.au' not in url:
        return result
    try:
        await page.goto(url, wait_until='domcontentloaded', timeout=60000)
        await page.wait_for_timeout(3000)

        data = await page.evaluate("""() => {
            const nd = document.getElementById('__NEXT_DATA__');
            if (!nd) return null;
            const d = JSON.parse(nd.textContent);
            const cp = d.props?.pageProps?.componentProps;
            if (!cp) return null;
            const summary = cp.listingSummary || {};
            const stats = summary.stats || [];
            const landArea = (stats.find(s => s.key === 'landArea') || {}).value;
            const builtArea = (stats.find(s => s.key === 'buildingArea') || {}).value;
            const descArr = Array.isArray(cp.description) ? cp.description : [cp.description || ''];

            // Extract address cleanly
            const addrObj = cp.address || {};
            let addrStr = '';
            if (typeof addrObj === 'string') {
                addrStr = addrObj;
            } else {
                const num = addrObj.streetNumber || '';
                const street = addrObj.street || '';
                addrStr = (num + ' ' + street).trim() || addrObj.displayAddress || addrObj.fullAddress || '';
            }
            const addrSuburb = typeof addrObj === 'object' ? (addrObj.suburb || '') : '';
            const addrPostcode = typeof addrObj === 'object' ? String(addrObj.postcode || '') : '';
            const addrState = typeof addrObj === 'object' ? (addrObj.state || 'QLD') : 'QLD';

            return {
                description: descArr,
                features: cp.features || [],
                beds: cp.beds || summary.beds,
                baths: summary.baths,
                parking: summary.parking,
                landArea: landArea,
                builtArea: builtArea,
                address: addrStr,
                suburb: addrSuburb,
                postcode: addrPostcode,
                state: addrState,
                propertyType: summary.propertyType,
            };
        }""")

        if not data:
            return result

        desc_lines = data.get('description', [])
        full_desc = ' '.join(str(l) for l in desc_lines if l)
        result['full_description'] = full_desc
        result['features_domain'] = data.get('features', [])
        if data.get('landArea'):
            result['land_size_m2'] = data['landArea']
        if data.get('builtArea'):
            result['building_size_m2'] = data['builtArea']
        if data.get('address'):
            result['address_full'] = data['address']
        if data.get('suburb'):
            result['suburb'] = data['suburb']
        if data.get('postcode'):
            result['postcode'] = str(data['postcode'])
        if data.get('beds') is not None:
            result['bedrooms'] = data['beds']
        if data.get('baths') is not None:
            result['bathrooms'] = data['baths']
        if data.get('parking') is not None:
            result['parking'] = data['parking']

        # Parse description lines for key data
        for line in desc_lines:
            l = str(line).strip()

            # Rental Appraisal: "$630 - $650/Per Week" or "$700/Week"
            m = re.search(r'Rental\s+Appraisal[^$]*\$\s*([\d,]+)\s*[-–to]+\s*\$?\s*([\d,]+)?', l, re.I)
            if m:
                lo = int(m.group(1).replace(',', ''))
                hi = int(m.group(2).replace(',', '')) if m.group(2) else lo
                result['weekly_rent_appraisal'] = (lo + hi) // 2
            # Single value rental appraisal
            if result['weekly_rent_appraisal'] is None:
                m = re.search(r'Rental\s+Appraisal[^$]*\$\s*([\d,]+)\s*/?\s*[Pp]er\s+[Ww]eek', l, re.I)
                if m:
                    result['weekly_rent_appraisal'] = int(m.group(1).replace(',', ''))

            # Build year
            m = re.search(r'[Bb]uilt\s+(?:[Ii]n\s+)?(\d{4})', l)
            if m:
                result['build_year_domain'] = int(m.group(1))

            # Council rates
            m = re.search(r'[Cc]ouncil\s+[Rr]ates?[^$]*\$\s*([\d,.]+)', l)
            if m:
                try:
                    result['council_rates_qtr'] = float(m.group(1).replace(',', ''))
                except:
                    pass

            # Tenancy signals
            l_lower = l.lower()
            if any(k in l_lower for k in ['rental lease in place', 'currently tenanted', 'tenant in place',
                                           'lease in place', 'existing lease', 'currently leased',
                                           'currently rented', 'investment ready', 'tenanted']):
                result['currently_tenanted'] = True
                # Try to extract lease end date
                m2 = re.search(r'until\s+(\w+\s+\d{4})', l, re.I)
                if m2:
                    result['lease_end_date'] = m2.group(1)
            if any(k in l_lower for k in ['vacant possession', 'vacant at settlement', 'owner occupied',
                                           'owner-occupied', 'no tenant']):
                if result['currently_tenanted'] is None:
                    result['currently_tenanted'] = False

        log(f"  Domain listing: rent_appraisal=${result['weekly_rent_appraisal']}/wk  "
            f"built={result['build_year_domain']}  land={result['land_size_m2']}m²  "
            f"tenanted={result['currently_tenanted']}  lease_end={result['lease_end_date']}")

    except Exception as e:
        log(f"  Domain listing scrape error: {e}")

    return result


async def scrape_property_com(page, address, suburb, postcode):
    """Get risk data, PropTrack estimate, rental estimate and tenancy from property.com.au."""
    result = {
        'flood_overlay': None, 'bushfire_overlay': None, 'heritage_overlay': None,
        'proptrack_estimate': None, 'proptrack_range_low': None, 'proptrack_range_high': None,
        'rental_estimate_pw': None,   # property.com.au's own rental estimate
        'land_size_m2': None, 'building_size_m2': None, 'ground_elevation_m': None,
        'last_leased_date': None, 'rental_history': [],
        'school_catchments': [], 'nbn_type': None,
        'currently_tenanted': None, 'property_com_url': None,
        'description_snippet': None,
    }
    try:
        # ── Navigate: try direct URL construction first, then search ──────────
        suburb_slug = suburb.lower().replace(' ', '-')
        street_parts = address.lower().split()
        num = street_parts[0] if street_parts else ''
        street_name = '-'.join(street_parts[1:]) if len(street_parts) > 1 else ''
        for old, new in [('crescent','cres'),('street','st'),('avenue','ave'),('court','ct'),
                         ('drive','dr'),('road','rd'),('place','pl'),('close','cl'),
                         ('circuit','cct'),('way','wy'),('terrace','tce'),('boulevard','blvd')]:
            street_name = street_name.replace(old, new)
        direct_url = f"https://www.property.com.au/qld/{suburb_slug}-{postcode}/{street_name}/{num}/"

        landed = False
        for attempt_url in [direct_url]:
            try:
                await page.goto(attempt_url, wait_until='domcontentloaded', timeout=25000)
                # Wait for the dynamic summary paragraph to render
                try:
                    await page.wait_for_selector('text=About the property', timeout=7000)
                except:
                    await page.wait_for_timeout(4000)
                # Check if we landed on a real property page (has estimated value or address)
                current_url = page.url
                if '/pid-' in current_url or suburb_slug in current_url:
                    result['property_com_url'] = current_url
                    landed = True
                    break
            except:
                pass

        if not landed:
            # Fall back to search
            search_q = f"{address} {suburb} {postcode}".strip()
            search_url = f"https://www.property.com.au/search/?q={search_q.replace(' ','+')}"
            await page.goto(search_url, wait_until='domcontentloaded', timeout=25000)
            await page.wait_for_timeout(3000)
            first_result = page.locator('a[href*="/pid-"]').first
            if await first_result.is_visible(timeout=5000):
                href = await first_result.get_attribute('href')
                prop_url = 'https://www.property.com.au' + href if href.startswith('/') else href
                result['property_com_url'] = prop_url
                await page.goto(prop_url, wait_until='domcontentloaded', timeout=25000)
                try:
                    await page.wait_for_selector('text=About the property', timeout=7000)
                except:
                    await page.wait_for_timeout(4000)

        # ── Extract full page text ─────────────────────────────────────────────
        text = await page.evaluate("() => document.body.innerText")
        full = text  # keep full text for regex searches across line breaks
        lines = [l.strip() for l in text.split('\n') if l.strip()]
        full_lower = full.lower()

        # ── Overlays — parse the "About the property" summary sentence ────────
        # property.com.au uses natural language in a single paragraph, e.g.:
        #   "no flood or heritage overlays detected. We have detected a bushfire overlay."
        # Flood
        if re.search(r'no flood\b[^.]*overlay|flood overlay[^.]*not detected|no flood overlay', full_lower):
            result['flood_overlay'] = False
        elif re.search(r'detected[^.]*flood overlay|flood overlay[^.]*detected|flood overlay on this', full_lower):
            result['flood_overlay'] = True
        # Bushfire
        if re.search(r'no bushfire[^.]*overlay|bushfire overlay[^.]*not detected|no bushfire overlay', full_lower):
            result['bushfire_overlay'] = False
        elif re.search(r'detected[^.]*bushfire overlay|bushfire overlay[^.]*detected|bushfire overlay on this', full_lower):
            result['bushfire_overlay'] = True
        # Heritage
        if re.search(r'no heritage[^.]*overlay|heritage overlay[^.]*not detected|no heritage overlay', full_lower):
            result['heritage_overlay'] = False
        elif re.search(r'detected[^.]*heritage overlay|heritage overlay[^.]*detected|heritage overlay on this', full_lower):
            result['heritage_overlay'] = True

        # ── PropTrack estimate ────────────────────────────────────────────────
        # Primary: summary sentence "estimated property value of X is $930,000"
        m = re.search(r'property value[^.]*?\$\s*([\d,]+)', full, re.I)
        if m:
            val = int(m.group(1).replace(',', ''))
            if 300000 < val < 6000000:
                result['proptrack_estimate'] = val

        # Secondary: standalone dollar amount after "Property value" heading
        if not result['proptrack_estimate']:
            for i, l in enumerate(lines):
                if l.lower().strip() in ('property value', 'estimated value'):
                    for j in range(i + 1, min(i + 10, len(lines))):
                        # Handle "$930,000" or "$930k" or "930,000"
                        m2 = re.search(r'^\$?([\d,]+)(k?)$', lines[j].strip(), re.I)
                        if m2:
                            raw = float(m2.group(1).replace(',', ''))
                            val = int(raw * 1000 if m2.group(2).lower() == 'k' else raw)
                            if 300000 < val < 6000000:
                                result['proptrack_estimate'] = val
                                break
                    if result['proptrack_estimate']:
                        break

        # PropTrack range — look for two "$Xk" values near each other
        range_m = re.findall(r'\$([\d]+(?:\.\d+)?)k\b', full_lower)
        if len(range_m) >= 2:
            candidates = [int(float(x) * 1000) for x in range_m if 300 < float(x) < 6000]
            if len(candidates) >= 2:
                result['proptrack_range_low']  = candidates[0]
                result['proptrack_range_high'] = candidates[1]
                if not result['proptrack_estimate']:
                    result['proptrack_estimate'] = (candidates[0] + candidates[1]) // 2

        # ── Rental estimate from property.com.au ──────────────────────────────
        # Summary: "potential rental income of $645 per week"
        m = re.search(r'rental income[^.]*?\$\s*([\d,]+)\s*per\s*week', full, re.I)
        if not m:
            # "$645pw" pattern
            m = re.search(r'\$(\d+)pw\b', full)
        if m:
            rent_val = int(m.group(1).replace(',', ''))
            if 200 < rent_val < 5000:
                result['rental_estimate_pw'] = rent_val

        # ── Land / building size ───────────────────────────────────────────────
        m = re.search(r'sits?\s+on\s+a\s+([\d,]+)\s*m²', full, re.I)
        if m: result['land_size_m2'] = int(m.group(1).replace(',', ''))
        if not result['land_size_m2']:
            m = re.search(r'([\d,]+)\s*m²\s*(?:lot|land)', full, re.I)
            if m: result['land_size_m2'] = int(m.group(1).replace(',', ''))
        m = re.search(r'building\s*(?:size|area)?[:\s]*([\d,]+)\s*m', full, re.I)
        if m: result['building_size_m2'] = int(m.group(1).replace(',', ''))

        # ── NBN — look at context window around any NBN/fibre mention ─────────
        for i, l in enumerate(lines):
            l_lower = l.lower()
            if 'nbn' in l_lower or 'fibre' in l_lower or 'broadband' in l_lower:
                ctx = ' '.join(lines[max(0, i-1):min(len(lines), i+3)]).lower()
                if 'fibre to the premises' in ctx or 'fttp' in ctx:
                    result['nbn_type'] = 'FTTP'; break
                elif 'fibre to the curb' in ctx or 'fttc' in ctx:
                    result['nbn_type'] = 'FTTC'; break
                elif 'fibre to the node' in ctx or 'fttn' in ctx:
                    result['nbn_type'] = 'FTTN'; break
                elif 'hybrid fibre' in ctx or 'hfc' in ctx:
                    result['nbn_type'] = 'HFC'; break
                elif 'nbn' in ctx:
                    result['nbn_type'] = 'NBN'

        # ── Schools — from summary paragraph ──────────────────────────────────
        school_m = re.findall(r'catchment of ([^.]+?)(?:\.|and\s+\w+\s+State)', full, re.I)
        if school_m:
            # Split on "and", strip
            parts = re.split(r'\band\b', school_m[0], flags=re.I)
            result['school_catchments'] = [s.strip() for s in parts if s.strip()][:4]
        if not result['school_catchments']:
            for l in lines:
                if re.search(r'\b(state school|secondary college|high school|college|academy)\b', l, re.I):
                    if len(l) < 100 and l not in result['school_catchments']:
                        result['school_catchments'].append(l.strip())
            result['school_catchments'] = result['school_catchments'][:4]

        # ── Tenancy / lease history ────────────────────────────────────────────
        leased_dates = []
        rental_history = []
        for i, l in enumerate(lines):
            if 'leased' in l.lower() and re.search(r'\b(jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)\b', l, re.I):
                leased_dates.append(l.strip())
            m = re.search(r'\$([\d,]+)\s*per\s*week', l, re.I)
            if m:
                rental_history.append(int(m.group(1).replace(',', '')))
        if leased_dates:
            result['last_leased_date'] = leased_dates[0]
        result['rental_history'] = rental_history[:8]
        result['currently_tenanted'] = is_tenanted('', '\n'.join(leased_dates))

        log(f"  property.com.au: flood={result['flood_overlay']} bush={result['bushfire_overlay']} "
            f"heritage={result['heritage_overlay']} est=${result['proptrack_estimate']} "
            f"rent_est=${result['rental_estimate_pw']}/wk nbn={result['nbn_type']} "
            f"schools={result['school_catchments'][:1]}")

    except Exception as e:
        log(f"  property.com.au error: {e}")

    return result

def parse_domain_listing(raw):
    """Clean up a raw Domain listing dict."""
    addr = str(raw.get('address',''))
    suburb = str(raw.get('suburb',''))
    postcode = str(raw.get('postcode',''))
    price_str = str(raw.get('price_display',''))
    url = str(raw.get('url',''))
    desc = str(raw.get('description',''))

    # Extract number + street from combined address if needed
    m = re.match(r'^(\d+[A-Za-z]?(?:/\d+[A-Za-z]?)?)\s+(.+)$', addr.strip())
    if m:
        num, street = m.group(1), m.group(2)
    else:
        num, street = '', addr

    # Check tenanted from listing description
    tenanted = is_tenanted(desc, '')

    # parse price
    price_num = parse_price(price_str)

    # is auction?
    is_auction = bool(re.search(r'auction', price_str, re.I))

    return {
        'id': re.sub(r'[^a-zA-Z0-9_]', '_', addr + '_' + suburb),
        'address': addr,
        'street_number': num,
        'street_name': street,
        'suburb': suburb,
        'postcode': postcode,
        'state': raw.get('state', 'QLD'),
        'listing_price': price_str,
        'price_numeric': price_num,
        'is_auction': is_auction,
        'bedrooms': raw.get('bedrooms'),
        'bathrooms': raw.get('bathrooms'),
        'car_spaces': raw.get('car_spaces'),
        'land_size_listed': raw.get('land_size'),
        'building_size_listed': raw.get('building_size'),
        'domain_url': url,
        'property_type': raw.get('property_type','house'),
        'description': desc,
        'agent': raw.get('agent',''),
        'days_listed': raw.get('days_listed'),
        'tenanted_from_listing': tenanted,
        'listing_id': raw.get('listing_id',''),
    }

async def run():
    from playwright.async_api import async_playwright

    log(f"\n{'='*60}")
    log(f"Northern Gold Coast Property Scraper — {datetime.now().strftime('%d %b %Y %H:%M')}")
    log(f"Search URL: {DOMAIN_URL}")
    log(f"{'='*60}\n")

    async with async_playwright() as pw:
        browser = await pw.chromium.launch(
            headless=True,
            args=['--no-sandbox','--disable-dev-shm-usage','--disable-blink-features=AutomationControlled']
        )
        context = await browser.new_context(
            viewport={'width': 1440, 'height': 900},
            user_agent='Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36',
            locale='en-AU',
            timezone_id='Australia/Brisbane',
        )
        # Stealth: hide webdriver flag
        await context.add_init_script("""
            Object.defineProperty(navigator, 'webdriver', { get: () => undefined });
        """)

        page = await context.new_page()

        # ── Step 1: Scrape Domain ──────────────────────────────────────────
        try:
            raw_listings = await scrape_domain(page)
        except Exception as e:
            log(f"Domain scrape failed: {e}")
            raw_listings = []

        if not raw_listings:
            log("No listings found from Domain. Check if page structure changed.")
            log("Trying to take a screenshot for debugging...")
            try:
                await page.screenshot(path='/sessions/stoic-elegant-wright/debug_domain.png')
                log("Screenshot saved to debug_domain.png")
            except: pass
            await browser.close()
            return False

        # ── Step 2: Filter and parse listings ─────────────────────────────
        parsed = []
        for raw in raw_listings:
            p = parse_domain_listing(raw)
            # Filter: must have a parseable price, be an auction, or have no address yet (DOM fallback)
            # DOM fallback listings have empty address — price will be confirmed from listing page
            no_address = not p.get('address')
            if p['price_numeric'] is None and not p['is_auction'] and not no_address:
                log(f"  Skipping (no price): {p['address']}")
                continue
            # Assume auction/no-price DOM fallback = ~$925k (middle of budget)
            if p['price_numeric'] is None:
                p['purchase_price'] = 925000
            else:
                p['purchase_price'] = p['price_numeric']
            # Skip if clearly out of range (but allow DOM fallback through — price unconfirmed)
            if not no_address and (p['purchase_price'] < 800000 or p['purchase_price'] > 1050000):
                continue
            parsed.append(p)

        # Drop entries where address is non-empty but obviously invalid
        # (empty address is allowed — DOM fallback will populate it from listing page)
        parsed = [p for p in parsed if not p.get('address') or re.match(r'^\d+[\w/]*\s+[A-Za-z]', p.get('address',''))]

        # Deduplicate by address (DOM fallback often returns each property twice)
        # Use URL as fallback dedup key when address is empty (DOM fallback path)
        seen_addr = set()
        deduped = []
        for p in parsed:
            addr_key = re.sub(r'[^a-z0-9]', '', (p['address'] + p.get('suburb','')).lower())
            if not addr_key:
                # DOM fallback: use URL slug as key
                addr_key = re.sub(r'[^a-z0-9]', '', p.get('domain_url', p.get('id', str(len(deduped)))))
            if addr_key not in seen_addr:
                seen_addr.add(addr_key)
                deduped.append(p)
        parsed = deduped

        log(f"\n{len(parsed)} listings in range after filtering and dedup\n")

        # ── Load existing cache ────────────────────────────────────────────
        cache = {}
        if DATA_PATH.exists():
            try:
                with open(DATA_PATH) as f:
                    old_data = json.load(f)
                for prop in old_data.get('properties', []):
                    # Prefer domain_url as cache key (most stable identifier)
                    ck = re.sub(r'[^a-z0-9]', '', (prop.get('domain_url') or '').lower().rstrip('/'))
                    if not ck:
                        ck = re.sub(r'[^a-z0-9]', '', (prop.get('address','') + prop.get('suburb','')).lower())
                    if ck:
                        cache[ck] = prop
                log(f"Loaded {len(cache)} cached properties (TTL={CACHE_TTL_DAYS}d)\n")
            except Exception as e:
                log(f"Cache load failed (will scrape fresh): {e}")
                cache = {}

        # ── Step 3: Enrich all listings in parallel (5 tabs at once) ─────
        CONCURRENCY = 5
        semaphore = asyncio.Semaphore(CONCURRENCY)
        enriched_results = [None] * len(parsed)

        async def enrich_one(i, p):
            async with semaphore:
                log(f"[{i+1}/{len(parsed)}] → {p['address']}, {p['suburb']}")

                # ── Cache check ────────────────────────────────────────────
                ck = re.sub(r'[^a-z0-9]', '', (p.get('domain_url') or '').lower().rstrip('/'))
                if not ck:
                    ck = re.sub(r'[^a-z0-9]', '', (p.get('address','') + p.get('suburb','')).lower())
                if ck and ck in cache:
                    cached = cache[ck]
                    scraped_at = cached.get('scraped_at')
                    if scraped_at:
                        try:
                            age_days = (datetime.now() - datetime.fromisoformat(scraped_at)).days
                            if age_days < CACHE_TTL_DAYS:
                                log(f"  ✓ CACHED ({age_days}d old) — skipping scrape")
                                enriched_results[i] = cached
                                return
                        except Exception:
                            pass  # malformed date — fall through to fresh scrape

                tab = await context.new_page()
                try:
                    # 3a. Domain individual listing page
                    domain_detail = await scrape_domain_listing(tab, p.get('domain_url', ''))

                    # If address is empty (DOM fallback path), populate from listing page
                    if not p.get('address') and domain_detail.get('address_full'):
                        p['address'] = domain_detail['address_full']
                        m_addr = re.match(r'^(\d+[A-Za-z]?(?:/\d+[A-Za-z]?)?)\s+(.+)$', p['address'].strip())
                        if m_addr:
                            p['street_number'] = m_addr.group(1)
                            p['street_name'] = m_addr.group(2)
                        p['id'] = re.sub(r'[^a-zA-Z0-9_]', '_', p['address'] + '_' + p.get('suburb',''))
                    if not p.get('suburb') and domain_detail.get('suburb'):
                        p['suburb'] = domain_detail['suburb']
                    if not p.get('postcode') and domain_detail.get('postcode'):
                        p['postcode'] = domain_detail['postcode']

                    # Validate we have a real street address; skip if not
                    if not re.match(r'^\d+[\w/]*\s+[A-Za-z]', p.get('address', '')):
                        log(f"  ✗ {p.get('domain_url','?')} — no valid address, skipping")
                        enriched_results[i] = None
                        return

                    # For DOM fallback listings, price range wasn't checked before — do it now
                    if p['purchase_price'] < 800000 or p['purchase_price'] > 1050000:
                        log(f"  ✗ {p['address']} — price ${p['purchase_price']:,} out of range, skipping")
                        enriched_results[i] = None
                        return

                    # Beds/baths from listing page if not already known
                    if p.get('bedrooms') is None and domain_detail.get('bedrooms') is not None:
                        p['bedrooms'] = domain_detail['bedrooms']
                    if p.get('bathrooms') is None and domain_detail.get('bathrooms') is not None:
                        p['bathrooms'] = domain_detail['bathrooms']
                    if p.get('parking') is None and domain_detail.get('parking') is not None:
                        p['parking'] = domain_detail['parking']

                    # ── Scraper-level quality filters ──────────────────────
                    # Apply AFTER we have real data from the listing page
                    land = domain_detail.get('land_size_m2') or p.get('land_size_m2') or p.get('land_size_listed') or 0
                    beds = p.get('bedrooms') or 0
                    if MIN_LAND_SIZE_M2 > 0 and land and land < MIN_LAND_SIZE_M2:
                        log(f"  ✗ {p['address']} — land {land}m² < {MIN_LAND_SIZE_M2}m² minimum, skipping")
                        enriched_results[i] = None
                        return
                    if MIN_BEDROOMS > 0 and beds and beds < MIN_BEDROOMS:
                        log(f"  ✗ {p['address']} — {beds} beds < {MIN_BEDROOMS} minimum, skipping")
                        enriched_results[i] = None
                        return

                    if domain_detail.get('land_size_m2'):
                        p['land_size_m2'] = domain_detail['land_size_m2']
                    if domain_detail.get('building_size_m2'):
                        p['building_size_m2'] = domain_detail['building_size_m2']
                    if domain_detail.get('features_domain'):
                        p['features_domain'] = domain_detail['features_domain']
                    if domain_detail.get('full_description'):
                        p['description'] = domain_detail['full_description']
                    if domain_detail.get('lease_end_date'):
                        p['lease_end_date'] = domain_detail['lease_end_date']

                    # 3b. Build year
                    if domain_detail.get('build_year_domain'):
                        p['build_year_est'] = domain_detail['build_year_domain']
                    else:
                        p['build_year_est'] = 2015
                        m = re.search(r'built\s+(?:in\s+)?(\d{4})', p.get('description',''), re.I)
                        if m: p['build_year_est'] = int(m.group(1))

                    # 3c. Weekly rent (Domain appraisal → propcom history → estimate)
                    if domain_detail.get('weekly_rent_appraisal'):
                        p['weekly_rent'] = domain_detail['weekly_rent_appraisal']
                        p['rent_source'] = 'domain_appraisal'
                    else:
                        p['weekly_rent'] = round(p['purchase_price'] * 0.00081)
                        p['rent_source'] = 'estimate'

                    # 3d. Tenancy from Domain description
                    if domain_detail.get('currently_tenanted') is not None:
                        p['currently_tenanted'] = domain_detail['currently_tenanted']
                    elif p.get('tenanted_from_listing') is not None:
                        p['currently_tenanted'] = p['tenanted_from_listing']

                    # 3e. property.com.au for flood/bushfire overlays (same tab)
                    risk_data = await scrape_property_com(
                        tab, p['address'], p['suburb'], p['postcode']
                    )
                    p.update({k: v for k, v in risk_data.items()
                              if k not in ('currently_tenanted', 'land_size_m2') or p.get(k) is None})

                    if p.get('proptrack_estimate'):
                        p['proptrack_gap'] = p['proptrack_estimate'] - p['purchase_price']
                    else:
                        p['proptrack_estimate'] = p['purchase_price']
                        p['proptrack_gap'] = 0

                    if p.get('rent_source') == 'estimate' and risk_data.get('rental_estimate_pw'):
                        p['weekly_rent'] = risk_data['rental_estimate_pw']
                        p['rent_source'] = 'propcom_estimate'
                    elif p.get('rent_source') == 'estimate' and p.get('rental_history'):
                        p['weekly_rent'] = sorted(p['rental_history'], reverse=True)[0]
                        p['rent_source'] = 'propcom_history'

                    # Financial model
                    model = financial_model(p)
                    p.update(model)

                    # Risk score
                    risk = (2 if p.get('flood_overlay') else 0) + (1 if p.get('bushfire_overlay') else 0)
                    p['risk_score'] = risk
                    p['risk_label'] = {0:'Low',1:'Moderate',2:'High',3:'Very High'}.get(risk,'Unknown')

                    # Timestamp for cache TTL
                    p['scraped_at'] = datetime.now().isoformat()

                    enriched_results[i] = p
                    log(f"  ✓ {p['address']} — ${p.get('weekly_rent')}/wk  IRR={p.get('irr')}%  AT=${p.get('yr1_aftertax_cashflow_pw')}/wk  tenanted={p.get('currently_tenanted')}")
                except Exception as e:
                    log(f"  ✗ {p['address']} error: {e}")
                    enriched_results[i] = None
                finally:
                    await tab.close()

        log(f"Starting parallel enrichment ({CONCURRENCY} tabs)…\n")
        await asyncio.gather(*[enrich_one(i, p) for i, p in enumerate(parsed)])
        enriched = [r for r in enriched_results if r is not None]
        log(f"\n✓ Enriched {len(enriched)} properties (fresh + cache hits from today's search)")

        # ── Merge: keep recently cached properties not in today's search ──
        # (e.g. temporarily delisted, price moved just outside range)
        today_keys = set()
        for p in enriched:
            ck = re.sub(r'[^a-z0-9]', '', (p.get('domain_url') or '').lower().rstrip('/'))
            if not ck:
                ck = re.sub(r'[^a-z0-9]', '', (p.get('address','') + p.get('suburb','')).lower())
            if ck:
                today_keys.add(ck)
        kept_from_cache = 0
        for ck, cached_prop in cache.items():
            if ck not in today_keys:
                scraped_at = cached_prop.get('scraped_at')
                if scraped_at:
                    try:
                        age_days = (datetime.now() - datetime.fromisoformat(scraped_at)).days
                        if age_days < CACHE_TTL_DAYS:
                            enriched.append(cached_prop)
                            kept_from_cache += 1
                            log(f"  + Retained from cache ({age_days}d old, not in today's search): {cached_prop.get('address','?')}")
                    except Exception:
                        pass
        if kept_from_cache:
            log(f"  → {kept_from_cache} properties retained from cache\n")

        await browser.close()

        if not enriched:
            log("No enriched properties after processing.")
            return False

        # ── Step 4: Save JSON ──────────────────────────────────────────────
        output = {
            'meta': {
                'generated': datetime.now().isoformat(),
                'generated_display': datetime.now().strftime('%d %b %Y %H:%M AEST'),
                'search_url': DOMAIN_URL,
                'suburbs_searched': ['Pimpama','Coomera','Upper Coomera','Ormeau','Helensvale','Hope Island',
                                     'Ripley','Deebing Heights','Redbank Plains','Yarrabilba','Loganlea'],
                'total_found': len(enriched),
                'cache_ttl_days': CACHE_TTL_DAYS,
            },
            'assumptions': {
                'deposit_pct': DEPOSIT_PCT, 'interest_rate': INTEREST_RATE,
                'cap_growth_rate': CAP_GROWTH_RATE, 'rental_growth': RENTAL_GROWTH,
                'inflation_rate': INFLATION_RATE,
                'vacancy_rate': VACANCY_RATE, 'pm_rate': PM_RATE,
                'marginal_rate_eamon': MARGINAL_RATE_E, 'marginal_rate_nadeene': MARGINAL_RATE_N,
                'avg_marginal': AVG_MARGINAL, 'cgt_discount': CGT_DISCOUNT,
                'selling_costs_pct': SELLING_COSTS_PCT,
                'buyers': 'Eamon & Nadeene', 'structure': '50/50 Tenants in Common',
            },
            'properties': enriched,
        }

        with open(DATA_PATH, 'w') as f:
            json.dump(output, f, indent=2, default=str)
        log(f"\n✓ Data saved → {DATA_PATH}")

        # ── Step 5: Build HTML ─────────────────────────────────────────────
        build_html(output, SITE_PATH)
        log(f"✓ Site built → {SITE_PATH}")
        log(f"\nDone! {len(enriched)} properties ready for review.")
        return True


def build_html(data, out_path):
    """Build the full HTML dashboard from data."""
    # Import and run the site builder
    # We pass data as a JSON-embedded string
    import subprocess, tempfile, os
    data_json = json.dumps(data, default=str)

    builder_path = '/sessions/stoic-elegant-wright/build_site_v2.py'
    # Write data to a temp file and have build_site_v2 read it
    temp_data = '/sessions/stoic-elegant-wright/_temp_scrape_data.json'
    with open(temp_data, 'w') as f:
        json.dump(data, f, default=str)

    result = subprocess.run(['python3', builder_path, temp_data, str(out_path)],
                            capture_output=True, text=True)
    if result.returncode != 0:
        log(f"HTML build error: {result.stderr}")
    else:
        log(f"HTML build: {result.stdout.strip()}")


if __name__ == '__main__':
    asyncio.run(run())
