from __future__ import annotations

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "Instant Flash Backend"
    database_url: str = "postgresql+psycopg://postgres:postgres@localhost:5432/instant_flash"
    jwt_secret_key: str = "change-me-in-production"
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = 60 * 24 * 30
    redis_url: str = "redis://127.0.0.1:6379/0"
    redis_key_prefix: str = "instant_flash"

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")


settings = Settings()
