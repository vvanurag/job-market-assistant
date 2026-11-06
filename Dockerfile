# The Job Market Assistant API (NFR-23). Built and started by: docker compose up -d
FROM python:3.12.16-slim

ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PIP_NO_CACHE_DIR=1 JOBMARKET_HOME=/opt/jobmarket
WORKDIR /opt/jobmarket

COPY pyproject.toml README.md ./
COPY src ./src
RUN pip install --no-cache-dir . && useradd --create-home app
# seeds and macros the API reads at runtime (skill dictionary, rules)
COPY transform/seeds ./transform/seeds
COPY transform/macros ./transform/macros

USER app
EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=5s CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/health')"
CMD ["uvicorn", "jobmarket.api.app:app", "--host", "0.0.0.0", "--port", "8000"]
