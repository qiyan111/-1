from __future__ import annotations

from functools import lru_cache

from pydantic import computed_field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    app_name: str = "Flow Cytometry Platform"
    app_version: str = "0.1.0"
    app_env: str = "local"

    postgres_user: str = "flow_user"
    postgres_password: str = "flow_password"
    postgres_db: str = "flow_cytometry"
    postgres_host: str = "localhost"
    postgres_port: int = 5432

    redis_url: str = "redis://localhost:6379/0"

    minio_endpoint: str = "http://localhost:9000"
    minio_bucket: str = "flow-cytometry-raw"
    minio_root_user: str = "minioadmin"
    minio_root_password: str = "minioadmin"

    jwt_secret_key: str = "change-me-in-development"
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = 60

    @computed_field
    @property
    def database_url(self) -> str:
        return (
            f"postgresql+psycopg://{self.postgres_user}:{self.postgres_password}"
            f"@{self.postgres_host}:{self.postgres_port}/{self.postgres_db}"
        )


@lru_cache
def get_settings() -> Settings:
    return Settings()

