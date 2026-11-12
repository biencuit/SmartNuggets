"""Le cerveau du poulailler : relie capteurs, détection, porte et serveur.

Règles (dans l'ordre de priorité) :
1. Prédateur vu → la porte se ferme si elle est ouverte, et refuse de s'ouvrir pendant
   `predator_lock_s`, même sur commande de l'application. Alerte avec photo, réduite
   à moins de 200 Ko (`coop_app.photo`). (#22, #23)
2. Nuit (hors de la plage horaire) → la porte se ferme et ne s'ouvre plus seule. (#14)
3. Poule vue devant la porte, de jour → la porte s'ouvre ; elle se referme quand plus
   aucune poule n'est passée depuis `auto_close_after_s`. (#10)
4. Commandes de l'application : OPEN, CLOSE, CALIBRATE (correction du compteur). (#13)
5. Chaque passage entre les barrières IR met à jour le compteur. (#16, #17)

Tout est appelé depuis un seul thread (`CoopApp.run`) : pas de verrou nécessaire.
"""

import logging
from collections.abc import Callable
from datetime import datetime
from typing import Any, Protocol

from ai_detector import Detector, Label, best
from coop_app.config import AppConfig
from coop_app.devices import Devices
from coop_app.photo import reduce_jpeg
from door_controller import Door, DoorState, MoveResult, Passage, PassageCounter, Source
from hardware.interfaces import Switch

logger = logging.getLogger(__name__)


class Uplink(Protocol):
    """Ce que le contrôleur utilise de `mqtt_uplink.MqttUplink`."""

    def send_telemetry(self, **fields: Any) -> None: ...

    def send_event(self, event_type: str, **fields: Any) -> None: ...

    def send_alert(self, alert_type: str, severity: str, **fields: Any) -> None: ...


class AnySwitch(Switch):
    """Actif dès qu'un des contacts l'est (les deux barrières servent d'anti-pincement)."""

    def __init__(self, *switches: Switch) -> None:
        self._switches = switches

    @property
    def active(self) -> bool:
        return any(switch.active for switch in self._switches)


