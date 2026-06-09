"""
Database engine and session management.

Uses SQLAlchemy 2.x with a synchronous engine so migrations (Alembic) and
regular request handlers share the same setup. Switching to Postgres later
only requires changing DATABASE_URL in .env.
"""
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, DeclarativeBase

from app.config import settings

# connect_args is SQLite-specific: allows the same connection to be used
# across threads (FastAPI runs handlers in a thread pool).
# Postgres doesn't need this arg — it's safe to leave for SQLite only.
connect_args = (
    {"check_same_thread": False}
    if settings.database_url.startswith("sqlite")
    else {}
)

engine = create_engine(
    settings.database_url,
    connect_args=connect_args,
    echo=False,  # set True to log every SQL statement while debugging
)

# Session factory — each request gets its own session via the dependency below
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


class Base(DeclarativeBase):
    """All SQLAlchemy models inherit from this base."""
    pass


def get_db():
    """
    FastAPI dependency that yields a database session per request
    and closes it when the request is done (even on exception).
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
