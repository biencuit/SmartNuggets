"""Mécanique de la porte : machine à états au-dessus du moteur pas-à-pas.

États : CLOSED → OPENING → OPEN → CLOSING → CLOSED, et ERROR si la porte n'arrive pas au
bout de sa course. Les noms sont ceux attendus par le serveur (`DoorState` du backend).

La position est comptée en demi-pas : 0 = fermée, `travel_steps` = ouverte. Si des fins
de course sont branchés, ce sont eux qui disent quand s'arrêter ; sinon on se fie au
nombre de pas. Pendant la fermeture, la barrière d'obstacle est vérifiée régulièrement :
si elle est coupée, la porte s'arrête et remonte (anti-pincement, base pour #12).
"""

import logging
from collections.abc import Callable
from dataclasses import dataclass
from enum import StrEnum

from hardware.interfaces import Direction, StepperMotor, Switch

logger = logging.getLogger(__name__)


class DoorState(StrEnum):
    OPEN = "OPEN"
    CLOSED = "CLOSED"
    OPENING = "OPENING"
    CLOSING = "CLOSING"
    ERROR = "ERROR"


class Source(StrEnum):
    """Qui a demandé le mouvement (TriggerSource côté serveur)."""

    AI_AUTO = "AI_AUTO"
    MANUAL_APP = "MANUAL_APP"
    SCHEDULE = "SCHEDULE"
    FAILSAFE = "FAILSAFE"


class MoveResult(StrEnum):
    DONE = "DONE"  # la porte est arrivée
    ALREADY = "ALREADY"  # elle y était déjà
    OBSTACLE = "OBSTACLE"  # fermeture interrompue, la porte est remontée
    BLOCKED = "BLOCKED"  # fin de course jamais atteint : état ERROR


@dataclass(frozen=True)
class DoorConfig:
    travel_steps: int = 8192  # demi-pas entre fermée et ouverte (2 tours de 28BYJ-48)
    margin_steps: int = 1024  # pas en plus tolérés avant de déclarer la porte bloquée
    check_every: int = 32  # vérifier l'obstacle tous les N pas


class Door:
    def __init__(
        self,
        motor: StepperMotor,
        config: DoorConfig | None = None,
        *,
        top: Switch | None = None,
        bottom: Switch | None = None,
        obstacle: Switch | None = None,
        on_change: Callable[[DoorState, Source], None] | None = None,
        initial: DoorState = DoorState.CLOSED,
    ) -> None:
        self.motor = motor
        self.config = config or DoorConfig()
        self.top = top
        self.bottom = bottom
        self.obstacle = obstacle
        self._on_change = on_change or (lambda state, source: None)
        self.state = initial
        self.position = self.config.travel_steps if initial == DoorState.OPEN else 0

    # ------------------------------------------------------------------ commandes

    def open(self, source: Source) -> MoveResult:
        if self.state == DoorState.OPEN:
            return MoveResult.ALREADY
        return self._move(Direction.UP, source)

    def close(self, source: Source) -> MoveResult:
        if self.state == DoorState.CLOSED:
            return MoveResult.ALREADY
        return self._move(Direction.DOWN, source)

    def calibrate(self) -> MoveResult:
        """Au démarrage, on ne sait pas où est la porte : on la descend jusqu'en bas."""
        self.state = DoorState.OPEN
        self.position = self.config.travel_steps
        return self._move(Direction.DOWN, Source.FAILSAFE)

    # ------------------------------------------------------------------ mouvement

    def _set(self, state: DoorState, source: Source) -> None:
        self.state = state
        self._on_change(state, source)

    def _arrived(self, direction: Direction) -> bool:
        switch = self.top if direction == Direction.UP else self.bottom
        if switch is not None:
            return switch.active
        target = self.config.travel_steps if direction == Direction.UP else 0
        return self.position == target

    def _move(self, direction: Direction, source: Source) -> MoveResult:
        closing = direction == Direction.DOWN
        self._set(DoorState.CLOSING if closing else DoorState.OPENING, source)
        limit = self.config.travel_steps + self.config.margin_steps
        steps = 0
        try:
            while not self._arrived(direction):
                if steps >= limit:
                    logger.error("Porte bloquée : fin de course non atteint après %d pas", steps)
                    self._set(DoorState.ERROR, source)
                    return MoveResult.BLOCKED
                if closing and steps % self.config.check_every == 0 and self._obstacle():
                    logger.warning("Obstacle pendant la fermeture : la porte remonte")
                    self._reopen()
                    return MoveResult.OBSTACLE
                self.motor.step(direction)
                self.position += int(direction)
                steps += 1
        finally:
            self.motor.release()
        self.position = self.config.travel_steps if direction == Direction.UP else 0
        self._set(DoorState.CLOSED if closing else DoorState.OPEN, source)
        return MoveResult.DONE

    def _obstacle(self) -> bool:
        return self.obstacle is not None and self.obstacle.active

    def _reopen(self) -> None:
        self._set(DoorState.OPENING, Source.FAILSAFE)
        while not self._arrived(Direction.UP) and self.position < self.config.travel_steps:
            self.motor.step(Direction.UP)
            self.position += 1
        self.position = self.config.travel_steps
        self._set(DoorState.OPEN, Source.FAILSAFE)
