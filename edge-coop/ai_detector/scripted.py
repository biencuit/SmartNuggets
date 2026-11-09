"""Détecteur simulé : renvoie ce qu'on lui a dit de voir (tests et mode démo)."""

from collections import deque

from ai_detector.base import Detection, Label
from hardware.interfaces import Frame


class ScriptedDetector:
    """Chaque appel à `detect` renvoie la prochaine réponse prévue, puis plus rien.

    >>> detector = ScriptedDetector()
    >>> detector.show(Label.HEN, 0.92)
    >>> detector.detect(frame)   # [Detection(Label.HEN, 0.92)]
    >>> detector.detect(frame)   # []
    """

    def __init__(self) -> None:
        self._pending: deque[list[Detection]] = deque()
        self.calls = 0

    def show(self, label: Label | str, confidence: float = 0.9, name: str = "") -> None:
        """Le prochain appel à `detect` verra cet objet."""
        self._pending.append([Detection(Label(label), confidence, name or str(label))])

    def show_nothing(self) -> None:
        self._pending.append([])

    def detect(self, frame: Frame) -> list[Detection]:
        self.calls += 1
        return self._pending.popleft() if self._pending else []