class CoopController:
    def __init__(
        self,
        config: AppConfig,
        devices: Devices,
        detector: Detector,
        uplink: Uplink,
        clock: Callable[[], float],
        now: Callable[[], datetime],
    ) -> None:
        self.config = config
        self.devices = devices
        self.detector = detector
        self.uplink = uplink
        self.clock = clock  # secondes, monotone (délais)
        self.now = now  # heure locale (plage horaire)
        self.counter = PassageCounter(config.inside_at_start, on_passage=self._on_passage)
        self.door = Door(
            devices.motor,
            config.door,
            top=devices.top,
            bottom=devices.bottom,
            obstacle=AnySwitch(devices.beam_outer, devices.beam_inner),
            on_change=self._on_door_change,
        )
        self.camera_ok = True
        self._predator_until = 0.0
        self._opened_for_hen_at: float | None = None
        self._last_activity = 0.0
        self._last_heartbeat: float | None = None
        self._motion_before = False

    # ------------------------------------------------------------------ boucle

    def poll(self) -> None:
        """Lit les capteurs et applique les règles. Appelé `1 / poll_s` fois par seconde."""
        self.counter.update(self.devices.beam_outer.active, self.devices.beam_inner.active)
        motion = self.devices.motion.active
        if motion and not self._motion_before:
            self.on_motion()
        self._motion_before = motion
        self.tick()

    def tick(self) -> None:
        t = self.clock()
        night = not self.config.schedule.is_day(self.now())
        if night and self.door.state != DoorState.CLOSED and not self._door_in_error():
            logger.info("Fin de journée : fermeture de la porte")
            self._close(Source.SCHEDULE)
        elif (
            self._opened_for_hen_at is not None
            and self.door.state == DoorState.OPEN
            and t - self._last_activity >= self.config.auto_close_after_s
        ):
            logger.info("Plus de passage depuis %.0f s : fermeture", t - self._last_activity)
            self._close(Source.AI_AUTO)
        if self._last_heartbeat is None or t - self._last_heartbeat >= self.config.heartbeat_s:
            self.heartbeat()

    def heartbeat(self) -> None:
        self._last_heartbeat = self.clock()
        self.uplink.send_telemetry(
            door_state=str(self.door.state),
            inside_count=self.counter.inside,
            camera_ok=self.camera_ok,
        )

    def start(self) -> None:
        """Au démarrage : recaler la porte (position inconnue) et annoncer l'état."""
        if self.door.calibrate() == MoveResult.BLOCKED:
            self._alert_blocked()
        self.heartbeat()

    # ------------------------------------------------------------------ détection

    def on_motion(self) -> None:
        """Le PIR a vu un mouvement : on regarde ce que c'est."""
        self._last_activity = self.clock()
        frame = self.devices.camera.capture()
        if frame is None:
            if self.camera_ok:
                logger.error("Caméra en panne")
                self.camera_ok = False
                self.heartbeat()
            return
        if not self.camera_ok:
            self.camera_ok = True
            self.heartbeat()
        detections = self.detector.detect(frame)
        predator = best(detections, Label.PREDATOR, self.config.predator_threshold)
        if predator is not None:
            self._on_predator(predator.confidence, frame.jpeg, predator.name)
            return
        hen = best(detections, Label.HEN, self.config.hen_threshold)
        if hen is None:
            return
        if self.door.state == DoorState.CLOSED and self._may_open(Source.AI_AUTO):
            logger.info("Poule devant la porte (confiance %.2f) : ouverture", hen.confidence)
            self._open(Source.AI_AUTO, ai_confidence=hen.confidence)
            self._opened_for_hen_at = self.clock()

    def _on_predator(self, confidence: float, jpeg: bytes, name: str) -> None:
        logger.warning("Prédateur détecté (%s, %.2f) : porte verrouillée", name, confidence)
        self._predator_until = self.clock() + self.config.predator_lock_s
        # L'alerte part avant la fermeture (qui prend plusieurs secondes), même sans photo.
        photo = reduce_jpeg(jpeg, self.config.photo_max_bytes)
        self.uplink.send_alert(
            "PREDATOR_DETECTED", "CRITICAL", ai_confidence=confidence, image=photo
        )
        if self.door.state != DoorState.CLOSED:
            self._close(Source.FAILSAFE)

    # ------------------------------------------------------------------ commandes

    def on_command(self, action: str, inside_count: int | None = None) -> None:
        """Commande reçue de l'application (déjà filtrée par `mqtt_uplink`)."""
        if action == "OPEN":
            if self._may_open(Source.MANUAL_APP):
                self._open(Source.MANUAL_APP)
                self._opened_for_hen_at = None  # ouverte à la main : pas de fermeture auto
        elif action == "CLOSE":
            self._close(Source.MANUAL_APP)
        elif action == "CALIBRATE" and inside_count is not None:
            self.counter.set_inside(inside_count)
            self.heartbeat()

    # ------------------------------------------------------------------ règles

    def predator_locked(self) -> bool:
        return self.clock() < self._predator_until

    def _may_open(self, source: Source) -> bool:
        if self.predator_locked():
            logger.warning("Ouverture refusée (%s) : prédateur vu récemment", source)
            return False
        if source == Source.AI_AUTO and not self.config.schedule.is_day(self.now()):
            return False
        return not self._door_in_error()

    def _door_in_error(self) -> bool:
        return self.door.state == DoorState.ERROR

    def _open(self, source: Source, ai_confidence: float | None = None) -> None:
        self._last_activity = self.clock()
        self._handle(self.door.open(source), source, ai_confidence)

    def _close(self, source: Source) -> None:
        self._opened_for_hen_at = None
        self._handle(self.door.close(source), source, None)

    def _handle(self, result: MoveResult, source: Source, ai_confidence: float | None) -> None:
        if result == MoveResult.BLOCKED:
            self._alert_blocked()
        elif result == MoveResult.OBSTACLE:
            self.uplink.send_event(
                "OBSTACLE",
                door_state=str(self.door.state),
                inside_count=self.counter.inside,
                trigger_source=Source.FAILSAFE,
            )
        elif result == MoveResult.DONE:
            event = "DOOR_OPEN" if self.door.state == DoorState.OPEN else "DOOR_CLOSE"
            self.uplink.send_event(
                event,
                door_state=str(self.door.state),
                inside_count=self.counter.inside,
                trigger_source=str(source),
                ai_confidence=ai_confidence,
            )

    def _alert_blocked(self) -> None:
        self.uplink.send_alert("DOOR_BLOCKED", "CRITICAL")
        self.heartbeat()

    def _on_door_change(self, state: DoorState, source: Source) -> None:
        if state in (DoorState.OPENING, DoorState.CLOSING):
            self.uplink.send_telemetry(door_state=str(state))

    def _on_passage(self, passage: Passage, inside: int) -> None:
        self._last_activity = self.clock()
        self.uplink.send_event(str(passage), inside_count=inside)
