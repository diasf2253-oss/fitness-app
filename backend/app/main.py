"""
FastAPI application entry point.

Responsibilities:
  - Mount all routers
  - Configure CORS (allow the Vite dev server at localhost:5173)
  - Register startup/shutdown events (APScheduler for YAZIO daily sync)
  - Expose public /api/ping health-check
"""
import logging
from contextlib import asynccontextmanager
from datetime import datetime

from fastapi import Depends, FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session

from app.auth import require_auth
from app.config import settings
from app.db import get_db
from app.routers import exercises, health, nutrition, routines, sessions
from app.routers import settings as settings_router
from app.routers import stats

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)


# ---------------------------------------------------------------------------
# APScheduler — daily YAZIO sync at 23:30 local time
# ---------------------------------------------------------------------------

def _create_scheduler():
    """Set up APScheduler with the YAZIO daily sync job."""
    from apscheduler.schedulers.asyncio import AsyncIOScheduler
    from apscheduler.triggers.cron import CronTrigger

    scheduler = AsyncIOScheduler()

    async def _yazio_nightly():
        """Run at 23:30 local time — syncs the last 2 days."""
        logger.info("APScheduler: starting nightly YAZIO sync")
        from app.db import SessionLocal
        from app.integrations.yazio import sync_days
        from app.models import AppSettings

        db = SessionLocal()
        try:
            result = await sync_days(
                days=2,
                email=settings.yazio_email,
                password=settings.yazio_password,
                db=db,
            )
            s = db.get(AppSettings, 1)
            if s:
                if result["errors"]:
                    s.yazio_last_error = "; ".join(result["errors"])
                else:
                    s.yazio_last_sync = datetime.utcnow()
                    s.yazio_last_error = None
                db.commit()
            logger.info("Nightly YAZIO sync done: %s", result)
        except Exception as e:
            logger.error("Nightly YAZIO sync crashed: %s", e)
        finally:
            db.close()

    scheduler.add_job(
        _yazio_nightly,
        CronTrigger(hour=23, minute=30),
        id="yazio_nightly",
        replace_existing=True,
    )
    return scheduler


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Start the scheduler on app startup, shut it down on exit."""
    scheduler = _create_scheduler()
    scheduler.start()
    logger.info("APScheduler started (YAZIO nightly sync at 23:30)")
    yield
    scheduler.shutdown()
    logger.info("APScheduler shut down")


# ---------------------------------------------------------------------------
# App
# ---------------------------------------------------------------------------

app = FastAPI(
    title="Personal Fitness & Health API",
    version="0.1.0",
    lifespan=lifespan,
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
# YAZIO manual sync endpoint
# ---------------------------------------------------------------------------

@app.post("/api/sync/yazio")
async def sync_yazio(
    days: int = 3,
    db: Session = Depends(get_db),
    _: None = Depends(require_auth),
):
    """Manually trigger a YAZIO nutrition sync for the last N days (default 3)."""
    from app.integrations.yazio import sync_days
    from app.models import AppSettings

    result = await sync_days(
        days=days,
        email=settings.yazio_email,
        password=settings.yazio_password,
        db=db,
    )

    # Update settings with sync result
    s = db.get(AppSettings, 1)
    if s:
        if result["errors"]:
            s.yazio_last_error = "; ".join(result["errors"])
        else:
            s.yazio_last_sync = datetime.utcnow()
            s.yazio_last_error = None
        db.commit()

    return {
        "days_synced": days,
        "rows_upserted": result["rows_upserted"],
        "errors": result["errors"],
        "message": "Sync complete" if not result["errors"] else "Sync completed with errors",
    }


# ---------------------------------------------------------------------------
# Include routers
# ---------------------------------------------------------------------------

app.include_router(exercises.router)
app.include_router(routines.router)
app.include_router(sessions.router)
app.include_router(stats.router)
app.include_router(health.router)
app.include_router(nutrition.router)
app.include_router(settings_router.router)
