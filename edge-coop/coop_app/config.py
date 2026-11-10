"""Configuration du programme du poulailler, lue dans les variables d'environnement.

Toutes les valeurs ont un défaut raisonnable ; voir `.env.example`. Les secrets MQTT sont
lus par `mqtt_uplink.UplinkConfig`, pas ici.
"""

import os
from collections.abc import Mapping
from dataclasses import dataclass

from door_controller import DoorConfig, Schedule


def _pins(value: str) -> tuple[int, ...]:
    return tuple(int(pin) for pin in value.split(","))


@dataclass(frozen=True)
class AppConfig:
    hardware: str = "mock"  # "mock" (PC) ou "pi" (Raspberry Pi 5)
    camera: str = "mock"  # "mock", "pi", "video:<fichier>" ou "folder:<dossier>"
    detector: str = "scripted"  # "scripted" ou "module:Classe"
    door: DoorConfig = DoorConfig()
    step_delay_s: float = 0.0015
    schedule: Schedule = Schedule()
    hen_threshold: float = 0.7
    predator_threshold: float = 0.5
    predator_lock_s: float = 300.0  # porte verrouillée après un prédateur
    auto_close_after_s: float = 60.0  # refermer quand plus aucune poule ne passe
    obstacle_retry_s: float = 10.0  # attente avant de réessayer de fermer (x1, x2, x3 puis fixe)
    obstacle_max_attempts: int = 3  # fermetures empêchées d'affilée avant l'alerte à l'éleveur
    heartbeat_s: float = 60.0
    poll_s: float = 0.05  # lecture des capteurs (20 fois par seconde)
    motor_pins: tuple[int, ...] = (5, 6, 13, 19)
    top_pin: int = 23
    bottom_pin: int = 24
    beam_outer_pin: int = 27
    beam_inner_pin: int = 22
    motion_pin: int = 17
    inside_at_start: int = 0

    @classmethod
    def from_env(cls, env: Mapping[str, str] | None = None) -> "AppConfig":
        env = os.environ if env is None else env

        def get(name: str, default: object) -> str:
            return env.get(name, str(default))

        d = cls()
        return cls(
            hardware=get("HARDWARE", d.hardware),
            camera=get("CAMERA", d.camera),
            detector=get("DETECTOR", d.detector),
            door=DoorConfig(
                travel_steps=int(get("DOOR_TRAVEL_STEPS", d.door.travel_steps)),
                margin_steps=int(get("DOOR_MARGIN_STEPS", d.door.margin_steps)),
                check_every=int(get("DOOR_CHECK_EVERY", d.door.check_every)),
            ),
            step_delay_s=float(get("STEP_DELAY_S", d.step_delay_s)),
            schedule=Schedule.parse(get("OPEN_FROM", "07:00"), get("CLOSE_AT", "21:00")),
            hen_threshold=float(get("HEN_THRESHOLD", d.hen_threshold)),
            predator_threshold=float(get("PREDATOR_THRESHOLD", d.predator_threshold)),
            predator_lock_s=float(get("PREDATOR_LOCK_S", d.predator_lock_s)),
            auto_close_after_s=float(get("AUTO_CLOSE_AFTER_S", d.auto_close_after_s)),
            obstacle_retry_s=float(get("OBSTACLE_RETRY_S", d.obstacle_retry_s)),
            obstacle_max_attempts=int(get("OBSTACLE_MAX_ATTEMPTS", d.obstacle_max_attempts)),
            heartbeat_s=float(get("HEARTBEAT_S", d.heartbeat_s)),
            motor_pins=_pins(get("MOTOR_PINS", "5,6,13,19")),
            top_pin=int(get("TOP_PIN", d.top_pin)),
            bottom_pin=int(get("BOTTOM_PIN", d.bottom_pin)),
            beam_outer_pin=int(get("BEAM_OUTER_PIN", d.beam_outer_pin)),
            beam_inner_pin=int(get("BEAM_INNER_PIN", d.beam_inner_pin)),
            motion_pin=int(get("MOTION_PIN", d.motion_pin)),
            inside_at_start=int(get("INSIDE_AT_START", d.inside_at_start)),
        )
