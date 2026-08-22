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

from app.config import settings
from app.routers import calendar, coach, dashboard, dev, exercises, health, insights, nutrition, plan, ranks, routines, sessions
from app.routers import settings as settings_router
from app.routers import stats, sync, trackers
from app.routers import streak, routine_notes, generator, report, diet, activities  # restored features
from app.routers import admin, auth as auth_router  # Phase 1-2 friends beta

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

app.include_router(exercises.router)
app.include_router(routines.router)
app.include_router(sessions.router)
app.include_router(stats.router)
app.include_router(health.router)
app.include_router(nutrition.router)
app.include_router(dashboard.router)
app.include_router(calendar.router)
app.include_router(trackers.router)
app.include_router(insights.router)
app.include_router(plan.router)
app.include_router(coach.router)
app.include_router(dev.router)
app.include_router(settings_router.router)
app.include_router(sync.router)
app.include_router(ranks.router)
app.include_router(streak.router)
app.include_router(routine_notes.router)
app.include_router(generator.router)
app.include_router(report.router)
app.include_router(diet.router)
app.include_router(activities.router)
app.include_router(auth_router.router)
app.include_router(admin.router)


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
