# Backend image: FastAPI + Kubernetes client + Prometheus client + AI agent
#
# OFFLINE BUILD: the Python packages are downloaded on the Windows host first
# (scripts\prepare-docker-build.ps1 -> backend\wheels\). Inside docker build there is no reliable
# internet access in this environment (Clash / blocked registries), so pip installs only from ./wheels.
FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    KUBECONFIG=/home/app/.kube/config

RUN useradd --create-home --uid 10001 app
WORKDIR /app

COPY requirements.txt .
COPY wheels ./wheels
RUN pip install --no-index --find-links=/app/wheels -r requirements.txt && rm -rf /app/wheels

COPY app ./app

USER app
EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=5s --start-period=15s \
  CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/', timeout=3)" || exit 1

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
