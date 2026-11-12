"""Caméra du Pi (PiCamera) avec un faux Picamera2 : la vraie est testée sur le Raspberry Pi."""

import logging

import pytest

from hardware.camera import PiCamera
from hardware.camera_check import check
from hardware.mock import TINY_JPEG, FakeCamera


class FakePicamera2:
    """Imite l'API de Picamera2 utilisée par PiCamera."""

    def __init__(self, fail_start: bool = False) -> None:
        self.fail_start = fail_start
        self.fail_capture = False
        self.config = None
        self.started = False
        self.closed = False

    def create_still_configuration(self, main):
        return {"main": main}

    def configure(self, config) -> None:
        self.config = config

    def start(self) -> None:
        if self.fail_start:
            raise RuntimeError("Camera __init__ sequence did not complete.")
        self.started = True

    def capture_file(self, buffer, format):
        assert format == "jpeg"
        if self.fail_capture:
            raise RuntimeError("timeout")
        buffer.write(TINY_JPEG)

    def close(self) -> None:
        self.closed = True


class Opener:
    """Fabrique de fausses caméras : garde chaque caméra ouverte, échoue sur demande."""

    def __init__(self, *failures: bool) -> None:
        self.failures = list(failures)
        self.cameras: list[FakePicamera2] = []

    def __call__(self) -> FakePicamera2:
        fail = self.failures.pop(0) if self.failures else False
        camera = FakePicamera2(fail_start=fail)
        self.cameras.append(camera)
        return camera


def test_photo_jpeg_dans_la_taille_demandee():
    opener = Opener()
    camera = PiCamera(800, 600, open_camera=opener)
    frame = camera.capture()
    assert frame is not None and frame.jpeg == TINY_JPEG
    assert opener.cameras[0].config == {"main": {"size": (800, 600)}}
    camera.close()
    assert opener.cameras[0].closed


def test_camera_absente_au_demarrage_le_programme_continue(caplog):
    opener = Opener(True, True)
    with caplog.at_level(logging.ERROR):
        camera = PiCamera(open_camera=opener)
        assert camera.capture() is None  # camera_ok = False dans l'application
    assert opener.cameras[0].closed  # pas de caméra laissée à moitié ouverte
    assert len([r for r in caplog.records if "Caméra introuvable" in r.message]) == 1


def test_camera_rebranchee_elle_repart_toute_seule():
    opener = Opener(True)
    camera = PiCamera(open_camera=opener)
    frame = camera.capture()  # 2e essai : la caméra répond
    assert frame is not None
    assert len(opener.cameras) == 2


def test_photo_ratee_la_camera_est_rouverte_ensuite():
    opener = Opener()
    camera = PiCamera(open_camera=opener)
    opener.cameras[0].fail_capture = True
    assert camera.capture() is None
    assert opener.cameras[0].closed
    assert camera.capture() is not None
    assert len(opener.cameras) == 2


def test_picamera2_absent_message_clair(caplog, monkeypatch):
    import builtins

    real_import = builtins.__import__

    def no_picamera2(name, *args, **kwargs):
        if name == "picamera2":
            raise ImportError(name)
        return real_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", no_picamera2)
    with caplog.at_level(logging.ERROR):
        camera = PiCamera()
    assert camera.capture() is None
    assert "python3-picamera2" in caplog.text


@pytest.mark.parametrize("works", [True, False])
def test_verification_de_la_camera(tmp_path, capsys, works):
    output = tmp_path / "photo.jpg"
    camera = FakeCamera() if works else PiCamera(open_camera=Opener(True, True))
    assert check(camera, output) is works
    assert output.exists() is works
    assert ("Photo enregistrée" if works else "Pas d'image") in capsys.readouterr().out
