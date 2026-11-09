"""Détection d'image : ce que la porte attend d'un détecteur, quel que soit le modèle.

Pour brancher un vrai modèle (YOLOv8-nano de Louis par exemple) :
1. écrire une classe avec une méthode `detect(frame) -> list[Detection]` ;
2. mettre son chemin dans `.env` : `DETECTOR=ai_detector.yolo:YoloDetector`.
Le reste du code ne change pas.
"""

from ai_detector.base import Detection, Detector, Label, best, load_detector
from ai_detector.scripted import ScriptedDetector

__all__ = ["Detection", "Detector", "Label", "ScriptedDetector", "best", "load_detector"]
