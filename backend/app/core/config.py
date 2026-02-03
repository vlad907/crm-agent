from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """
    Central application settings loaded from environment variables.
    """

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    app_name: str = "crm-backend"
    environment: str = Field(default="development", alias="ENV")
    debug: bool = False

    database_url: str = Field(
        default="postgresql+psycopg2://postgres:postgres@db:5432/crm_db",
        alias="DATABASE_URL",
    )

    api_prefix: str = "/api/v1"


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
