FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /app
COPY pyproject.toml setup.py README.md LICENSE NOTICE ./
COPY src ./src
RUN pip install --no-cache-dir '.[web]' \
    && mkdir -p /data/uploads \
    && chown -R 65532:65532 /data

USER 65532:65532
VOLUME ["/data"]
EXPOSE 8081
HEALTHCHECK --interval=30s --timeout=3s --start-period=10s --retries=3 \
  CMD ["python", "-c", "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8081/health', timeout=2).read()"]
CMD ["trustflow", "serve", "--database", "/data/trustflow.db", "--upload-dir", "/data/uploads", "--host", "127.0.0.1", "--port", "8081"]
