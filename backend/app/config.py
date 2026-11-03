"""Configuration de l'API, lue depuis les variables d'environnement (ou le fichier .env)."""

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    app_name: str = "SmartNuggets API"

    # SQLite par défaut pour le développement local ; PostgreSQL (asyncpg) en production.
    database_url: str = "sqlite+aiosqlite:///./smartnuggets.db"


@lru_cache
def get_settings() -> Settings:
    return Settings()
