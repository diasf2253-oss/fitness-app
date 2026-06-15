"""
Application configuration loaded from the .env file via pydantic-settings.
All settings have defaults so the app starts even without a .env (for tests).
"""
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    # Bearer token that protects every API route except /api/ping
    app_token: str = "changeme"

    # SQLAlchemy connection string.
    # Swap to postgresql+psycopg://... to move off SQLite.
    database_url: str = "sqlite:///./fitness.sqlite3"

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
        case_sensitive=False,   # APP_TOKEN and app_token both work
        extra="ignore",         # stale .env entries must never crash startup
    )


# Module-level singleton — import this everywhere
settings = Settings()
