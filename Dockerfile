# ---------------------------------------------------------------------------
# Single-image build: compile the frontend, then serve app + API from
# FastAPI on one origin. Works as-is on Railway/Fly/any Docker host.
#
# Persist the database! Mount a volume at /app/data and set:
#   DATABASE_URL=sqlite:////app/data/fitness.sqlite3
# (or point DATABASE_URL at Postgres). Also set ADMIN_EMAIL/ADMIN_PASSWORD
# (Phase 1-2 friends beta — creates the admin account + first invite code).
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

# Boot sequence: apply DB migrations, ensure the admin account + first invite
# code exist, seed the (idempotent) exercise library, then start the server.
# All three steps are safe to re-run on every deploy. The real database lives
# on the persistent volume mounted at /app/data and survives redeploys, so no
# user data is seeded here — that was a one-time bootstrap and is now done.
CMD ["sh", "-c", "alembic upgrade head && python -m app.seed_admin && python -m app.seed && uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000}"]
