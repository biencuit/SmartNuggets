"""Client MQTT du Raspberry Pi : envoi des événements et réception des commandes.

- Connexion TLS (port 8883) avec un compte par poulailler (nom d'utilisateur = COOP_ID).
- Last Will : si le Pi disparaît (câble, courant), le broker publie "offline" sur
  smartnuggets/{coop_id}/status ; le Pi publie "online" à chaque connexion.
- Sortant : tout passe par l'Outbox SQLite. Un thread d'envoi publie les messages un par
  un, dans l'ordre, et ne les retire qu'après l'accusé de réception du broker (PUBACK).
- Entrant : une commande plus vieille que COMMAND_MAX_AGE_S est ignorée, ainsi qu'une
  commande déjà reçue (même command_id), pour ne jamais ouvrir la porte au mauvais moment.

Les callbacks paho tournent dans le thread réseau : `on_command` doit rendre la main vite
(par exemple en déposant la commande dans une file traitée par le contrôleur de porte).
"""

import base64
import json
import logging
import threading
import time
from collections import deque
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

import paho.mqtt.client as mqtt
from paho.mqtt.enums import CallbackAPIVersion

from mqtt_uplink.config import UplinkConfig
from mqtt_uplink.outbox import Outbox

logger = logging.getLogger(__name__)

ROOT = "smartnuggets"
ONLINE = b"online"
OFFLINE = b"offline"
ACTIONS = {"OPEN", "CLOSE", "CALIBRATE"}


@dataclass(frozen=True)
class Command:
    command_id: str
    action: str
    inside_count: int | None
    issued_at: datetime


def utc_iso(timestamp: float) -> str:
    return datetime.fromtimestamp(timestamp, UTC).isoformat().replace("+00:00", "Z")


def create_paho_client(config: UplinkConfig) -> mqtt.Client:
    client = mqtt.Client(
        CallbackAPIVersion.VERSION2,
        client_id=f"smartnuggets-{config.coop_id}",
        protocol=mqtt.MQTTv5,
    )
    if config.mqtt_username:
        client.username_pw_set(config.mqtt_username, config.mqtt_password)
    if config.mqtt_tls:
        client.tls_set(ca_certs=config.mqtt_ca_cert)
    client.reconnect_delay_set(min_delay=1, max_delay=60)
    return client


