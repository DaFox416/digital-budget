from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings, read from environment variables (or a local .env file)."""

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    environment: str = "local"
    cors_origins: list[str] = ["http://localhost:5173"]
    database_url: str = "postgresql+psycopg://budget:budget@localhost:5432/budget"
    # Separate database for the test suite; it's created automatically if missing
    test_database_url: str = "postgresql+psycopg://budget:budget@localhost:5432/budget_test"
    # Used to decide what "today" is for new movements
    timezone: str = "America/Mexico_City"


@lru_cache
def get_settings() -> Settings:
    return Settings()
