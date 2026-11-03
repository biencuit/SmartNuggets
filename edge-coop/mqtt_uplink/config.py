"""Configuration lue dans les variables d'environnement (voir .env.example)."""

import os
from collections.abc import Mapping
from dataclasses import dataclass


def _bool(value: str) -> bool:
    return value.strip().lower() in {"1", "true", "yes", "oui"}


@dataclass(frozen=True)
class UplinkConfig:
    coop_id: str
    mqtt_host: str
    mqtt_port: int = 8883
    mqtt_tls: bool = True
    mqtt_ca_cert: str | None = None
    mqtt_username: str | None = None
    mqtt_password: str | None = None
    outbox_path: str = "outbox.db"
    command_max_age_s: float = 60.0
    keepalive_s: int = 30

    @classmethod
    def from_env(cls, env: Mapping[str, str] | None = None) -> "UplinkConfig":
        env = os.environ if env is None else env
        return cls(
            coop_id=env["COOP_ID"],
            mqtt_host=env["MQTT_HOST"],
            mqtt_port=int(env.get("MQTT_PORT", "8883")),
            mqtt_tls=_bool(env.get("MQTT_TLS", "true")),
            mqtt_ca_cert=env.get("MQTT_CA_CERT") or None,
            mqtt_username=env.get("MQTT_USERNAME") or None,
            mqtt_password=env.get("MQTT_PASSWORD") or None,
            outbox_path=env.get("OUTBOX_PATH", "outbox.db"),
            command_max_age_s=float(env.get("COMMAND_MAX_AGE_S", "60")),
        )
