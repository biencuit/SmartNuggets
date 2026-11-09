"""Intégration : capteurs simulés + détection simulée + porte + messages vers le serveur."""

from dataclasses import dataclass, field, replace
from datetime import datetime
from typing import Any

import pytest

from ai_detector import Label, ScriptedDetector
from coop_app.app import CoopApp
from coop_app.config import AppConfig
from coop_app.controller import CoopController
from coop_app.devices import build_devices
from door_controller import DoorConfig, DoorState
from mqtt_uplink.client import Command

DAY = datetime(2026, 11, 10, 10, 0)
NIGHT = datetime(2026, 11, 10, 22, 0)


@dataclass
class FakeUplink:
    sent: list[tuple[str, str, dict[str, Any]]] = field(default_factory=list)

    def send_telemetry(self, **fields):
        self.sent.append(("telemetry", "", fields))

    def send_event(self, event_type, **fields):
        self.sent.append(("event", event_type, fields))

    def send_alert(self, alert_type, severity, **fields):
        self.sent.append(("alert", alert_type, {"severity": severity, **fields}))

    def events(self):
        return [name for kind, name, _ in self.sent if kind == "event"]

    def alerts(self):
        return [name for kind, name, _ in self.sent if kind == "alert"]


class Clock:
    def __init__(self) -> None:
        self.t = 1000.0
        self.now = DAY

    def __call__(self) -> float:
        return self.t


@pytest.fixture
def env():
    config = replace(
        AppConfig(),
        door=DoorConfig(travel_steps=50, margin_steps=10),
        auto_close_after_s=30,
        predator_lock_s=300,
        inside_at_start=4,
    )
    devices = build_devices(config)
    detector = ScriptedDetector()
    uplink = FakeUplink()
    clock = Clock()
    controller = CoopController(config, devices, detector, uplink, clock, lambda: clock.now)
    controller.start()
    uplink.sent.clear()
    return controller, devices, detector, uplink, clock


def mouvement(controller, devices):
    devices.motion.active = True
    controller.poll()
    devices.motion.active = False
    controller.poll()


def passage(controller, devices, entree=True):
    etapes = [(1, 0), (1, 1), (0, 1), (0, 0)]
    if not entree:
        etapes = [(b, a) for a, b in etapes]
    for outer, inner in etapes:
        devices.beam_outer.active, devices.beam_inner.active = bool(outer), bool(inner)
        controller.poll()


def test_une_poule_devant_la_porte_l_ouvre(env):
    controller, devices, detector, uplink, _ = env
    detector.show(Label.HEN, 0.92)
    mouvement(controller, devices)
    assert controller.door.state == DoorState.OPEN
    kind, name, fields = [s for s in uplink.sent if s[0] == "event"][0]
    assert name == "DOOR_OPEN"
    assert fields["trigger_source"] == "AI_AUTO" and fields["ai_confidence"] == 0.92


def test_confiance_trop_basse_ou_autre_chose_la_porte_reste_fermee(env):
    controller, devices, detector, uplink, _ = env
    detector.show(Label.HEN, 0.4)
    mouvement(controller, devices)
    detector.show(Label.OTHER, 0.99)
    mouvement(controller, devices)
    assert controller.door.state == DoorState.CLOSED
    assert uplink.events() == []


def test_passages_comptes_puis_refermeture_automatique(env):
    controller, devices, detector, uplink, clock = env
    detector.show(Label.HEN, 0.9)
    mouvement(controller, devices)
    passage(controller, devices, entree=False)
    passage(controller, devices, entree=False)
    assert controller.counter.inside == 2
    clock.t += 29
    controller.tick()
    assert controller.door.state == DoorState.OPEN
    clock.t += 2
    controller.tick()
    assert controller.door.state == DoorState.CLOSED
    assert uplink.events() == ["DOOR_OPEN", "HEN_EXIT", "HEN_EXIT", "DOOR_CLOSE"]


