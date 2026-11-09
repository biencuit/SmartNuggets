"""Couche matérielle : séquence du 28BYJ-48 et simulateurs."""

import pytest

from hardware import HALF_STEP_SEQUENCE, STEPS_PER_TURN, Direction, HalfStepper
from hardware.camera import FolderCamera
from hardware.interfaces import Camera, StepperMotor, Switch
from hardware.mock import TINY_JPEG, FakeCamera, FakeStepper, FakeSwitch, LimitSwitch


class Recorder:
    """4 fausses sorties GPIO : garde l'état des bobines après chaque pas."""

    def __init__(self) -> None:
        self.levels = [0, 0, 0, 0]
        self.history: list[tuple[int, ...]] = []

    def pins(self):
        def make(i):
            def set_level(level: int) -> None:
                self.levels[i] = level
                if i == 3:
                    self.history.append(tuple(self.levels))

            return set_level

        return [make(i) for i in range(4)]


def test_sequence_demi_pas_une_ou_deux_bobines_voisines():
    assert len(HALF_STEP_SEQUENCE) == 8
    for current, following in zip(
        HALF_STEP_SEQUENCE, HALF_STEP_SEQUENCE[1:] + HALF_STEP_SEQUENCE[:1], strict=True
    ):
        assert sum(current) in (1, 2)
        # D'un demi-pas au suivant, une seule bobine change d'état.
        assert sum(a != b for a, b in zip(current, following, strict=True)) == 1


def test_le_moteur_parcourt_la_sequence_dans_les_deux_sens():
    rec = Recorder()
    motor = HalfStepper(rec.pins(), step_delay_s=0)
    for _ in range(8):
        motor.step(Direction.UP)
    assert rec.history == [*HALF_STEP_SEQUENCE[1:], HALF_STEP_SEQUENCE[0]]
    assert motor.position == 8

    rec.history.clear()
    for _ in range(8):
        motor.step(Direction.DOWN)
    assert rec.history == list(reversed(HALF_STEP_SEQUENCE))
    assert motor.position == 0


def test_release_coupe_les_quatre_bobines():
    rec = Recorder()
    motor = HalfStepper(rec.pins(), step_delay_s=0)
    motor.step(Direction.UP)
    motor.release()
    assert rec.levels == [0, 0, 0, 0]


def test_un_tour_complet_fait_4096_demi_pas_et_attend_entre_chaque():
    waits: list[float] = []
    motor = HalfStepper(Recorder().pins(), step_delay_s=0.002, sleep=waits.append)
    for _ in range(STEPS_PER_TURN):
        motor.step(Direction.UP)
    assert motor.position == 4096
    assert waits == [0.002] * 4096


def test_refuse_un_delai_trop_court_ou_un_mauvais_nombre_de_sorties():
    with pytest.raises(ValueError, match="Délai trop court"):
        HalfStepper(Recorder().pins(), step_delay_s=0.0002)
    with pytest.raises(ValueError, match="4 sorties"):
        HalfStepper(Recorder().pins()[:3])


def test_les_simulateurs_respectent_les_interfaces():
    assert isinstance(FakeStepper(), StepperMotor)
    assert isinstance(FakeSwitch(), Switch)
    assert isinstance(FakeCamera(), Camera)


def test_fin_de_course_simule_suit_la_position_du_moteur():
    motor = FakeStepper()
    top = LimitSwitch(motor, 10, above=True)
    bottom = LimitSwitch(motor, 0, above=False)
    assert bottom.active and not top.active
    for _ in range(10):
        motor.step(Direction.UP)
    assert top.active and not bottom.active
    top.stuck = True
    assert not top.active


def test_camera_simulee_et_panne():
    camera = FakeCamera()
    assert camera.capture().jpeg == TINY_JPEG
    camera.broken = True
    assert camera.capture() is None


def test_camera_dossier_tourne_en_boucle(tmp_path):
    (tmp_path / "a.jpg").write_bytes(b"A")
    (tmp_path / "b.jpg").write_bytes(b"B")
    camera = FolderCamera(tmp_path)
    assert [camera.capture().jpeg for _ in range(3)] == [b"A", b"B", b"A"]
    with pytest.raises(FileNotFoundError):
        FolderCamera(tmp_path / "vide")
