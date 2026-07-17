# ---------------------------------------------------------------------------
# Single-image build: compile the frontend, then serve app + API from
# FastAPI on one origin. Works as-is on Railway/Fly/any Docker host.
#
# Persist the database! Mount a volume at /app/data and set:
#   DATABASE_URL=sqlite:////app/data/fitness.sqlite3
# (or point DATABASE_URL at Postgres). Also set a strong APP_TOKEN.
# ---------------------------------------------------------------------------

FROM node:20-alpine AS frontend
WORKDIR /build
COPY frontend/package*.json ./
RUN npm ci
COPY frontend/ ./
# Railway passes service variables as build args when declared. The staging
# service sets VITE_APP_ENV=staging so the baked-in frontend shows its
# STAGING badge without waiting for the runtime /api/ping probe.
ARG VITE_APP_ENV=""
ENV VITE_APP_ENV=$VITE_APP_ENV
RUN npm run build


FROM python:3.12-slim
WORKDIR /app

COPY backend/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY backend/ .
COPY --from=frontend /build/dist /app/static
ENV FRONTEND_DIST=/app/static

EXPOSE 8000

# Migrations and the (idempotent) exercise-library seed run on every boot,
# so a fresh volume comes up ready to use.
CMD ["sh", "-c", "alembic upgrade head && python -m app.seed && uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000}"]