def test_predateur_alerte_avec_photo_et_porte_verrouillee(env):
    controller, devices, detector, uplink, clock = env
    detector.show(Label.HEN, 0.9)
    mouvement(controller, devices)
    detector.show(Label.PREDATOR, 0.8, "renard")
    mouvement(controller, devices)
    assert controller.door.state == DoorState.CLOSED
    alert = [s for s in uplink.sent if s[0] == "alert"][0]
    assert alert[1] == "PREDATOR_DETECTED" and alert[2]["image"].startswith(b"\xff\xd8")
    # Ni une poule, ni l'application ne rouvrent la porte pendant le verrouillage.
    detector.show(Label.HEN, 0.99)
    mouvement(controller, devices)
    controller.on_command("OPEN")
    assert controller.door.state == DoorState.CLOSED
    clock.t += 301
    controller.on_command("OPEN")
    assert controller.door.state == DoorState.OPEN


def test_la_nuit_la_porte_se_ferme_et_ne_s_ouvre_plus_seule(env):
    controller, devices, detector, uplink, clock = env
    controller.on_command("OPEN")
    clock.now = NIGHT
    controller.tick()
    assert controller.door.state == DoorState.CLOSED
    assert uplink.sent[-1][2]["trigger_source"] == "SCHEDULE"
    detector.show(Label.HEN, 0.95)
    mouvement(controller, devices)
    assert controller.door.state == DoorState.CLOSED
    controller.on_command("OPEN")  # l'éleveur peut toujours ouvrir à la main
    assert controller.door.state == DoorState.OPEN


def test_commandes_de_l_application(env):
    controller, _, _, uplink, _ = env
    controller.on_command("OPEN")
    controller.on_command("CLOSE")
    controller.on_command("CALIBRATE", inside_count=9)
    assert [f.get("trigger_source") for k, _, f in uplink.sent if k == "event"] == [
        "MANUAL_APP",
        "MANUAL_APP",
    ]
    assert controller.counter.inside == 9
    assert uplink.sent[-1] == (
        "telemetry",
        "",
        {"door_state": "CLOSED", "inside_count": 9, "camera_ok": True},
    )


def test_porte_bloquee_alerte(env):
    controller, devices, _, uplink, _ = env
    devices.top.stuck = True
    controller.on_command("OPEN")
    assert controller.door.state == DoorState.ERROR
    assert uplink.alerts() == ["DOOR_BLOCKED"]
    controller.on_command("OPEN")  # plus d'ouverture tant qu'elle est en erreur
    assert controller.door.state == DoorState.ERROR


def test_obstacle_a_la_fermeture(env):
    controller, devices, _, uplink, _ = env
    controller.on_command("OPEN")
    devices.beam_inner.active = True
    controller.on_command("CLOSE")
    assert controller.door.state == DoorState.OPEN
    assert uplink.events()[-1] == "OBSTACLE"


def test_camera_en_panne_signalee(env):
    controller, devices, _, uplink, _ = env
    devices.camera.broken = True
    mouvement(controller, devices)
    assert uplink.sent[-1] == (
        "telemetry",
        "",
        {"door_state": "CLOSED", "inside_count": 4, "camera_ok": False},
    )


def test_battement_de_coeur_regulier(env):
    controller, _, _, uplink, clock = env
    controller.tick()
    assert uplink.sent == []
    clock.t += 60
    controller.tick()
    assert uplink.sent[-1][0] == "telemetry"


def test_les_commandes_mqtt_passent_par_la_boucle_principale(env):
    controller = env[0]
    app = CoopApp(controller, poll_s=0, sleep=lambda s: None)
    app.submit(Command("c1", "OPEN", None, DAY))
    assert controller.door.state == DoorState.CLOSED  # rien tant que la boucle n'a pas tourné
    app.step()
    assert controller.door.state == DoorState.OPEN
    turns = iter(range(3))
    app.run(until=lambda: next(turns, None) is None)


def test_configuration_depuis_l_environnement():
    config = AppConfig.from_env(
        {"HARDWARE": "pi", "MOTOR_PINS": "1,2,3,4", "CLOSE_AT": "20:30", "HEN_THRESHOLD": "0.8"}
    )
    assert config.hardware == "pi" and config.motor_pins == (1, 2, 3, 4)
    assert config.schedule.close_at.hour == 20 and config.hen_threshold == 0.8
    with pytest.raises(ValueError):
        build_devices(replace(config, hardware="arduino"))
