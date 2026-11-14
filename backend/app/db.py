"""
Database engine and session management.

Uses SQLAlchemy 2.x with a synchronous engine so migrations (Alembic) and
regular request handlers share the same setup. Switching to Postgres later
only requires changing DATABASE_URL in .env.
"""
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, DeclarativeBase

from app.config import settings

def _connect_args(url: str) -> dict:
    """
    Driver options that depend on the database:
      - SQLite: allow one connection to be used across threads (FastAPI runs
        handlers in a thread pool).
      - Postgres via psycopg 3: switch off automatic server-side prepared
        statements. psycopg prepares a query on the server once it has run
        five times — but on Vercel the app talks to Supabase through its
        *transaction pooler* (many app connections share a few real ones),
        and a statement prepared on one real connection doesn't exist on the
        next: "prepared statement … does not exist". Off costs nothing
        noticeable at this app's size and is harmless on a direct connection.
    """
    if url.startswith("sqlite"):
        return {"check_same_thread": False}
    if url.startswith("postgresql+psycopg"):
        return {"prepare_threshold": None}
    return {}


connect_args = _connect_args(settings.database_url)

engine = create_engine(
    settings.database_url,
    connect_args=connect_args,
    echo=False,  # set True to log every SQL statement while debugging
    # Serverless hosts (Vercel) freeze and thaw instances between requests, so a
    # pooled connection can be dead by the time it's reused. Ping before use.
    pool_pre_ping=True,
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
