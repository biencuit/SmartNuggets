"""Moteur pas-à-pas 28BYJ-48 commandé par une carte ULN2003.

Le 28BYJ-48 a 4 bobines. L'ULN2003 les alimente en 5 V quand le Pi met à 1 l'entrée
correspondante (IN1 à IN4). On les allume dans un ordre précis : c'est la séquence.

Séquence en demi-pas (8 étapes) : une bobine, puis deux, puis la suivante seule, etc.
Avec la réduction 1/64 du moteur, il faut 4096 demi-pas pour un tour de l'axe de sortie.
Sous ~1 ms entre deux pas, le moteur décroche (il vibre sans tourner).
"""

import time
from collections.abc import Callable, Sequence

from hardware.interfaces import Direction

# Bobines alimentées à chaque demi-pas, dans l'ordre IN1, IN2, IN3, IN4.
HALF_STEP_SEQUENCE: tuple[tuple[int, int, int, int], ...] = (
    (1, 0, 0, 0),
    (1, 1, 0, 0),
    (0, 1, 0, 0),
    (0, 1, 1, 0),
    (0, 0, 1, 0),
    (0, 0, 1, 1),
    (0, 0, 0, 1),
    (1, 0, 0, 1),
)
STEPS_PER_TURN = 4096  # demi-pas par tour de l'axe de sortie
MIN_STEP_DELAY_S = 0.001


class HalfStepper:
    """Pilote générique : écrit la séquence de demi-pas sur 4 sorties.

    `pins` : 4 fonctions `set(valeur)` pour IN1 à IN4. Les sorties sont injectées pour
    que la séquence soit testable sans Raspberry Pi.
    """

    def __init__(
        self,
        pins: Sequence[Callable[[int], None]],
        step_delay_s: float = 0.0015,
        sleep: Callable[[float], None] = time.sleep,
    ) -> None:
        if len(pins) != 4:
            raise ValueError("Il faut exactement 4 sorties (IN1 à IN4)")
        if step_delay_s and step_delay_s < MIN_STEP_DELAY_S:
            raise ValueError(f"Délai trop court : minimum {MIN_STEP_DELAY_S} s entre deux pas")
        self._pins = list(pins)
        self.step_delay_s = step_delay_s
        self._sleep = sleep
        self._index = 0  # position dans HALF_STEP_SEQUENCE
        self.position = 0  # en demi-pas depuis le démarrage (positif = vers le haut)

    def step(self, direction: Direction) -> None:
        self._index = (self._index + int(direction)) % len(HALF_STEP_SEQUENCE)
        self._write(HALF_STEP_SEQUENCE[self._index])
        self.position += int(direction)
        if self.step_delay_s:
            self._sleep(self.step_delay_s)

    def release(self) -> None:
        self._write((0, 0, 0, 0))

    def _write(self, levels: Sequence[int]) -> None:
        for pin, level in zip(self._pins, levels, strict=True):
            pin(level)
