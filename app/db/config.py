from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict
from sqlalchemy.engine import make_url


class Settings(BaseSettings):
    database_url: str = Field(validation_alias="DATABASE_URL")
    classification_reset_token: str | None = Field(
        default=None, min_length=32, validation_alias="CLASSIFICATION_RESET_TOKEN"
    )
    openrouter_api_key: str | None = Field(default=None, validation_alias="OPENROUTER_API_KEY")
    openrouter_base_url: str = Field(default="https://openrouter.ai/api/v1", validation_alias="OPENROUTER_BASE_URL")
    openrouter_light_model: str = Field(default="openai/gpt-4.1-mini", validation_alias="OPENROUTER_LIGHT_MODEL")
    openrouter_heavy_model: str = Field(default="openai/gpt-4.1", validation_alias="OPENROUTER_HEAVY_MODEL")
    cors_origins: str = Field(default="http://localhost:5173,http://127.0.0.1:5173", validation_alias="CORS_ORIGINS")

    @property
    def cors_origin_list(self) -> list[str]:
        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    def sqlalchemy_url(self) -> str:
        """Normalize common Aiven URLs to the psycopg 3 SQLAlchemy driver."""
        url = make_url(self.database_url)
        if url.drivername in {"postgres", "postgresql"}:
            url = url.set(drivername="postgresql+psycopg")
        return url.render_as_string(hide_password=False)


@lru_cache
def get_settings() -> Settings:
    return Settings()
