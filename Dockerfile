# syntax=docker/dockerfile:1

FROM python:3.12.13-slim
WORKDIR /app

COPY backend/pyproject.toml backend/pyproject.toml
COPY backend/requirements.txt backend/requirements.txt
COPY backend/app backend/app

RUN pip install --no-cache-dir --constraint backend/requirements.txt ./backend

ENV AFR_DB_PATH=/data/afr.db
VOLUME /data
EXPOSE 8700

# Bind 0.0.0.0 inside the container so Docker's loopback-only host publish can reach it.
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8700"]
