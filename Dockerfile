# syntax=docker/dockerfile:1

# --- UI build stage: produce ui/dist -------------------------------------
FROM node:22-alpine AS ui
WORKDIR /ui
COPY ui/package.json ui/package-lock.json ./
RUN npm install
COPY ui/ ./
RUN npm run build      # -> /ui/dist

# --- backend stage: FastAPI + the built UI -------------------------------
FROM python:3.12.13-slim
WORKDIR /app
COPY backend/pyproject.toml backend/pyproject.toml
COPY backend/requirements.txt backend/requirements.txt
COPY backend/app backend/app
RUN pip install --no-cache-dir --constraint backend/requirements.txt ./backend

# Serve the built UI from "/" (app.main mounts AFR_UI_DIST as static files).
COPY --from=ui /ui/dist /app/ui-dist

ENV AFR_DB_PATH=/data/afr.db \
    AFR_UI_DIST=/app/ui-dist
VOLUME /data
EXPOSE 8700
# Bind 0.0.0.0 *inside the container* so Docker's port publish can reach it.
# Host exposure is still loopback-only: docker-compose publishes 127.0.0.1:8700.
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8700"]
