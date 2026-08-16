# syntax=docker/dockerfile:1

FROM node:22-alpine AS ui-builder
WORKDIR /src/ui

COPY ui/package.json ui/package-lock.json ./
RUN npm ci

COPY ui/ ./
RUN npm run build

FROM python:3.12.13-slim
WORKDIR /app

COPY backend/pyproject.toml backend/pyproject.toml
COPY backend/requirements.txt backend/requirements.txt
COPY backend/app backend/app
COPY sdk/pyproject.toml sdk/pyproject.toml
COPY sdk/afr sdk/afr
COPY cli/pyproject.toml cli/pyproject.toml
COPY cli/afr_cli cli/afr_cli
COPY --from=ui-builder /src/ui/dist /app/ui/dist

RUN pip install --no-cache-dir --constraint backend/requirements.txt ./sdk ./cli ./backend \
    && python -m pip check

ENV AFR_DB_PATH=/data/afr.db \
    AFR_UI_DIST=/app/ui/dist \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

VOLUME /data
EXPOSE 8700

HEALTHCHECK --interval=10s --timeout=3s --start-period=10s --retries=6 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8700/health', timeout=2).read()" || exit 1

# Bind 0.0.0.0 inside the container so Docker's loopback-only host publish can reach it.
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8700"]
