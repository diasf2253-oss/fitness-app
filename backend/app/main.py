"""
FastAPI application entry point.

Responsibilities:
  - Mount all routers
  - Configure CORS (allow the Vite dev server at localhost:5173)
  - Expose public /api/ping health-check
  - In production, serve the built frontend from the same origin
    (single URL for the PWA and the Apple Health pushes)

All health/nutrition data arrives via Apple Health pushes from the phone
(see routers/health.py) — there is no server-side sync job to schedule.
"""
import logging
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.core.config import settings
from app.routers import (
    activities, admin, auth, calendar, coach, dashboard, dev, diet, exercises,
    generator, health, insights, nutrition, plan, ranks, report, routine_notes,
    routines, sessions, settings as settings_router, splits, stats, streak,
    sync, trackers,
)

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)

app = FastAPI(
    title="Personal Fitness & Health API",
    version="0.2.0",
)

# CORS: the Vite dev server, same-LAN phone access, and any configured
# cross-origin frontends (Vercel staging/previews — see config.cors_origins).
_LAN_DEV_REGEX = r"http://192\.168\.\d+\.\d+:5173"
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://127.0.0.1:5173",
        *settings.cors_origin_list,
    ],
    # Allow any local-network IP (192.168.x.x) on port 5173 for gym phone
    # access; CORS_ALLOW_ORIGIN_REGEX widens this (e.g. *.vercel.app previews).
    allow_origin_regex=(
        f"(?:{_LAN_DEV_REGEX})|(?:{settings.cors_allow_origin_regex})"
        if settings.cors_allow_origin_regex
        else _LAN_DEV_REGEX
    ),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ---------------------------------------------------------------------------
# Public health-check (no auth)
# ---------------------------------------------------------------------------

@app.get("/api/ping")
def ping():
    """Public endpoint — used by the frontend to verify the API is reachable.
    `env` lets any frontend detect it is talking to staging (STAGING badge)."""
    return {"status": "ok", "env": settings.app_env}


# ---------------------------------------------------------------------------
# Include routers
# ---------------------------------------------------------------------------

# Order is the original mounting order — keep it (FastAPI matches routes in
# the order they were added). A new feature = a new module in routers/ + one
# entry here.
ROUTERS = (
    exercises, routines, splits, sessions, stats, health, nutrition, dashboard,
    calendar, trackers, insights, plan, coach, dev, settings_router, sync,
    ranks, streak, routine_notes, generator, report, diet, activities, auth,
    admin,
)
for module in ROUTERS:
    app.include_router(module.router)


# ---------------------------------------------------------------------------
# Single-origin frontend serving (production)
#
# When frontend/dist exists (npm run build, or the Docker image's baked
# copy), the API serves it at / — app and API share one URL, so the PWA,
# the phone, and Health Auto Export all point at the same place.
# /api/* routes above always win; everything else falls back to
# index.html so client-side routes deep-link correctly.
# ---------------------------------------------------------------------------

class SPAStaticFiles(StaticFiles):
    """StaticFiles that serves index.html for unknown, extensionless paths."""

    async def get_response(self, path: str, scope):
        try:
            return await super().get_response(path, scope)
        except StarletteHTTPException as exc:
            if exc.status_code == 404:
                return await super().get_response("index.html", scope)
            raise


def mount_frontend(application: FastAPI, dist_dir: str | Path) -> bool:
    """Mount the built frontend if it exists. Returns True when mounted."""
    dist = Path(dist_dir).resolve()
    if not (dist / "index.html").is_file():
        return False
    application.mount("/", SPAStaticFiles(directory=dist, html=True), name="spa")
    logger.info("Serving built frontend from %s", dist)
    return True


if not mount_frontend(app, settings.frontend_dist):
    logger.info("No frontend build found at %s — API-only mode (dev)", settings.frontend_dist)
