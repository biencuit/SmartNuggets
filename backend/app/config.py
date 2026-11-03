"""Configuration de l'API, lue depuis les variables d'environnement (ou le fichier .env)."""

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    app_name: str = "SmartNuggets API"

    # SQLite par défaut pour le développement local ; PostgreSQL (asyncpg) en production.
    database_url: str = "sqlite+aiosqlite:///./smartnuggets.db"

    # Authentification (JWT signé HS256). Sans clé, une clé aléatoire est générée au
    # démarrage : pratique en développement, mais les sessions sont perdues à chaque relance.
    jwt_secret_key: str | None = None
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = 1440

    # Origines autorisées à appeler l'API depuis un navigateur (frontend).
    cors_origins: list[str] = ["http://localhost:5173"]

    # Photos des alertes envoyées par le Raspberry Pi.
    media_dir: str = "media"
    max_image_bytes: int = 2_000_000

    # Broker MQTT (Mosquitto). Désactivé par défaut : l'API tourne alors sans le poulailler.
    mqtt_enabled: bool = False
    mqtt_host: str = "localhost"
    mqtt_port: int = 8883
    mqtt_tls: bool = True
    mqtt_ca_cert: str | None = None  # None : autorités de certification du système
    mqtt_username: str | None = None
    mqtt_password: str | None = None
    mqtt_client_id: str = "smartnuggets-backend"


@lru_cache
def get_settings() -> Settings:
    return Settings()
