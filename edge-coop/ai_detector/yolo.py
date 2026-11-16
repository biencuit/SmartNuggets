"""Détecteur YOLO (Ultralytics) : reconnaît une poule sur l'image de la caméra.

COCO, le jeu d'images sur lequel le modèle est entraîné, n'a pas de classe « poule » : on
garde la classe « bird », qui reconnaît les poules (et tout autre oiseau).

Mode démo : pour tester sans poule, on fait passer un objet du quotidien pour une poule
(`YOLO_HEN_CLASSES=67` : un téléphone) et, si on veut, un autre pour un prédateur
(`YOLO_PREDATOR_CLASSES=41` : une tasse). Numéros des 80 classes : `coco.yaml` d'Ultralytics.

Les poids ne sont pas dans Git : Ultralytics télécharge `yolo11n.pt` au premier lancement.
Sur le Pi, on exporte le modèle en NCNN (`yolo export model=yolo11n.pt format=ncnn`), puis
`YOLO_MODEL=yolo11n_ncnn_model` dans `.env`.
"""

import io
import os
from collections.abc import Sequence
from typing import Any

from ai_detector.base import Detection, Label
from hardware.interfaces import Frame

BIRD = 14  # numéro de la classe « bird » dans COCO
DEFAULT_MODEL = "yolo11n.pt"  # version nano : 5 Mo, assez rapide pour le Pi 5


def classes_from_env(name: str, default: Sequence[int]) -> tuple[int, ...]:
    """Lit une liste de numéros de classes COCO (« 67 » ou « 41,77 »), vide si absente."""
    value = os.environ.get(name, "").strip()
    if not value:
        return tuple(default)
    try:
        return tuple(int(part) for part in value.split(",") if part.strip())
    except ValueError:
        raise ValueError(f"{name} attend des numéros de classes COCO, reçu : {value!r}") from None


class YoloDetector:
    """Renvoie une `Detection` par poule (ou prédateur) vu sur l'image.

    confidence : en dessous, le modèle ignore ce qu'il voit. Le seuil qui décide d'ouvrir la
    porte (`HEN_THRESHOLD`) est appliqué ensuite par le programme du poulailler.
    hen_classes / predator_classes : classes COCO prises pour une poule / un prédateur
    (par défaut : `YOLO_HEN_CLASSES`, sinon « bird » ; `YOLO_PREDATOR_CLASSES`, sinon aucune).
    yolo : modèle déjà chargé (les tests passent un faux modèle).
    """

    def __init__(
        self,
        model: str | None = None,
        confidence: float = 0.25,
        yolo: Any = None,
        hen_classes: Sequence[int] | None = None,
        predator_classes: Sequence[int] | None = None,
    ):
        if yolo is None:
            from ultralytics import YOLO  # seulement installé avec `pip install -e ".[yolo]"`

            yolo = YOLO(model or os.environ.get("YOLO_MODEL", DEFAULT_MODEL))
        self.yolo = yolo
        self.confidence = confidence
        self.hen_classes = tuple(
            hen_classes if hen_classes is not None else classes_from_env("YOLO_HEN_CLASSES", [BIRD])
        )
        self.predator_classes = tuple(
            predator_classes
            if predator_classes is not None
            else classes_from_env("YOLO_PREDATOR_CLASSES", [])
        )

    def detect(self, frame: Frame) -> list[Detection]:
        from PIL import Image

        image = Image.open(io.BytesIO(frame.jpeg)).convert("RGB")
        wanted = [*self.hen_classes, *self.predator_classes]
        result = self.yolo(image, classes=wanted, conf=self.confidence, verbose=False)[0]
        detections = []
        for cls, conf in zip(result.boxes.cls.tolist(), result.boxes.conf.tolist(), strict=True):
            if int(cls) in self.hen_classes:
                detections.append(Detection(Label.HEN, float(conf), "poule"))
            else:
                name = result.names.get(int(cls), str(int(cls)))
                detections.append(Detection(Label.PREDATOR, float(conf), name))
        return detections
