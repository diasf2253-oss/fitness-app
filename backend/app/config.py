"""
Application configuration loaded from the .env file via pydantic-settings.
All settings have defaults so the app starts even without a .env (for tests).
"""
from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    # Cookie session auth (Phase 1-2 friends beta). The cookie carries an
    # opaque session id (never a JWT) looked up against the auth_session
    # table, so logout / temp-password resets can invalidate it server-side.
    session_cookie_name: str = "session_id"
    session_max_age_days: int = 30
    # False only for local dev over http:// and tests — browsers silently
    # refuse to store/send a Secure cookie on a non-HTTPS connection, so this
    # must be false there or every login would appear to succeed and then
    # immediately look logged-out. Always true on Railway/Vercel (HTTPS).
    session_cookie_secure: bool = True

    # Brute-force speed bump on the auth endpoints (login/join), enforced in
    # app/ratelimit.py. Disabled in tests (conftest sets it false) so the
    # suite's many logins don't trip the limit.
    auth_rate_limit_enabled: bool = True

    # Seeds the first admin account (python -m app.seed_admin) and the
    # migration backfill that attaches all pre-multi-user data to it.
    # Never hardcode these — env vars only.
    admin_email: str = ""
    admin_password: str = ""

    # SQLAlchemy connection string. SQLite by default; Postgres in production
    # (Railway). A bare postgres URL is normalized to the psycopg (v3) driver
    # below — see _use_psycopg_driver.
    database_url: str = "sqlite:///./fitness.sqlite3"

    @field_validator("database_url")
    @classmethod
    def _use_psycopg_driver(cls, v: str) -> str:
        """
        Route bare Postgres URLs to psycopg 3 (the driver in requirements.txt).

        Railway injects DATABASE_URL as `postgresql://...` (and some providers
        use the legacy `postgres://`). With no explicit driver, SQLAlchemy
        reaches for psycopg2, which we don't ship — so every DB call (and the
        boot-time `alembic upgrade head`) fails with ModuleNotFoundError and
        the app 500s. Rewriting the scheme to `postgresql+psycopg://` makes it
        use the installed driver. SQLite and explicit `+driver` URLs are left
        untouched, so tests and anyone who pins a driver are unaffected.
        """
        if v.startswith("postgres://"):
            v = "postgresql://" + v[len("postgres://"):]
        if v.startswith("postgresql://"):
            v = "postgresql+psycopg://" + v[len("postgresql://"):]
        return v

    # Which deployment this is: 'production' (default — the laptop and the
    # Railway prod service) or 'staging'. Exposed on /api/ping so the frontend
    # can show its STAGING badge no matter which build is talking to us.
    app_env: str = "production"

    # Sample-data seeding (POST /api/dev/seed-sample-health) writes ~30 days of
    # invented weight/steps/sleep/nutrition into a real account. That is a demo
    # convenience, never something a beta user should be able to trigger — so it
    # is off unless explicitly switched on (ENABLE_DEV_SEED=true in a local .env).
    # Note we deliberately do NOT key this off app_env: that defaults to
    # 'production' on the laptop too, so it cannot tell "my machine" from "the
    # Railway prod service". The matching DELETE stays available everywhere so
    # leftover sample rows can always be cleaned up.
    enable_dev_seed: bool = False

    # Cross-origin frontends (the Vercel staging/preview deployments call the
    # Railway API from another origin). Comma-separated exact origins:
    #   CORS_ORIGINS=https://fitness-staging.vercel.app
    # plus an optional regex for the per-branch preview URLs:
    #   CORS_ALLOW_ORIGIN_REGEX=https://.*\.vercel\.app
    # Both empty (the default) ⇒ same-origin + Vite-dev only, as before.
    cors_origins: str = ""
    cors_allow_origin_regex: str = ""

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]

    # Built-frontend directory (relative to the backend working directory).
    # When it exists, the API also serves the app — one origin for
    # everything, which is what the PWA and Health Auto Export point at.
    # The Docker image overrides this to its baked-in copy.
    frontend_dist: str = "../frontend/dist"

    # AI Coach (Claude). Empty key → coach endpoints return 503 and the rest
    # of the app works unchanged; tests never need a real key.
    anthropic_api_key: str = ""
    coach_model: str = "claude-opus-4-8"

    @property
    def coach_enabled(self) -> bool:
        return bool(self.anthropic_api_key)

    model_config = SettingsConfigDict(
        env_file=".env",        # looks for .env relative to the working directory
        env_file_encoding="utf-8",
        case_sensitive=False,   # DATABASE_URL and database_url both work
        extra="ignore",         # stale .env entries must never crash startup
    )


# Module-level singleton — import this everywhere
settings = Settings()
