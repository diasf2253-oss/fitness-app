"""
Application configuration loaded from the .env file via pydantic-settings.
All settings have defaults so the app starts even without a .env (for tests).
"""
from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    # Supabase Auth: Supabase runs sign-in (email + password, Google) and
    # hands the browser a signed access token; app/core/supabase_auth.py checks
    # that token on every request. This app still decides who gets in
    # (invite code → pending → admin approval) via its own users table.
    #   SUPABASE_URL              https://<project-ref>.supabase.co
    #   SUPABASE_PUBLISHABLE_KEY  the publishable (or legacy anon) key — public
    #                             by design; used to ask Supabase whether an
    #                             email address is confirmed
    #   SUPABASE_SECRET_KEY       optional, server-only — a secret key
    #                             (sb_secret_…) or the legacy service_role key;
    #                             only needed for the admin "reset link" button
    # Empty SUPABASE_URL ⇒ every signed-in route answers 503 "login isn't
    # configured", and the rest (ping, the built frontend) still works.
    supabase_url: str = ""
    supabase_publishable_key: str = ""
    supabase_secret_key: str = ""

    @field_validator("supabase_url")
    @classmethod
    def _strip_trailing_slash(cls, v: str) -> str:
        return v.strip().rstrip("/")

    @property
    def supabase_issuer(self) -> str:
        """The `iss` claim every genuine user token from this project carries."""
        return f"{self.supabase_url}/auth/v1"

    # Brute-force speed bump on the signup endpoint (/join), enforced in
    # app/core/ratelimit.py. Password sign-in itself is rate-limited by Supabase.
    # Disabled in tests (conftest sets it false); test_rate_limit.py flips it
    # back on to exercise it.
    auth_rate_limit_enabled: bool = True

    # The first admin account (python -m app.cli.seed_admin) and the migration
    # backfill that attaches all pre-multi-user data to it. There is no admin
    # password here any more: the admin signs in through Supabase with this
    # email, and app/core/auth.py links the two on first sign-in.
    # Never hardcode it — env vars only.
    admin_email: str = ""

    # SQLAlchemy connection string. SQLite by default (local dev, tests);
    # Supabase Postgres on Vercel (the transaction pooler). A bare postgres URL is normalized to the psycopg (v3) driver
    # below — see _use_psycopg_driver.
    database_url: str = "sqlite:///./fitness.sqlite3"

    @field_validator("database_url")
    @classmethod
    def _use_psycopg_driver(cls, v: str) -> str:
        """
        Route bare Postgres URLs to psycopg 3 (the driver in requirements.txt).

        Supabase hands out `postgresql://...` strings (and some providers use
        the legacy `postgres://`). With no explicit driver, SQLAlchemy
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
    # production deployment) or 'staging' (set APP_ENV=staging on previews). Exposed on /api/ping so the frontend
    # can show its STAGING badge no matter which build is talking to us.
    app_env: str = "production"

    # Sample-data seeding (POST /api/dev/seed-sample-health) writes ~30 days of
    # invented weight/steps/sleep/nutrition into a real account. That is a demo
    # convenience, never something a beta user should be able to trigger — so it
    # is off unless explicitly switched on (ENABLE_DEV_SEED=true in a local .env).
    # Note we deliberately do NOT key this off app_env: that defaults to
    # 'production' on the laptop too, so it cannot tell "my machine" from "the
    # production deployment". The matching DELETE stays available everywhere so
    # leftover sample rows can always be cleaned up.
    enable_dev_seed: bool = False

    # Cross-origin frontends — only needed if a frontend is ever served from a
    # different domain than the API (today both share one Vercel domain). Comma-separated exact origins:
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
