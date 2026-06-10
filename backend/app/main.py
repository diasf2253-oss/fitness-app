"""
FastAPI application entry point.

Responsibilities:
  - Mount all routers
  - Configure CORS (allow the Vite dev server at localhost:5173)
  - Expose public /api/ping health-check

All health/nutrition data arrives via Apple Health pushes from the phone
(see routers/health.py) — there is no server-side sync job to schedule.
"""
import logging

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.routers import dashboard, dev, exercises, health, nutrition, routines, sessions
from app.routers import settings as settings_router
from app.routers import stats

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)

app = FastAPI(
    title="Personal Fitness & Health API",
    version="0.2.0",
)

# CORS: allow the Vite dev server and same-LAN access from phone in the gym
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://127.0.0.1:5173",
    ],
    # Allow any local-network IP (192.168.x.x) on port 5173 for gym phone access
    allow_origin_regex=r"http://192\.168\.\d+\.\d+:5173",
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ---------------------------------------------------------------------------
# Public health-check (no auth)
# ---------------------------------------------------------------------------

@app.get("/api/ping")
def ping():
    """Public endpoint — used by the frontend to verify the API is reachable."""
    return {"status": "ok"}


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
app.include_router(dev.router)
app.include_router(settings_router.router)
