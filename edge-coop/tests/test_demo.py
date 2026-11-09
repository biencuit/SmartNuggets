"""Bout en bout : le scénario de la démo, rejoué en accéléré sur le vrai programme du Pi."""

from dataclasses import replace
from datetime import datetime
from pathlib import Path

import pytest

from ai_detector import ScriptedDetector
from coop_app.app import CoopApp
from coop_app.config import AppConfig
from coop_app.controller import CoopController
from coop_app.demo import DemoScenario, Step, load_scenario
from coop_app.devices import build_devices
from door_controller import DoorConfig, DoorState
from tests.test_controller import FakeUplink

SCENARIO = Path(__file__).parent.parent / "scenarios" / "journee.json"


def test_scenario_de_la_demo_de_bout_en_bout():
    config = replace(
        AppConfig(),
        door=DoorConfig(travel_steps=40, margin_steps=10),
        predator_lock_s=20,
        auto_close_after_s=1000,
        inside_at_start=10,
        poll_s=0.05,
    )
    t = [0.0]
    devices = build_devices(config)
    detector = ScriptedDetector()
    uplink = FakeUplink()
    said: list[str] = []
    scenario = DemoScenario(
        load_scenario(SCENARIO),
        devices,
        detector,
        clock=lambda: t[0],
        close_at=config.schedule.close_at,
        real_now=lambda: datetime(2026, 11, 26, 9, 0).astimezone(),
        say=said.append,
    )
    controller = CoopController(config, devices, detector, uplink, lambda: t[0], scenario.now)
    app = CoopApp(controller, config.poll_s, sleep=lambda s: t.__setitem__(0, t[0] + s))

    app.run(until=lambda: scenario.finished and t[0] > 95, before_step=scenario.update)

    assert uplink.events() == [
        "DOOR_OPEN",  # poule le matin
        *["HEN_EXIT"] * 4,
        "DOOR_CLOSE",  # renard
        "DOOR_OPEN",  # poule après le verrou
        *["HEN_ENTRY"] * 3,
        "DOOR_CLOSE",  # soir
    ]
    assert uplink.alerts() == ["PREDATOR_DETECTED"]
    closes = [f for kind, name, f in uplink.sent if name == "DOOR_CLOSE"]
    assert [c["trigger_source"] for c in closes] == ["FAILSAFE", "SCHEDULE"]
    assert closes[-1]["inside_count"] == 9  # une poule dehors : le serveur en fera une alerte
    assert controller.door.state == DoorState.CLOSED
    assert len(said) == 7


def test_action_inconnue_refusee():
    with pytest.raises(ValueError, match="Action inconnue"):
        Step(at=1, do="danser")
