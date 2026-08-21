from functools import lru_cache
from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

def normalize_database_url(url: str) -> str:
    """Neon/Supabase give postgresql://; SQLAlchemy async needs +asyncpg."""
    if url.startswith("postgres://"):
        url = "postgresql://" + url[len("postgres://") :]
    if url.startswith("postgresql://") and "+asyncpg" not in url:
        url = "postgresql+asyncpg://" + url[len("postgresql://") :]
    return url

class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_prefix="OPERAI_", extra="ignore")
    database_url: str = "postgresql+asyncpg://postgres:postgres@localhost:5432/operai"
    jwt_secret: str = Field("development-secret-change-this-now", min_length=32)
    access_token_minutes: int = 30
    refresh_token_days: int = 30
    cors_origins: list[str] = ["http://localhost:3000"]
    asaas_api_key: str = ""
    asaas_api_url: str = "https://sandbox.asaas.com/api/v3"
    asaas_webhook_token: str = "dev-asaas-webhook"
    trial_days: int = 14
    encryption_key: str = ""
    evolution_api_url: str = "http://127.0.0.1:8080"
    evolution_api_key: str = ""
    public_api_url: str = "http://127.0.0.1:8001"
    frontend_url: str = "http://localhost:3000"

    @field_validator("database_url", mode="before")
    @classmethod
    def _db_url(cls, value: str) -> str:
        return normalize_database_url(str(value))

@lru_cache
def get_settings() -> Settings:
    return Settings()
