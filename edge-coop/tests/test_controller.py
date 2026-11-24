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
from mqtt_uplink.client import Command, ScheduleDay

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


def test_ouverture_forcee_depuis_l_application_malgre_le_predateur(env):
    controller, devices, detector, uplink, clock = env
    detector.show(Label.PREDATOR, 0.8, "renard")
    mouvement(controller, devices)
    clock.t += 5
    controller.on_command("OPEN")  # refusée : verrouillage
    assert controller.door.state == DoorState.CLOSED
    controller.on_command("OPEN", force=True)  # « Ouvrir quand même »
    assert controller.door.state == DoorState.OPEN
    assert not controller.predator_locked()


def test_duree_de_verrouillage_reglee_dans_l_application(env):
    controller, devices, detector, uplink, clock = env
    controller.set_predator_lock_s(10)
    detector.show(Label.PREDATOR, 0.8, "renard")
    mouvement(controller, devices)
    clock.t += 9
    assert controller.predator_locked()
    clock.t += 2
    assert not controller.predator_locked()
    detector.show(Label.HEN, 0.9)
    mouvement(controller, devices)
    assert controller.door.state == DoorState.OPEN


def test_raccourcir_le_verrouillage_en_cours(env):
    controller, devices, detector, uplink, clock = env
    detector.show(Label.PREDATOR, 0.8, "renard")
    mouvement(controller, devices)  # 300 s par défaut dans ce test
    clock.t += 20
    controller.set_predator_lock_s(15)  # le nouveau réglage s'applique tout de suite
    assert not controller.predator_locked()


def predator_alert(uplink):
    return next(fields for kind, name, fields in uplink.sent if name == "PREDATOR_DETECTED")


def test_predateur_photo_lourde_reduite_avant_l_envoi(env):
    from tests.test_photo import big_jpeg

    controller, devices, detector, uplink, clock = env
    devices.camera.jpeg = big_jpeg()
    detector.show(Label.PREDATOR, 0.9, "renard")
    mouvement(controller, devices)
    photo = predator_alert(uplink)["image"]
    assert len(photo) <= 200_000 and photo.startswith(b"\xff\xd8")


def test_predateur_photo_illisible_l_alerte_part_quand_meme(env):
    controller, devices, detector, uplink, clock = env
    detector.show(Label.HEN, 0.9)
    mouvement(controller, devices)
    devices.camera.jpeg = b"image abimee"
    detector.show(Label.PREDATOR, 0.8, "renard")
    mouvement(controller, devices)
    assert predator_alert(uplink)["image"] is None
    assert controller.door.state == DoorState.CLOSED


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


def late_hen_alerts(uplink):
    return [f for kind, name, f in uplink.sent if kind == "alert" and name == "HEN_AFTER_CLOSING"]


def test_poule_vue_apres_la_fermeture_alerte_avec_photo_porte_fermee(env):
    controller, devices, detector, uplink, clock = env
    clock.now = NIGHT
    detector.show(Label.HEN, 0.9)
    mouvement(controller, devices)
    assert controller.door.state == DoorState.CLOSED
    assert uplink.events() == []
    (alert,) = late_hen_alerts(uplink)
    assert alert["severity"] == "CRITICAL" and alert["ai_confidence"] == 0.9
    assert alert["image"].startswith(b"\xff\xd8")


def test_poule_apres_la_fermeture_une_alerte_par_minute_au_plus(env):
    controller, devices, detector, uplink, clock = env
    clock.now = NIGHT
    for _ in range(3):  # trois images à la suite : une seule alerte
        detector.show(Label.HEN, 0.9)
        mouvement(controller, devices)
    clock.t += 59
    detector.show(Label.HEN, 0.9)
    mouvement(controller, devices)
    assert len(late_hen_alerts(uplink)) == 1
    clock.t += 2
    detector.show(Label.HEN, 0.9)
    mouvement(controller, devices)
    assert len(late_hen_alerts(uplink)) == 2


def test_poule_de_jour_ou_confiance_trop_basse_pas_d_alerte_de_fermeture(env):
    controller, devices, detector, uplink, clock = env
    detector.show(Label.HEN, 0.9)
    mouvement(controller, devices)  # de jour : la porte s'ouvre, pas d'alerte
    clock.now = NIGHT
    controller.tick()
    detector.show(Label.HEN, 0.4)
    mouvement(controller, devices)  # sous le seuil HEN_THRESHOLD : ignoré
    assert late_hen_alerts(uplink) == []


def test_planning_de_l_application_declenche_l_alerte(env):
    """Planning reçu du serveur (#70) qui ferme à 14h : une poule à 14h30 donne l'alerte."""
    controller, devices, detector, uplink, clock = env
    controller.on_schedule(
        [ScheduleDay(weekday=day, open_from="07:00", close_at="14:00") for day in range(7)]
    )
    clock.now = datetime(2026, 11, 10, 14, 30)
    detector.show(Label.HEN, 0.9)
    mouvement(controller, devices)
    assert controller.door.state == DoorState.CLOSED
    assert len(late_hen_alerts(uplink)) == 1


def test_on_schedule_remplace_l_horaire_d_un_jour_precis(env):
    """Planning reçu du serveur (#70) : un samedi peut fermer plus tard qu'un mardi."""
    controller, devices, detector, uplink, clock = env
    saturday_evening = datetime(2026, 11, 14, 22, 0)  # samedi, horaire par défaut : nuit

    controller.on_command("OPEN")
    clock.now = saturday_evening
    controller.tick()
    assert controller.door.state == DoorState.CLOSED  # horaire fixe (21h) : encore en vigueur

    controller.on_command("OPEN")
    controller.on_schedule(
        [
            ScheduleDay(weekday=day, open_from="07:00", close_at="22:30" if day == 5 else "21:00")
            for day in range(7)
        ]
    )
    controller.tick()
    assert controller.door.state == DoorState.OPEN  # samedi (jour 5) : encore jour jusqu'à 22h30

    detector.show(Label.HEN, 0.95)
    clock.now = NIGHT  # mardi (jour 1), resté à 21h dans le nouveau planning
    controller.tick()
    assert controller.door.state == DoorState.CLOSED
    mouvement(controller, devices)
    assert controller.door.state == DoorState.CLOSED  # ne s'ouvre pas seule hors plage


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


def test_le_planning_mqtt_passe_par_la_boucle_principale(env):
    controller = env[0]
    app = CoopApp(controller, poll_s=0, sleep=lambda s: None)
    app.submit_schedule(
        [ScheduleDay(weekday=d, open_from="00:00", close_at="23:59") for d in range(7)]
    )
    assert controller._weekly_schedule[0].close_at.hour == 21  # rien avant le tour de boucle
    app.step()
    assert controller._weekly_schedule[0].close_at.hour == 23


def test_configuration_depuis_l_environnement():
    config = AppConfig.from_env(
        {
            "HARDWARE": "pi",
            "MOTOR_PINS": "1,2,3,4",
            "CLOSE_AT": "20:30",
            "HEN_THRESHOLD": "0.8",
            "PHOTO_MAX_BYTES": "150000",
        }
    )
    assert config.hardware == "pi" and config.motor_pins == (1, 2, 3, 4)
    assert config.photo_max_bytes == 150_000
    assert config.schedule.close_at.hour == 20 and config.hen_threshold == 0.8
    with pytest.raises(ValueError):
        build_devices(replace(config, hardware="arduino"))
