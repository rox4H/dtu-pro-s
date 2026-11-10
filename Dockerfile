FROM python:3.13-slim

LABEL org.opencontainers.image.title="Hoymiles DTU Reader" \
      org.opencontainers.image.description="Read-only local JSON reader for Hoymiles DTUs." \
      org.opencontainers.image.source="https://github.com/rox4H/dtu-pro-s" \
      org.opencontainers.image.licenses="MIT"

WORKDIR /app

COPY pyproject.toml README.md LICENSE NOTICE ./
COPY src ./src

RUN pip install --no-cache-dir . \
 && useradd --system --no-create-home reader \
 && mkdir -p /data/logs \
 && chown -R reader /data

USER reader
ENV HTTP_HOST=0.0.0.0 \
    LOG_DIR=/data/logs \
    PYTHONUNBUFFERED=1

EXPOSE 5001
VOLUME ["/data"]

HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
  CMD ["python", "-c", "import os,urllib.request as u; t=os.getenv('API_TOKEN'); r=u.Request('http://127.0.0.1:5001/api/health', headers={'Authorization':f'Bearer {t}'} if t else {}); u.urlopen(r, timeout=4)"]

CMD ["hoymiles-dtu-reader"]
