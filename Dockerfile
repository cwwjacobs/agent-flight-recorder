# Agent Flight Recorder — single-image deploy (backend + built UI)
#
#   docker compose up --build        → http://localhost:8700
#
# Stage 1 builds the web UI; stage 2 runs FastAPI and serves the UI as
# static files. SQLite lives on the /data volume.

# Pin to patch-version tag. Digest pinning is the next step; tracked in
# docs/dependency-integrity.md.
FROM node:20.19.3-slim AS ui-build
WORKDIR /build
COPY ui/package.json ui/package-lock.json ./
RUN npm ci --no-audit --no-fund
COPY ui/ ./
RUN npm run build

# Pin to patch-version tag. Digest pinning is the next step; tracked in
# docs/dependency-integrity.md.
FROM python:3.12.13-slim
WORKDIR /app

COPY backend/pyproject.toml backend/pyproject.toml
COPY backend/requirements.txt backend/requirements.txt
COPY backend/app backend/app
RUN pip install --no-cache-dir --constraint backend/requirements.txt ./backend

COPY --from=ui-build /build/dist /app/ui-dist

ENV AFR_DB_PATH=/data/afr.db \
    AFR_UI_DIST=/app/ui-dist
# Premium is opt-in: set AFR_PREMIUM_ENABLED=true at run time.
# SECURITY: the API is unauthenticated unless AFR_API_TOKEN is set. Publishing
# port 8700 exposes the full API (including mutating MCP tools) to anything that
# can reach it — set AFR_API_TOKEN for any non-loopback deployment.

VOLUME /data
EXPOSE 8700

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8700"]
