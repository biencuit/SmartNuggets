"""Plage horaire de la journée : en dehors, la porte reste fermée (base pour #14).

Heures fixes pour l'instant. Une évolution possible : calculer le lever et le coucher du
soleil, ou utiliser un capteur de luminosité.
"""

from dataclasses import dataclass
from datetime import datetime, time


@dataclass(frozen=True)
class Schedule:
    open_from: time = time(7, 0)
    close_at: time = time(21, 0)

    def is_day(self, now: datetime) -> bool:
        current = now.time()
        if self.open_from <= self.close_at:
            return self.open_from <= current < self.close_at
        return current >= self.open_from or current < self.close_at  # plage sur minuit

    @classmethod
    def parse(cls, open_from: str, close_at: str) -> "Schedule":
        return cls(time.fromisoformat(open_from), time.fromisoformat(close_at))
