# One container = the whole agent backend + UI. Built and run on a Vultr Cloud Compute VM.
FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 DATA_DIR=/data PORT=8080 \
    FORWARDED_ALLOW_IPS=127.0.0.1 RETENTION_HOURS=24
WORKDIR /srv

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY app ./app
COPY samples ./samples

# FORWARDED_ALLOW_IPS: only a trusted proxy may set the client address (compose sets it for Caddy).
# Run as an unprivileged user; /data holds the SQLite run history + audit log (mount a volume to keep it).
RUN useradd --create-home --uid 10001 agent && mkdir -p /data && chown agent /data
USER agent
VOLUME ["/data"]
EXPOSE 8080

HEALTHCHECK --interval=30s --timeout=3s --start-period=5s \
  CMD python -c "import urllib.request,os;urllib.request.urlopen(f'http://127.0.0.1:{os.environ[\"PORT\"]}/healthz',timeout=2)"

CMD ["sh", "-c", "exec uvicorn app.main:app --host 0.0.0.0 --port ${PORT} --proxy-headers --forwarded-allow-ips=${FORWARDED_ALLOW_IPS}"]
