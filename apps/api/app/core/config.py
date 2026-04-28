from __future__ import annotations

from functools import lru_cache

from typing import Any

from pydantic import AliasChoices, Field, field_validator, model_validator
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
    cors_origins: list[str] = ["http://localhost:5173", "http://127.0.0.1:5173"]

    database_url: str = Field(default="", validation_alias=AliasChoices("DATABASE_URL"))
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

    jwt_secret: str = Field(
        default="change-me-in-development",
        validation_alias=AliasChoices("JWT_SECRET", "JWT_SECRET_KEY"),
    )
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = 60

    @field_validator("cors_origins", mode="before")
    @classmethod
    def parse_cors_origins(cls, value: Any) -> Any:
        if isinstance(value, str):
            return [origin.strip() for origin in value.split(",") if origin.strip()]
        return value

    @model_validator(mode="after")
    def build_database_url(self) -> Settings:
        if not self.database_url:
            self.database_url = (
                f"postgresql+psycopg://{self.postgres_user}:{self.postgres_password}"
                f"@{self.postgres_host}:{self.postgres_port}/{self.postgres_db}"
            )
        return self


@lru_cache
def get_settings() -> Settings:
    return Settings()
