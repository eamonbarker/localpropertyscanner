# Use Microsoft's official Playwright + Python image (Chromium pre-installed)
FROM mcr.microsoft.com/playwright/python:v1.58.0-jammy

WORKDIR /app

# Install cron + Python deps
RUN DEBIAN_FRONTEND=noninteractive apt-get update && \
    DEBIAN_FRONTEND=noninteractive apt-get install -y --no-install-recommends cron tzdata \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy app files
COPY scraper_full.py .
COPY web_app.py .
COPY build_site_v2.py .
COPY entrypoint.sh .
RUN chmod +x entrypoint.sh

# Nightly cron job — runs scraper at 11:00 PM local time
# Logs go to /data/cron.log (same persistent volume as property_data.json)
RUN echo '0 23 * * * root PROPERTY_DATA_DIR=/data python3 /app/scraper_full.py >> /data/cron.log 2>&1' \
    > /etc/cron.d/property-scan \
    && chmod 0644 /etc/cron.d/property-scan

# Persistent data directory (override with PROPERTY_DATA_DIR env var)
RUN mkdir -p /data
ENV PROPERTY_DATA_DIR=/data
ENV PORT=8787
ENV PERSIST_ASSESSMENTS=true
EXPOSE 8787

CMD ["/app/entrypoint.sh"]
