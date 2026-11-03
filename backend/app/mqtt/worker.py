"""Client MQTT du serveur : écoute les poulaillers et leur envoie les commandes.

Tourne en tâche de fond dans l'API (lifespan) et se reconnecte tout seul si le broker
redémarre. La session MQTT est persistante : les messages publiés par les Raspberry Pi
pendant un redémarrage de l'API sont conservés par le broker et livrés à la reconnexion.
"""

import asyncio
import json
import logging
import ssl
from pathlib import Path

import aiomqtt
from paho.mqtt.packettypes import PacketTypes
from paho.mqtt.properties import Properties
from pydantic import ValidationError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.config import Settings
from app.errors import ServiceUnavailableError
from app.mqtt import topics
from app.mqtt.messages import AlertMessage, TelemetryMessage, parse_status
from app.services.broadcaster import Broadcaster
from app.services.commands import DoorCommand
from app.services.ingestion import IngestionService

logger = logging.getLogger(__name__)

SESSION_EXPIRY_S = 24 * 3600
MAX_BACKOFF_S = 60.0


class MqttWorker:
    def __init__(
        self,
        settings: Settings,
        sessionmaker: async_sessionmaker[AsyncSession],
        broadcaster: Broadcaster,
    ) -> None:
        self.settings = settings
        self.sessionmaker = sessionmaker
        self.broadcaster = broadcaster
        self.client: aiomqtt.Client | None = None

    def _create_client(self) -> aiomqtt.Client:
        tls_context = None
        if self.settings.mqtt_tls:
            tls_context = ssl.create_default_context(cafile=self.settings.mqtt_ca_cert)
        properties = Properties(PacketTypes.CONNECT)
        properties.SessionExpiryInterval = SESSION_EXPIRY_S
        return aiomqtt.Client(
            hostname=self.settings.mqtt_host,
            port=self.settings.mqtt_port,
            username=self.settings.mqtt_username,
            password=self.settings.mqtt_password,
            identifier=self.settings.mqtt_client_id,
            protocol=aiomqtt.ProtocolVersion.V5,
            clean_start=False,
            properties=properties,
            tls_context=tls_context,
        )

    async def run(self) -> None:
        """Boucle infinie : connexion, abonnement, traitement des messages, reconnexion."""
        backoff = 1.0
        while True:
            try:
                async with self._create_client() as client:
                    self.client = client
                    backoff = 1.0
                    logger.info("Connecté au broker MQTT %s", self.settings.mqtt_host)
                    for channel in topics.INCOMING:
                        await client.subscribe(topics.subscription(channel), qos=1)
                    async for message in client.messages:
                        await self.handle_message(message.topic.value, message.payload)
            except aiomqtt.MqttError as exc:
                logger.warning(
                    "Broker MQTT injoignable (%s), nouvel essai dans %.0f s", exc, backoff
                )
            finally:
                self.client = None
            await asyncio.sleep(backoff)
            backoff = min(backoff * 2, MAX_BACKOFF_S)

    async def handle_message(self, topic: str, payload: object) -> None:
        """Traite un message ; une erreur ne doit jamais arrêter la boucle d'écoute."""
        parsed = topics.parse(topic)
        if parsed is None:
            logger.warning("Topic ignoré : %s", topic)
            return
        coop_id, channel = parsed
        raw = payload if isinstance(payload, bytes) else str(payload).encode()
        try:
            async with self.sessionmaker() as session:
                service = IngestionService(
                    session,
                    self.broadcaster,
                    Path(self.settings.media_dir),
                    self.settings.max_image_bytes,
                    self.settings.device_offline_after_s,
                    self.settings.low_battery_threshold,
                )
                if channel is topics.Channel.TELEMETRY:
                    await service.handle_telemetry(
                        coop_id, TelemetryMessage.model_validate_json(raw)
                    )
                elif channel is topics.Channel.ALERTS:
                    await service.handle_alert(coop_id, AlertMessage.model_validate_json(raw))
                elif channel is topics.Channel.STATUS:
                    online = parse_status(raw)
                    if online is None:
                        logger.warning("Statut inconnu reçu de %s : %r", coop_id, raw[:20])
                        return
                    await service.handle_status(coop_id, online)
        except ValidationError as exc:
            logger.warning("Message %s invalide de %s : %s", channel, coop_id, exc)
        except Exception:
            logger.exception("Erreur lors du traitement d'un message de %s", coop_id)


class MqttCommandPublisher:
    """Publie les commandes sur smartnuggets/{coop_id}/commands (QoS 1)."""

    def __init__(self, worker: MqttWorker) -> None:
        self.worker = worker

    async def publish(self, command: DoorCommand) -> None:
        client = self.worker.client
        if client is None:
            raise ServiceUnavailableError("Broker MQTT injoignable : commande non envoyée")
        try:
            await client.publish(
                topics.topic(command.coop_id, topics.Channel.COMMANDS),
                payload=json.dumps(command.to_payload()),
                qos=1,
            )
        except aiomqtt.MqttError as exc:
            raise ServiceUnavailableError("Échec de l'envoi de la commande au broker MQTT") from exc
