"""Détecteur YOLO, testé avec un faux modèle (le vrai n'est pas installé dans la CI)."""

from types import SimpleNamespace

import pytest

pytest.importorskip("PIL")

from ai_detector import Detection, Detector, Label, best, load_detector  # noqa: E402
from ai_detector.yolo import BIRD, YoloDetector  # noqa: E402
from hardware.mock import FakeCamera  # noqa: E402

FRAME = FakeCamera().capture()


class FakeYolo:
    """Imite `ultralytics.YOLO` : renvoie les confiances prévues et retient l'appel."""

    def __init__(self, confidences: list[float]) -> None:
        self.confidences = confidences
        self.calls: list[dict] = []

    def __call__(self, image, **kwargs):
        self.calls.append({"image": image, **kwargs})
        boxes = SimpleNamespace(conf=SimpleNamespace(tolist=lambda: self.confidences))
        return [SimpleNamespace(boxes=boxes)]


def test_une_poule_vue_donne_une_detection_hen():
    detector = YoloDetector(yolo=FakeYolo([0.91]))
    assert detector.detect(FRAME) == [Detection(Label.HEN, 0.91, "poule")]


def test_plusieurs_poules_donnent_plusieurs_detections():
    detector = YoloDetector(yolo=FakeYolo([0.88, 0.75]))
    assert [d.confidence for d in detector.detect(FRAME)] == [0.88, 0.75]


def test_pas_de_poule_donne_une_liste_vide():
    assert YoloDetector(yolo=FakeYolo([])).detect(FRAME) == []


def test_le_modele_ne_cherche_que_les_oiseaux_au_dessus_du_seuil():
    fake = FakeYolo([])
    YoloDetector(confidence=0.4, yolo=fake).detect(FRAME)
    call = fake.calls[0]
    assert call["classes"] == [BIRD] == [14]
    assert call["conf"] == 0.4
    assert call["image"].mode == "RGB"  # le JPEG de la caméra est décodé avant l'analyse


def test_le_seuil_du_poulailler_s_applique_aux_detections():
    detections = YoloDetector(yolo=FakeYolo([0.5, 0.82])).detect(FRAME)
    assert best(detections, Label.HEN, 0.7) == Detection(Label.HEN, 0.82, "poule")
    assert best(detections, Label.HEN, 0.9) is None


def test_se_charge_par_son_chemin_comme_dans_le_env():
    detector = load_detector("ai_detector.yolo:YoloDetector", yolo=FakeYolo([]))
    assert isinstance(detector, Detector)
