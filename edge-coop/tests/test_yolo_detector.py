"""Détecteur YOLO, testé avec un faux modèle (le vrai n'est pas installé dans la CI)."""

from types import SimpleNamespace

import pytest

pytest.importorskip("PIL")

from ai_detector import Detection, Detector, Label, best, load_detector  # noqa: E402
from ai_detector.yolo import BIRD, YoloDetector  # noqa: E402
from hardware.mock import FakeCamera  # noqa: E402

FRAME = FakeCamera().capture()


PHONE, CUP = 67, 41  # classes COCO « cell phone » et « cup »
NAMES = {BIRD: "bird", CUP: "cup", PHONE: "cell phone"}


@pytest.fixture(autouse=True)
def sans_mode_demo(monkeypatch):
    monkeypatch.delenv("YOLO_HEN_CLASSES", raising=False)
    monkeypatch.delenv("YOLO_PREDATOR_CLASSES", raising=False)


class FakeYolo:
    """Imite `ultralytics.YOLO` : renvoie les objets prévus et retient l'appel.

    confidences : une confiance par objet vu ; classes : leur classe COCO (oiseau par défaut).
    """

    def __init__(self, confidences: list[float], classes: list[int] | None = None) -> None:
        self.confidences = confidences
        self.classes = classes if classes is not None else [BIRD] * len(confidences)
        self.calls: list[dict] = []

    def __call__(self, image, **kwargs):
        self.calls.append({"image": image, **kwargs})
        boxes = SimpleNamespace(
            conf=SimpleNamespace(tolist=lambda: self.confidences),
            cls=SimpleNamespace(tolist=lambda: [float(c) for c in self.classes]),
        )
        return [SimpleNamespace(boxes=boxes, names=NAMES)]


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


def test_mode_demo_un_telephone_passe_pour_une_poule(monkeypatch):
    monkeypatch.setenv("YOLO_HEN_CLASSES", "67")
    fake = FakeYolo([0.88], classes=[PHONE])
    detector = YoloDetector(yolo=fake)
    assert detector.detect(FRAME) == [Detection(Label.HEN, 0.88, "poule")]
    assert fake.calls[0]["classes"] == [PHONE]  # un vrai oiseau n'est plus cherché


def test_mode_demo_un_objet_passe_pour_un_predateur(monkeypatch):
    monkeypatch.setenv("YOLO_HEN_CLASSES", "67")
    monkeypatch.setenv("YOLO_PREDATOR_CLASSES", "41")
    fake = FakeYolo([0.9, 0.8], classes=[PHONE, CUP])
    detections = YoloDetector(yolo=fake).detect(FRAME)
    assert fake.calls[0]["classes"] == [PHONE, CUP]
    assert detections == [Detection(Label.HEN, 0.9, "poule"), Detection(Label.PREDATOR, 0.8, "cup")]


def test_classes_passees_directement():
    fake = FakeYolo([0.7], classes=[CUP])
    detector = YoloDetector(yolo=fake, hen_classes=[BIRD, PHONE], predator_classes=[CUP])
    assert fake.calls == []
    assert detector.detect(FRAME) == [Detection(Label.PREDATOR, 0.7, "cup")]
    assert fake.calls[0]["classes"] == [BIRD, PHONE, CUP]


def test_classes_invalides_dans_le_env(monkeypatch):
    monkeypatch.setenv("YOLO_HEN_CLASSES", "telephone")
    with pytest.raises(ValueError, match="YOLO_HEN_CLASSES"):
        YoloDetector(yolo=FakeYolo([]))