class MqttUplink:
    def __init__(
        self,
        config: UplinkConfig,
        outbox: Outbox,
        on_command: Callable[[Command], None],
        client: Any = None,
        clock: Callable[[], float] = time.time,
        publish_timeout_s: float = 10.0,
    ) -> None:
        self.config = config
        self.outbox = outbox
        self.on_command = on_command
        self.clock = clock
        self.publish_timeout_s = publish_timeout_s
        self.client = client if client is not None else create_paho_client(config)
        self._connected = False
        self._recent_commands: deque[str] = deque(maxlen=100)
        self._wakeup = threading.Event()
        self._stopping = threading.Event()
        self._sender = threading.Thread(target=self._send_loop, name="mqtt-outbox", daemon=True)

        self.client.on_connect = self._on_connect
        self.client.on_disconnect = self._on_disconnect
        self.client.on_message = self._on_message
        self.client.will_set(self.topic("status"), OFFLINE, qos=1, retain=True)

    # ------------------------------------------------------------------ cycle de vie

    def topic(self, channel: str) -> str:
        return f"{ROOT}/{self.config.coop_id}/{channel}"

    @property
    def connected(self) -> bool:
        return self._connected

    def start(self) -> None:
        """Connexion en arrière-plan ; paho se reconnecte tout seul en cas de coupure."""
        self.client.connect_async(
            self.config.mqtt_host,
            self.config.mqtt_port,
            keepalive=self.config.keepalive_s,
            clean_start=True,
        )
        self.client.loop_start()
        self._sender.start()

    def stop(self) -> None:
        """Arrêt propre : annonce "offline" (le Last Will n'est pas envoyé dans ce cas)."""
        self._stopping.set()
        self._wakeup.set()
        if self._sender.is_alive():
            self._sender.join(timeout=self.publish_timeout_s + 1)
        if self._connected:
            info = self.client.publish(self.topic("status"), OFFLINE, qos=1, retain=True)
            info.wait_for_publish(timeout=2)
        self.client.disconnect()
        self.client.loop_stop()

    # ------------------------------------------------------------------ envoi

    def send_telemetry(
        self,
        *,
        door_state: str | None = None,
        inside_count: int | None = None,
        battery_level: int | None = None,
        event: dict[str, Any] | None = None,
    ) -> None:
        payload: dict[str, Any] = {"sent_at": utc_iso(self.clock())}
        for key, value in (
            ("door_state", door_state),
            ("inside_count", inside_count),
            ("battery_level", battery_level),
            ("event", event),
        ):
            if value is not None:
                payload[key] = value
        self._enqueue("telemetry", payload)

    def send_event(
        self,
        event_type: str,
        *,
        inside_count: int | None = None,
        door_state: str | None = None,
        trigger_source: str | None = None,
        ai_confidence: float | None = None,
    ) -> None:
        """Passage de poule ou mouvement de porte, avec l'état qui en résulte."""
        event: dict[str, Any] = {"event_type": event_type, "occurred_at": utc_iso(self.clock())}
        if trigger_source is not None:
            event["trigger_source"] = trigger_source
        if ai_confidence is not None:
            event["ai_confidence"] = ai_confidence
        self.send_telemetry(door_state=door_state, inside_count=inside_count, event=event)

    def send_alert(
        self,
        alert_type: str,
        severity: str,
        *,
        ai_confidence: float | None = None,
        image: bytes | None = None,
        image_format: str = "jpeg",
    ) -> None:
        payload: dict[str, Any] = {
            "sent_at": utc_iso(self.clock()),
            "alert_type": alert_type,
            "severity": severity,
        }
        if ai_confidence is not None:
            payload["ai_confidence"] = ai_confidence
        if image is not None:
            payload["image_base64"] = base64.b64encode(image).decode("ascii")
            payload["image_format"] = image_format
        self._enqueue("alerts", payload)

    def _enqueue(self, channel: str, payload: dict[str, Any]) -> None:
        self.outbox.enqueue(self.topic(channel), json.dumps(payload).encode("utf-8"), qos=1)
        self._wakeup.set()

    def send_pending(self) -> int:
        """Envoie les messages en attente, un par un et dans l'ordre.

        Renvoie le nombre de messages confirmés par le broker. S'arrête à la première
        erreur (connexion perdue, pas d'accusé) : le message reste dans l'outbox.
        """
        sent = 0
        while self._connected and not self._stopping.is_set():
            batch = self.outbox.peek(limit=1)
            if not batch:
                break
            message = batch[0]
            info = self.client.publish(
                message.topic, message.payload, qos=message.qos, retain=message.retain
            )
            if info.rc != mqtt.MQTT_ERR_SUCCESS:
                break
            try:
                info.wait_for_publish(timeout=self.publish_timeout_s)
            except (RuntimeError, ValueError):
                break
            if not info.is_published():
                break
            self.outbox.remove(message.id)
            sent += 1
        return sent

    def _send_loop(self) -> None:
        while not self._stopping.is_set():
            self._wakeup.wait(timeout=5.0)
            self._wakeup.clear()
            try:
                self.send_pending()
            except Exception:
                logger.exception("Erreur dans le thread d'envoi MQTT")

    # ------------------------------------------------------------------ callbacks paho

    def _on_connect(self, client: Any, userdata: Any, flags: Any, reason_code: Any, props: Any):
        if reason_code.is_failure:
            logger.error("Connexion MQTT refusée : %s", reason_code)
            return
        self._connected = True
        logger.info("Connecté au broker %s", self.config.mqtt_host)
        client.subscribe(self.topic("commands"), qos=1)
        client.publish(self.topic("status"), ONLINE, qos=1, retain=True)
        self._wakeup.set()  # vide la file accumulée pendant la coupure

    def _on_disconnect(
        self, client: Any, userdata: Any, flags: Any, reason_code: Any, props: Any
    ) -> None:
        self._connected = False
        logger.warning(
            "Déconnecté du broker (%s) ; %d message(s) en attente", reason_code, len(self.outbox)
        )

    def _on_message(self, client: Any, userdata: Any, message: Any) -> None:
        if message.topic != self.topic("commands"):
            return
        command = parse_command(message.payload)
        if command is None:
            return
        age = self.clock() - command.issued_at.timestamp()
        if abs(age) > self.config.command_max_age_s:
            logger.warning("Commande %s ignorée : émise il y a %.0f s", command.action, age)
            return
        if command.command_id in self._recent_commands:
            logger.info("Commande %s déjà reçue, ignorée", command.command_id)
            return
        self._recent_commands.append(command.command_id)
        try:
            self.on_command(command)
        except Exception:
            logger.exception("Erreur lors de l'exécution de la commande %s", command.action)


def parse_command(payload: bytes) -> Command | None:
    try:
        data = json.loads(payload)
        action = data["action"]
        inside_count = data.get("inside_count")
        issued_at = datetime.fromisoformat(data["issued_at"])
        command_id = str(data["command_id"])
    except (ValueError, KeyError, TypeError):
        logger.warning("Commande illisible ignorée : %r", payload[:100])
        return None
    if issued_at.tzinfo is None:
        issued_at = issued_at.replace(tzinfo=UTC)
    if action not in ACTIONS:
        logger.warning("Action inconnue ignorée : %r", action)
        return None
    if inside_count is not None and (not isinstance(inside_count, int) or inside_count < 0):
        logger.warning("inside_count invalide ignoré : %r", inside_count)
        return None
    if action == "CALIBRATE" and inside_count is None:
        logger.warning("CALIBRATE sans inside_count ignoré")
        return None
    return Command(command_id, action, inside_count, issued_at)
