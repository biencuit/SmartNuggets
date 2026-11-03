import base64
from datetime import UTC, datetime, timedelta

from mqtt_uplink import MqttUplink, Outbox, UplinkConfig
from mqtt_uplink.client import Command, parse_command

from .conftest import NOW, FakePahoClient

COMMANDS = "smartnuggets/coop_01/commands"


def command(action: str = "OPEN", age_s: float = 0, command_id: str = "c1", **extra) -> dict:
    issued_at = datetime.fromtimestamp(NOW, UTC) - timedelta(seconds=age_s)
    return {"command_id": command_id, "action": action, "issued_at": issued_at.isoformat(), **extra}


def test_last_will_offline(uplink: MqttUplink, fake_client: FakePahoClient) -> None:
    assert fake_client.will == ("smartnuggets/coop_01/status", b"offline", 1, True)


def test_connexion_annonce_online_et_s_abonne_aux_commandes(
    uplink: MqttUplink, fake_client: FakePahoClient
) -> None:
    fake_client.connect()

    assert uplink.connected
    assert fake_client.subscriptions == [COMMANDS]
    assert fake_client.published[0] == ("smartnuggets/coop_01/status", b"online", 1, True)


def test_messages_gardes_pendant_une_coupure_puis_envoyes_dans_l_ordre(
    uplink: MqttUplink, fake_client: FakePahoClient, outbox: Outbox
) -> None:
    uplink.send_event("HEN_EXIT", inside_count=9, trigger_source="AI_AUTO", ai_confidence=0.9)
    uplink.send_telemetry(battery_level=80, camera_ok=True)
    assert uplink.send_pending() == 0
    assert len(outbox) == 2

    fake_client.connect()
    assert uplink.send_pending() == 2

    telemetry = fake_client.payloads("telemetry")
    assert telemetry[0]["inside_count"] == 9
    assert telemetry[0]["event"] == {
        "event_type": "HEN_EXIT",
        "occurred_at": "2026-11-03T08:00:00Z",
        "trigger_source": "AI_AUTO",
        "ai_confidence": 0.9,
    }
    assert telemetry[1] == {
        "sent_at": "2026-11-03T08:00:00Z",
        "battery_level": 80,
        "camera_ok": True,
    }
    assert len(outbox) == 0


def test_message_sans_accuse_reste_dans_la_file(
    uplink: MqttUplink, fake_client: FakePahoClient, outbox: Outbox
) -> None:
    fake_client.connect()
    fake_client.ack = False
    uplink.send_telemetry(inside_count=3)

    assert uplink.send_pending() == 0
    assert len(outbox) == 1

    fake_client.drop()
    assert not uplink.connected
    fake_client.ack = True
    fake_client.connect()
    assert uplink.send_pending() == 1
    assert len(outbox) == 0


def test_alerte_avec_photo(uplink: MqttUplink, fake_client: FakePahoClient) -> None:
    fake_client.connect()
    uplink.send_alert("PREDATOR_DETECTED", "CRITICAL", ai_confidence=0.8, image=b"\xff\xd8\xff")
    uplink.send_pending()

    alert = fake_client.payloads("alerts")[0]
    assert alert["alert_type"] == "PREDATOR_DETECTED"
    assert base64.b64decode(alert["image_base64"]) == b"\xff\xd8\xff"
    assert alert["image_format"] == "jpeg"


def test_commande_recente_executee(
    uplink: MqttUplink, fake_client: FakePahoClient, received: list[Command]
) -> None:
    fake_client.connect()
    fake_client.receive(COMMANDS, command("OPEN", age_s=5))

    assert [c.action for c in received] == ["OPEN"]


def test_commande_trop_vieille_ignoree(
    uplink: MqttUplink, fake_client: FakePahoClient, received: list[Command]
) -> None:
    fake_client.connect()
    fake_client.receive(COMMANDS, command("OPEN", age_s=3600))
    fake_client.receive(COMMANDS, command("OPEN", age_s=-3600, command_id="futur"))

    assert received == []


def test_commande_en_double_executee_une_seule_fois(
    uplink: MqttUplink, fake_client: FakePahoClient, received: list[Command]
) -> None:
    fake_client.connect()
    fake_client.receive(COMMANDS, command("CLOSE"))
    fake_client.receive(COMMANDS, command("CLOSE"))

    assert len(received) == 1


def test_erreur_du_callback_ne_casse_pas_le_client(
    config: UplinkConfig, outbox: Outbox, fake_client: FakePahoClient
) -> None:
    def boom(_: Command) -> None:
        raise RuntimeError("moteur bloqué")

    uplink = MqttUplink(config, outbox, boom, client=fake_client, clock=lambda: NOW)
    fake_client.connect()
    fake_client.receive(COMMANDS, command("OPEN"))  # ne lève pas d'exception
    assert uplink.connected


def test_parse_command_refuse_les_commandes_invalides() -> None:
    issued = "2026-11-03T08:00:00Z"
    assert parse_command(b"pas du json") is None
    assert parse_command(b'{"action": "OPEN"}') is None
    assert (
        parse_command(b'{"command_id": "1", "action": "BOOM", "issued_at": "%s"}' % issued.encode())
        is None
    )
    calibrate = {"command_id": "1", "action": "CALIBRATE", "issued_at": issued}
    assert parse_command(str(calibrate).replace("'", '"').encode()) is None
    ok = parse_command(
        b'{"command_id": "1", "action": "CALIBRATE", "inside_count": 4, "issued_at": "%s"}'
        % issued.encode()
    )
    assert ok is not None
    assert ok.inside_count == 4
    assert ok.issued_at == datetime(2026, 11, 3, 8, tzinfo=UTC)


def test_config_depuis_l_environnement() -> None:
    config = UplinkConfig.from_env(
        {"COOP_ID": "coop_02", "MQTT_HOST": "vps.example", "MQTT_TLS": "false", "MQTT_CA_CERT": ""}
    )
    assert config.coop_id == "coop_02"
    assert config.mqtt_port == 8883
    assert config.mqtt_tls is False
    assert config.mqtt_ca_cert is None
