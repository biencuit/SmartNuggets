"""Photo des alertes réduite avant l'envoi (US-SECU-3, #23)."""

import io
import random
import sys

from PIL import Image

from coop_app.photo import MAX_BYTES, reduce_jpeg
from hardware.mock import TINY_JPEG


def make_image(width: int, height: int, noise: bool = False, fmt: str = "JPEG") -> bytes:
    """Bruit aléatoire (JPEG très lourd) ou dégradé (JPEG léger)."""
    if noise:
        pixels = random.Random(23).randbytes(width * height * 3)
        image = Image.frombytes("RGB", (width, height), pixels)
    else:
        image = Image.linear_gradient("L").resize((width, height)).convert("RGB")
    buffer = io.BytesIO()
    image.save(buffer, format=fmt, **({"quality": 95} if fmt == "JPEG" else {}))
    return buffer.getvalue()


def big_jpeg() -> bytes:
    """Photo de 3000 x 2000 bien plus lourde que 200 Ko (une image d'une vidéo HD, par ex.)."""
    jpeg = make_image(3000, 2000, noise=True)
    assert len(jpeg) > 5 * MAX_BYTES
    return jpeg


def open_jpeg(data: bytes) -> Image.Image:
    image = Image.open(io.BytesIO(data))
    assert image.format == "JPEG"
    return image


def test_photo_trop_lourde_reduite_sous_200_ko():
    photo = reduce_jpeg(big_jpeg())
    assert photo is not None
    assert len(photo) <= MAX_BYTES and photo.startswith(b"\xff\xd8")
    assert max(open_jpeg(photo).size) <= 640


def test_grande_photo_legere_ramenee_a_640_px():
    photo = reduce_jpeg(make_image(1920, 1080))
    assert photo is not None
    assert open_jpeg(photo).size == (640, 360)  # proportions gardées


def test_petite_photo_envoyee_telle_quelle():
    jpeg = make_image(640, 480)
    assert reduce_jpeg(jpeg) == jpeg
    assert reduce_jpeg(TINY_JPEG) == TINY_JPEG


def test_autre_format_converti_en_jpeg():
    photo = reduce_jpeg(make_image(320, 240, fmt="PNG"))
    assert photo is not None
    assert open_jpeg(photo).size == (320, 240)


def test_image_illisible_ou_impossible_a_reduire():
    assert reduce_jpeg(b"pas une image") is None
    assert reduce_jpeg(big_jpeg()[:5000]) is None  # photo coupée en cours de transfert
    assert reduce_jpeg(make_image(640, 480), max_bytes=100) is None


def test_sans_pillow_seule_une_photo_legere_part(monkeypatch):
    monkeypatch.setitem(sys.modules, "PIL", None)  # `from PIL import …` lève ImportError
    light = b"\xff\xd8" + bytes(1000)
    assert reduce_jpeg(light) == light
    assert reduce_jpeg(b"\xff\xd8" + bytes(MAX_BYTES)) is None
