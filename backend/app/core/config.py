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
        default="sqlite:///./crm.db",
        alias="DATABASE_URL",
    )
    openai_api_key: str | None = Field(default=None, alias="OPENAI_API_KEY")
    anthropic_api_key: str | None = Field(default=None, alias="ANTHROPIC_API_KEY")
    anthropic_model: str = Field(default="claude-sonnet-4-5", alias="ANTHROPIC_MODEL")
    google_places_api_key: str | None = Field(default=None, alias="GOOGLE_PLACES_API_KEY")
    google_oauth_client_id: str | None = Field(default=None, alias="GOOGLE_OAUTH_CLIENT_ID")
    google_oauth_client_secret: str | None = Field(default=None, alias="GOOGLE_OAUTH_CLIENT_SECRET")
    gmail_oauth_redirect_uri: str = Field(
        default="http://localhost:8000/api/v1/integrations/gmail/callback",
        alias="GMAIL_OAUTH_REDIRECT_URI",
    )
    google_login_redirect_uri: str = Field(
        default="http://localhost:8000/api/v1/auth/google/callback",
        alias="GOOGLE_LOGIN_REDIRECT_URI",
    )
    gmail_oauth_scopes: str = Field(
        default=(
            "https://www.googleapis.com/auth/gmail.compose "
            "https://www.googleapis.com/auth/gmail.send "
            "https://www.googleapis.com/auth/gmail.modify"
        ),
        alias="GMAIL_OAUTH_SCOPES",
    )
    oauth_state_signing_secret: str = Field(default="dev-oauth-state-secret", alias="OAUTH_STATE_SIGNING_SECRET")
    frontend_base_url: str = Field(default="http://localhost:3000", alias="FRONTEND_BASE_URL")
    openai_model: str = Field(default="gpt-4o-mini", alias="OPENAI_MODEL")
    openai_rate_limit_retries: int = Field(default=5, alias="OPENAI_RATE_LIMIT_RETRIES")
    openai_rate_limit_backoff_seconds: float = Field(
        default=1.0,
        alias="OPENAI_RATE_LIMIT_BACKOFF_SECONDS",
    )
    default_workspace_id: str | None = Field(default=None, alias="DEFAULT_WORKSPACE_ID")
    default_user_id: str | None = Field(default=None, alias="DEFAULT_USER_ID")
    pipeline_worker_enabled: bool = Field(default=True, alias="PIPELINE_WORKER_ENABLED")
    pipeline_worker_interval_seconds: int = Field(default=45, alias="PIPELINE_WORKER_INTERVAL_SECONDS")
    pipeline_worker_batch_size: int = Field(default=5, alias="PIPELINE_WORKER_BATCH_SIZE")

    api_prefix: str = "/api/v1"


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
