"""Ce que le reste du code attend du matériel, sans savoir s'il est réel ou simulé.

Chaque interface a deux versions :
- une version réelle pour le Raspberry Pi 5 (`hardware.gpio`, `hardware.camera`) ;
- une version simulée pour le PC et les tests (`hardware.mock`).
"""

from dataclasses import dataclass, field
from enum import IntEnum
from time import time
from typing import Protocol, runtime_checkable


class Direction(IntEnum):
    """Sens de rotation du moteur : +1 lève la porte, -1 la baisse."""

    UP = 1
    DOWN = -1


@runtime_checkable
class StepperMotor(Protocol):
    """Moteur pas-à-pas (28BYJ-48 + ULN2003 sur le vrai poulailler)."""

    def step(self, direction: Direction) -> None:
        """Avance d'un seul pas dans le sens donné (bloquant, quelques millisecondes)."""

    def release(self) -> None:
        """Coupe le courant dans les bobines (le moteur ne chauffe plus à l'arrêt)."""


@runtime_checkable
class Switch(Protocol):
    """Contact tout ou rien : fin de course, barrière infrarouge, capteur de présence."""

    @property
    def active(self) -> bool:
        """True quand le contact est fermé, la barrière coupée ou un mouvement vu."""


@dataclass(frozen=True)
class Frame:
    """Une image de la caméra, en JPEG (format envoyé au serveur avec les alertes)."""

    jpeg: bytes
    taken_at: float = field(default_factory=time)


@runtime_checkable
class Camera(Protocol):
    def capture(self) -> Frame | None:
        """Prend une image. None si la caméra ne répond pas (camera_ok = False)."""

    def close(self) -> None:
        """Libère la caméra."""
