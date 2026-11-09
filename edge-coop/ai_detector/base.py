"""Interface commune des détecteurs."""

import importlib
from collections.abc import Iterable
from dataclasses import dataclass
from enum import StrEnum
from typing import Any, Protocol, runtime_checkable

from hardware.interfaces import Frame


class Label(StrEnum):
    HEN = "hen"
    PREDATOR = "predator"
    OTHER = "other"


@dataclass(frozen=True)
class Detection:
    """Un objet vu sur l'image.

    label : catégorie utilisée par la porte (poule, prédateur, autre).
    confidence : entre 0 et 1.
    name : nom précis renvoyé par le modèle (« renard », « chat »…), pour les journaux.
    """

    label: Label
    confidence: float
    name: str = ""

    def __post_init__(self) -> None:
        if not 0.0 <= self.confidence <= 1.0:
            raise ValueError(f"Confiance hors de [0, 1] : {self.confidence}")


@runtime_checkable
class Detector(Protocol):
    def detect(self, frame: Frame) -> list[Detection]:
        """Analyse une image et renvoie ce qui a été vu (liste vide si rien)."""


def best(detections: Iterable[Detection], label: Label, threshold: float) -> Detection | None:
    """La détection la plus sûre de cette catégorie, si elle dépasse le seuil."""
    candidates = [d for d in detections if d.label == label and d.confidence >= threshold]
    return max(candidates, key=lambda d: d.confidence, default=None)


def load_detector(spec: str, **kwargs: Any) -> Detector:
    """Crée un détecteur à partir de « module:Classe » (ou « scripted » pour la démo)."""
    if spec == "scripted":
        spec = "ai_detector.scripted:ScriptedDetector"
    module_name, _, class_name = spec.partition(":")
    if not class_name:
        raise ValueError(f"Format attendu « module:Classe », reçu : {spec!r}")
    detector = getattr(importlib.import_module(module_name), class_name)(**kwargs)
    if not isinstance(detector, Detector):
        raise TypeError(f"{spec} n'a pas de méthode detect(frame)")
    return detector
