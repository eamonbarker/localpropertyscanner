# Use Microsoft's official Playwright + Python image (Chromium pre-installed)
FROM mcr.microsoft.com/playwright/python:v1.40.0-jammy

WORKDIR /app

# Install Python deps
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy app files
COPY scraper_full.py .
COPY web_app.py .

# Data dir for temporary scrape results
RUN mkdir -p /tmp/propdata
ENV PROPERTY_DATA_DIR=/tmp/propdata

# Railway injects PORT; default to 8080 locally
ENV PORT=8080
EXPOSE 8080

CMD ["python3", "web_app.py"]
