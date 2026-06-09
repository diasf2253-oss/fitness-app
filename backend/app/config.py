"""
Application configuration loaded from the .env file via pydantic-settings.
All settings have defaults so the app starts even without a .env (for tests).
"""
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    # Bearer token that protects every API route except /api/ping
    app_token: str = "changeme"

    # YAZIO credentials — filled in by the user, never hardcoded
    yazio_email: str = "placeholder@example.com"
    yazio_password: str = "placeholder"

    # SQLAlchemy connection string.
    # Swap to postgresql+psycopg://... to move off SQLite.
    database_url: str = "sqlite:///./fitness.sqlite3"

    model_config = SettingsConfigDict(
        env_file=".env",        # looks for .env relative to the working directory
        env_file_encoding="utf-8",
        case_sensitive=False,   # APP_TOKEN and app_token both work
    )


# Module-level singleton — import this everywhere
settings = Settings()
