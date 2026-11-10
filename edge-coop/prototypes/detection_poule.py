#!/usr/bin/env python3
"""Teste le vrai détecteur YOLO sur un dossier de photos (US-DET-2).

Affiche pour chaque image « Poule détectée » ou « Pas de poule » et le temps d'analyse,
pour vérifier les critères d'acceptation (confiance > 0,7, moins de 500 ms sur le Pi 5).

    pip install -e ".[yolo]"
    python prototypes/detection_poule.py chemin/vers/images
"""

import sys
import time
from pathlib import Path

from ai_detector import Label, best
from ai_detector.yolo import YoloDetector
from hardware.interfaces import Frame

SEUIL_POULE = 0.7  # même valeur que HEN_THRESHOLD dans .env


def main(dossier: Path) -> None:
    detecteur = YoloDetector()
    for image in sorted(dossier.glob("*.jpg")):
        frame = Frame(image.read_bytes())
        debut = time.perf_counter()
        detections = detecteur.detect(frame)
        duree_ms = (time.perf_counter() - debut) * 1000

        poule = best(detections, Label.HEN, SEUIL_POULE)
        verdict = f"Poule détectée (confiance {poule.confidence:.2f})" if poule else "Pas de poule"
        print(f"{image.name} : {verdict} - {duree_ms:.0f} ms")


if __name__ == "__main__":
    main(Path(sys.argv[1] if len(sys.argv) > 1 else "."))
