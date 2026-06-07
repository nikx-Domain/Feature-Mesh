from enum import Enum

from pydantic_settings import BaseSettings, SettingsConfigDict


class AppEnv(str, Enum):
    DEVELOPMENT = "development"
    TESTING = "testing"
    STAGING = "staging"
    PRODUCTION = "production"


class Settings(BaseSettings):
    APP_ENV: AppEnv = AppEnv.DEVELOPMENT
    LOG_LEVEL: str = "info"

    # Database Settings
    POSTGRES_USER: str = "postgres"
    POSTGRES_PASSWORD: str = "postgres_secure_password"
    POSTGRES_DB: str = "feature_flags"
    POSTGRES_HOST: str = "localhost"
    POSTGRES_PORT: int = 5432

    # Defaults to async connection string for the application
    DATABASE_URL: str = (
        "postgresql+asyncpg://postgres:postgres_secure_password@localhost:5432/feature_flags"
    )

    # Redis Cache
    REDIS_URL: str = "redis://localhost:6379/0"

    # Kafka
    KAFKA_BOOTSTRAP_SERVERS: str = "localhost:9092"

    # JWT Settings (RS256)
    JWT_PRIVATE_KEY: str = ""
    JWT_PUBLIC_KEY: str = ""

    model_config = SettingsConfigDict(
        env_file=".env", env_file_encoding="utf-8", extra="ignore"
    )


settings = Settings()
