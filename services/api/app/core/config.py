from __future__ import annotations

from functools import lru_cache

from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    app_env: str = Field(default="development", alias="APP_ENV")
    project_name: str = Field(default="AgriMandi API", alias="PROJECT_NAME")
    api_v1_prefix: str = Field(default="/api/v1", alias="API_V1_PREFIX")
    database_url: str = Field(alias="DATABASE_URL")
    jwt_secret_key: SecretStr = Field(alias="JWT_SECRET_KEY")
    jwt_refresh_secret_key: SecretStr = Field(alias="JWT_REFRESH_SECRET_KEY")
    jwt_algorithm: str = Field(default="HS256", alias="JWT_ALGORITHM")
    access_token_expire_minutes: int = Field(default=15, alias="ACCESS_TOKEN_EXPIRE_MINUTES")
    refresh_token_expire_days: int = Field(default=14, alias="REFRESH_TOKEN_EXPIRE_DAYS")
    cors_origins: str = Field(default="http://localhost:5173,http://localhost:5174,http://localhost:3000", alias="CORS_ORIGINS")

    # Market Intelligence & External Data Sources (Phase 2B)
    data_gov_in_api_key: SecretStr | None = Field(default=None, alias="DATA_GOV_IN_API_KEY")
    agmarknet_api_base_url: str = Field(default="https://api.data.gov.in/resource", alias="AGMARKNET_API_BASE_URL")
    market_data_outlier_ratio_threshold: float = Field(default=3.0, alias="MARKET_DATA_OUTLIER_RATIO_THRESHOLD")

    @property
    def cors_origin_list(self) -> list[str]:
        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()
