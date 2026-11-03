import json
from collections.abc import Iterator
from dataclasses import dataclass, field
from typing import Any

import pytest
from paho.mqtt.client import MQTT_ERR_NO_CONN, MQTT_ERR_SUCCESS
from paho.mqtt.packettypes import PacketTypes
from paho.mqtt.reasoncodes import ReasonCode

from mqtt_uplink import MqttUplink, Outbox, UplinkConfig
from mqtt_uplink.client import Command

NOW = 1_793_692_800.0  # 2026-11-03T08:00:00Z


@dataclass
class FakeInfo:
    rc: int
    mid: int
    acked: bool

    def wait_for_publish(self, timeout: float | None = None) -> None:
        return None

    def is_published(self) -> bool:
        return self.acked


@dataclass
class FakeMessage:
    topic: str
    payload: bytes


@dataclass
class FakePahoClient:
    """Imite paho.mqtt.Client : enregistre les publications au lieu de les envoyer."""

    online: bool = True
    ack: bool = True
    published: list[tuple[str, bytes, int, bool]] = field(default_factory=list)
    subscriptions: list[str] = field(default_factory=list)
    will: tuple[str, bytes, int, bool] | None = None
    on_connect: Any = None
    on_disconnect: Any = None
    on_message: Any = None

    def will_set(self, topic: str, payload: bytes, qos: int, retain: bool) -> None:
        self.will = (topic, payload, qos, retain)

    def publish(self, topic: str, payload: bytes, qos: int = 0, retain: bool = False) -> FakeInfo:
        if not self.online:
            return FakeInfo(MQTT_ERR_NO_CONN, 0, False)
        self.published.append((topic, payload, qos, retain))
        return FakeInfo(MQTT_ERR_SUCCESS, len(self.published), self.ack)

    def subscribe(self, topic: str, qos: int = 0) -> None:
        self.subscriptions.append(topic)

    # Simulation des événements réseau
    def connect(self) -> None:
        self.online = True
        self.on_connect(self, None, None, ReasonCode(PacketTypes.CONNACK, "Success"), None)

    def drop(self) -> None:
        self.online = False
        reason = ReasonCode(PacketTypes.DISCONNECT, "Unspecified error")
        self.on_disconnect(self, None, None, reason, None)

    def receive(self, topic: str, payload: dict[str, Any] | bytes) -> None:
        raw = payload if isinstance(payload, bytes) else json.dumps(payload).encode()
        self.on_message(self, None, FakeMessage(topic, raw))

    def payloads(self, channel: str) -> list[Any]:
        return [
            json.loads(payload)
            for topic, payload, _, _ in self.published
            if topic.endswith("/" + channel)
        ]


@pytest.fixture
def outbox(tmp_path) -> Iterator[Outbox]:
    box = Outbox(str(tmp_path / "outbox.db"))
    yield box
    box.close()


@pytest.fixture
def config() -> UplinkConfig:
    return UplinkConfig(coop_id="coop_01", mqtt_host="broker.test")


@pytest.fixture
def fake_client() -> FakePahoClient:
    return FakePahoClient(online=False)


@pytest.fixture
def received() -> list[Command]:
    return []


@pytest.fixture
def uplink(config, outbox, fake_client, received) -> MqttUplink:
    return MqttUplink(config, outbox, received.append, client=fake_client, clock=lambda: NOW)
