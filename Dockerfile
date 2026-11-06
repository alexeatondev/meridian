# Meridian hosted app
FROM python:3.12-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PIP_NO_CACHE_DIR=1
WORKDIR /app
COPY pyproject.toml README.md ./
COPY src ./src
COPY config ./config
COPY policies ./policies
COPY regimes ./regimes
COPY agents ./agents
COPY skills ./skills
COPY schemas ./schemas
RUN pip install ".[app]" && useradd --create-home --uid 10001 meridian
# the package resolves config/policies relative to the repo root; point it at /app
ENV MERIDIAN_REPO_ROOT=/app
USER meridian
EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=5s CMD python -c "import urllib.request;urllib.request.urlopen('http://127.0.0.1:8000/healthz')"
CMD ["uvicorn", "meridian.app.main:app", "--host", "0.0.0.0", "--port", "8000", "--proxy-headers", "--forwarded-allow-ips", "*"]
