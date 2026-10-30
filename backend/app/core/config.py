from functools import lru_cache
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    APP_ENV: str = "development"
    SECRET_KEY: str = "change-me"
    API_KEY: str = "dev-api-key"

    DATABASE_URL: str = "postgresql+psycopg://docintel:docintel@db:5432/docintel"

    REDIS_URL: str = "redis://redis:6379/0"
    CELERY_BROKER_URL: str = "redis://redis:6379/1"
    CELERY_RESULT_BACKEND: str = "redis://redis:6379/2"

    UPLOAD_DIR: str = "storage/uploads"
    MAX_UPLOAD_MB: int = 50

    LLM_PROVIDER: str = "none"  # gemini | openai | none
    LLM_MODEL: str = "gemini-1.5-flash"
    GEMINI_API_KEY: str = ""
    OPENAI_API_KEY: str = ""

    EMBEDDING_MODEL: str = "sentence-transformers/all-MiniLM-L6-v2"
    EMBEDDING_DIM: int = 384

    CORS_ORIGINS: str = "http://localhost:3000,http://127.0.0.1:3000,https://frontend-gamma-eight-24.vercel.app,https://frontend-amqz1p9kv-oli-ahmeds-projects.vercel.app"

    @property
    def cors_origins_list(self) -> list[str]:
        return [o.strip() for o in self.CORS_ORIGINS.split(",") if o.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
