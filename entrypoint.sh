#!/bin/bash
# Start cron daemon (nightly property scan)
service cron start

echo "========================================"
echo " Property Scanner starting"
echo " Data dir : ${PROPERTY_DATA_DIR:-/data}"
echo " Port     : ${PORT:-8787}"
echo " Timezone : $(cat /etc/timezone 2>/dev/null || echo 'UTC')"
echo "========================================"

# Run the web server (foreground — keeps container alive)
exec python3 /app/web_app.py
