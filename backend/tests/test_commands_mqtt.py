import json

from fastapi import FastAPI
from httpx import AsyncClient

from app.models import Coop
from app.mqtt.worker import MqttCommandPublisher, MqttWorker


class FakeMqttClient:
    def __init__(self) -> None:
        self.published: list[tuple[str, str, int]] = []

    async def publish(self, topic: str, payload: str, qos: int) -> None:
        self.published.append((topic, payload, qos))


def install_mqtt_publisher(app: FastAPI) -> MqttWorker:
    worker = MqttWorker(app.state.settings, app.state.sessionmaker, app.state.broadcaster)
    app.state.command_publisher = MqttCommandPublisher(worker)
    return worker


async def test_commande_publiee_sur_le_topic_du_poulailler(
    app: FastAPI, client: AsyncClient, coop: Coop
) -> None:
    worker = install_mqtt_publisher(app)
    fake = FakeMqttClient()
    worker.client = fake  # type: ignore[assignment]

    response = await client.post(
        "/api/v1/coops/coop_01/command", json={"action": "CALIBRATE", "inside_count": 9}
    )

    assert response.status_code == 202
    topic, payload, qos = fake.published[0]
    assert topic == "smartnuggets/coop_01/commands"
    assert qos == 1
    body = json.loads(payload)
    assert body["action"] == "CALIBRATE"
    assert body["inside_count"] == 9
    assert body["command_id"] == response.json()["command_id"]
    assert "issued_at" in body


async def test_commande_refusee_si_broker_injoignable(
    app: FastAPI, client: AsyncClient, coop: Coop
) -> None:
    install_mqtt_publisher(app)

    response = await client.post("/api/v1/coops/coop_01/command", json={"action": "OPEN"})

    assert response.status_code == 503
