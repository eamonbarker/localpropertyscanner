#!/usr/bin/env python3
"""
Property Dashboard Local Server
================================
Serves the dashboard at http://localhost:8787 and provides two API endpoints:

  POST /api/scrape   {"url": "https://www.domain.com.au/..."}
      Runs a full assessment on a single listing and upserts into the JSON.
      Returns {"ok": true/false, "log": "...", "address": "..."}

  DELETE /api/property/<prop_id>
      Removes a property from the JSON by its id field, then rebuilds HTML.
      Returns {"ok": true, "removed": 1}

Run with:
  python3 serve.py
Then open http://localhost:8787 in your browser.
"""

import json
import re
import subprocess
import sys
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import unquote

BASE_DIR  = Path(__file__).parent
DATA_PATH = BASE_DIR / 'property_data.json'
HTML_PATH = BASE_DIR / 'property_analysis.html'
PORT      = 8787


class Handler(BaseHTTPRequestHandler):

    # ── CORS headers for all responses ───────────────────────────────────
    def _cors(self):
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'GET, POST, DELETE, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type')

    def _json(self, code, obj):
        body = json.dumps(obj, default=str).encode()
        self.send_response(code)
        self.send_header('Content-Type', 'application/json')
        self._cors()
        self.end_headers()
        self.wfile.write(body)

    # ── OPTIONS preflight ─────────────────────────────────────────────────
    def do_OPTIONS(self):
        self.send_response(200)
        self._cors()
        self.end_headers()

    # ── GET ───────────────────────────────────────────────────────────────
    def do_GET(self):
        if self.path in ('/', '/index.html'):
            if HTML_PATH.exists():
                content = HTML_PATH.read_bytes()
                self.send_response(200)
                self.send_header('Content-Type', 'text/html; charset=utf-8')
                self._cors()
                self.end_headers()
                self.wfile.write(content)
            else:
                self._json(404, {'ok': False, 'error': 'Dashboard not built yet — run scraper first'})
        elif self.path == '/api/ping':
            self._json(200, {'ok': True})
        elif self.path == '/api/data':
            if DATA_PATH.exists():
                content = DATA_PATH.read_bytes()
                self.send_response(200)
                self.send_header('Content-Type', 'application/json')
                self._cors()
                self.end_headers()
                self.wfile.write(content)
            else:
                self._json(404, {'ok': False, 'error': 'property_data.json not found'})
        else:
            self._json(404, {'ok': False, 'error': 'Not found'})

    # ── POST /api/scrape ──────────────────────────────────────────────────
    def do_POST(self):
        if self.path != '/api/scrape':
            self._json(404, {'ok': False, 'error': 'Not found'})
            return

        length = int(self.headers.get('Content-Length', 0))
        try:
            body = json.loads(self.rfile.read(length))
        except Exception:
            self._json(400, {'ok': False, 'error': 'Invalid JSON body'})
            return

        url = (body.get('url') or '').strip()
        if not url:
            self._json(400, {'ok': False, 'error': 'url is required'})
            return

        scraper = BASE_DIR / 'scraper_full.py'
        if not scraper.exists():
            self._json(500, {'ok': False, 'error': f'scraper_full.py not found in {BASE_DIR}'})
            return

        print(f"  → Scraping: {url}")
        result = subprocess.run(
            [sys.executable, str(scraper), url],
            capture_output=True, text=True, timeout=300
        )
        output_log = (result.stdout + result.stderr).strip()
        ok = result.returncode == 0

        # Try to extract address from log output
        address = None
        m = re.search(r'Address\s*:\s*(.+)', output_log)
        if m:
            address = m.group(1).strip()

        self._json(200 if ok else 500, {
            'ok': ok,
            'address': address,
            'log': output_log,
        })

    # ── DELETE /api/property/<id> ─────────────────────────────────────────
    def do_DELETE(self):
        m = re.match(r'/api/property/(.+)', self.path)
        if not m:
            self._json(404, {'ok': False, 'error': 'Not found'})
            return

        prop_id = unquote(m.group(1))

        if not DATA_PATH.exists():
            self._json(404, {'ok': False, 'error': 'property_data.json not found'})
            return

        try:
            data = json.loads(DATA_PATH.read_text())
        except Exception as e:
            self._json(500, {'ok': False, 'error': f'Could not read JSON: {e}'})
            return

        before = len(data.get('properties', []))
        data['properties'] = [p for p in data.get('properties', [])
                              if p.get('id') != prop_id]
        after = len(data['properties'])
        removed = before - after

        if removed == 0:
            self._json(404, {'ok': False, 'error': f'No property with id={prop_id!r}'})
            return

        data.setdefault('meta', {})['total_found'] = after
        DATA_PATH.write_text(json.dumps(data, indent=2, default=str))
        print(f"  → Deleted property id={prop_id!r}  ({removed} removed, {after} remain)")

        # Rebuild dashboard HTML
        builder = BASE_DIR / 'build_site_v2.py'
        if builder.exists():
            subprocess.run([sys.executable, str(builder)], capture_output=True, timeout=60)

        self._json(200, {'ok': True, 'removed': removed, 'total': after})

    # Suppress default request logging noise
    def log_message(self, fmt, *args):
        pass


if __name__ == '__main__':
    server = ThreadingHTTPServer(('localhost', PORT), Handler)
    print(f"\n  Property Dashboard  →  http://localhost:{PORT}")
    print(f"  JSON data          →  {DATA_PATH}")
    print(f"\n  Press Ctrl+C to stop\n")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print('\n  Server stopped.')
