"""Détecteur YOLO (Ultralytics) : reconnaît une poule sur l'image de la caméra.

COCO, le jeu d'images sur lequel le modèle est entraîné, n'a pas de classe « poule » : on
garde la classe « bird », qui reconnaît les poules (et tout autre oiseau).

Les poids ne sont pas dans Git : Ultralytics télécharge `yolo11n.pt` au premier lancement.
Sur le Pi, on exporte le modèle en NCNN (`yolo export model=yolo11n.pt format=ncnn`), puis
`YOLO_MODEL=yolo11n_ncnn_model` dans `.env`.
"""

import io
import os
from typing import Any

from ai_detector.base import Detection, Label
from hardware.interfaces import Frame

BIRD = 14  # numéro de la classe « bird » dans COCO
DEFAULT_MODEL = "yolo11n.pt"  # version nano : 5 Mo, assez rapide pour le Pi 5


class YoloDetector:
    """Renvoie une `Detection(Label.HEN, …)` par poule vue sur l'image.

    confidence : en dessous, le modèle ignore ce qu'il voit. Le seuil qui décide d'ouvrir la
    porte (`HEN_THRESHOLD`) est appliqué ensuite par le programme du poulailler.
    yolo : modèle déjà chargé (les tests passent un faux modèle).
    """

    def __init__(self, model: str | None = None, confidence: float = 0.25, yolo: Any = None):
        if yolo is None:
            from ultralytics import YOLO  # seulement installé avec `pip install -e ".[yolo]"`

            yolo = YOLO(model or os.environ.get("YOLO_MODEL", DEFAULT_MODEL))
        self.yolo = yolo
        self.confidence = confidence

    def detect(self, frame: Frame) -> list[Detection]:
        from PIL import Image

        image = Image.open(io.BytesIO(frame.jpeg)).convert("RGB")
        result = self.yolo(image, classes=[BIRD], conf=self.confidence, verbose=False)[0]
        return [Detection(Label.HEN, float(c), "poule") for c in result.boxes.conf.tolist()]
