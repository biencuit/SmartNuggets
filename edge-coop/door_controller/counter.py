"""Comptage des poules avec deux barrières infrarouges dans l'encadrement de la porte.

   dehors | barrière EXTÉRIEURE | barrière INTÉRIEURE | dedans

Une poule qui entre coupe d'abord l'extérieure et libère en dernier l'intérieure.
Une poule qui sort fait l'inverse. Si elle fait demi-tour (elle coupe et libère la même
barrière sans avoir coupé l'autre), rien n'est compté.
"""

from collections.abc import Callable
from enum import StrEnum


class Passage(StrEnum):
    ENTRY = "HEN_ENTRY"
    EXIT = "HEN_EXIT"


class PassageCounter:
    def __init__(
        self, inside: int = 0, on_passage: Callable[[Passage, int], None] | None = None
    ) -> None:
        self.inside = max(0, inside)
        self._on_passage = on_passage or (lambda passage, inside: None)
        self._first: str | None = None  # première barrière coupée
        self._seen: set[str] = set()  # barrières coupées pendant ce passage
        self._last_released: str | None = None
        self._outer = False
        self._inner = False

    def update(self, outer: bool, inner: bool) -> Passage | None:
        """À appeler à chaque lecture des barrières (True = coupée)."""
        for name, now, before in (("outer", outer, self._outer), ("inner", inner, self._inner)):
            if now and not before:
                self._first = self._first or name
                self._seen.add(name)
            elif before and not now:
                self._last_released = name
        self._outer, self._inner = outer, inner
        if outer or inner or self._first is None:
            return None
        return self._finish()

    def _finish(self) -> Passage | None:
        crossed = self._seen == {"outer", "inner"}
        first, last = self._first, self._last_released
        self._first, self._seen, self._last_released = None, set(), None
        if not crossed or first == last:
            return None
        if first == "outer":
            self.inside += 1
            passage = Passage.ENTRY
        else:
            self.inside = max(0, self.inside - 1)
            passage = Passage.EXIT
        self._on_passage(passage, self.inside)
        return passage

    def set_inside(self, inside: int) -> None:
        """Correction manuelle depuis l'application (commande CALIBRATE)."""
        self.inside = max(0, inside)
