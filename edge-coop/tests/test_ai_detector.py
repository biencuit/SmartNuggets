"""Interface de détection et détecteur simulé."""

import pytest

from ai_detector import Detection, Detector, Label, ScriptedDetector, best, load_detector
from hardware.mock import FakeCamera

FRAME = FakeCamera().capture()


def test_le_detecteur_simule_rend_les_reponses_dans_l_ordre_puis_rien():
    detector = ScriptedDetector()
    detector.show(Label.HEN, 0.9)
    detector.show("predator", 0.8, "renard")
    assert detector.detect(FRAME) == [Detection(Label.HEN, 0.9, "hen")]
    assert detector.detect(FRAME) == [Detection(Label.PREDATOR, 0.8, "renard")]
    assert detector.detect(FRAME) == []
    assert detector.calls == 3


def test_best_garde_la_plus_sure_au_dessus_du_seuil():
    seen = [Detection(Label.HEN, 0.6), Detection(Label.HEN, 0.95), Detection(Label.PREDATOR, 0.99)]
    assert best(seen, Label.HEN, 0.7) == Detection(Label.HEN, 0.95)
    assert best(seen, Label.HEN, 0.97) is None
    assert best([], Label.PREDATOR, 0.5) is None


def test_confiance_invalide_refusee():
    with pytest.raises(ValueError):
        Detection(Label.HEN, 1.5)


class ModeleDeLouis:
    """Exemple de vrai modèle branché par son chemin, comme dans le .env."""

    def __init__(self, seuil: float = 0.5) -> None:
        self.seuil = seuil

    def detect(self, frame):
        return [Detection(Label.HEN, 0.77, "poule")]


def test_charger_un_detecteur_par_son_chemin():
    assert isinstance(load_detector("scripted"), ScriptedDetector)
    detector = load_detector("tests.test_ai_detector:ModeleDeLouis", seuil=0.3)
    assert isinstance(detector, Detector)
    assert detector.seuil == 0.3
    assert detector.detect(FRAME)[0].name == "poule"


def test_chemin_de_detecteur_invalide():
    with pytest.raises(ValueError):
        load_detector("ai_detector.scripted")
    with pytest.raises(TypeError):
        load_detector("hardware.mock:FakeSwitch")
