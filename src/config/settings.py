from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment variables or .env file."""

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")

    anthropic_api_key: str
    redis_url: str = "redis://localhost:6379"
    database_url: str = "postgresql://localhost:5432/predictive_maintenance"
    langfuse_secret_key: str = ""
    langfuse_public_key: str = ""
    environment: str = "development"


settings = Settings()
