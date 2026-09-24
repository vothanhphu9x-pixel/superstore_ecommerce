from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


BASE_DIR = Path(__file__).resolve().parents[1]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=BASE_DIR / ".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    app_name: str = "superstore-api"
    app_env: str = "development"

    api_host: str = "0.0.0.0"
    api_port: int = 8000
    api_reload: bool = False
    api_cors_origins: str = "http://localhost:3000"
    api_key: str = ""

    cache_enabled: bool = True
    redis_url: str = "redis://localhost:6379/0"
    cache_ttl_seconds: int = 900
    cache_key_prefix: str = "superstore"

    snowflake_account: str = ""
    snowflake_user: str = ""
    snowflake_password: str = ""
    snowflake_database: str = "SUPERSTORE_DB"
    snowflake_gold_schema: str = "ANALYTIC_LAYER_GOLD_LAYER"
    snowflake_mart_schema: str = "ANALYTIC_LAYER_MART_LAYER"
    snowflake_warehouse: str = "COMPUTE_WH"
    snowflake_role: str = "ANALYTICS_READONLY"
    snowflake_max_rows: int = 1000
    snowflake_query_timeout: int = 30

    log_level: str = "INFO"
    log_file: str = "logs/application.log"

    @property
    def cors_origins(self) -> list[str]:
        raw = self.api_cors_origins.strip()

        if raw == "*":
            return ["*"]

        return [
            origin.strip()
            for origin in raw.split(",")
            if origin.strip()
        ]


@lru_cache
def get_settings() -> Settings:
    return Settings()