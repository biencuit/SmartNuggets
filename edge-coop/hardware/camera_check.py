"""Vérifie la caméra du Raspberry Pi en prenant une photo, avec le même code que le poulailler.

python -m hardware.camera_check               # photo dans test-camera.jpg
python -m hardware.camera_check photo.jpg     # autre nom de fichier
"""

import argparse
import logging
from pathlib import Path

from hardware.camera import AIDE_CAMERA, PiCamera
from hardware.interfaces import Camera


def check(camera: Camera, output: Path) -> bool:
    """Prend une photo et l'enregistre. False si la caméra ne donne pas d'image."""
    try:
        frame = camera.capture()
    finally:
        camera.close()
    if frame is None:
        print(f"Pas d'image : {AIDE_CAMERA}")
        return False
    output.write_bytes(frame.jpeg)
    print(f"Photo enregistrée : {output} ({len(frame.jpeg) // 1024} Ko)")
    return True


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("output", nargs="?", default="test-camera.jpg", type=Path)
    parser.add_argument("--largeur", type=int, default=640)
    parser.add_argument("--hauteur", type=int, default=480)
    args = parser.parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    return 0 if check(PiCamera(args.largeur, args.hauteur), args.output) else 1


if __name__ == "__main__":
    raise SystemExit(main())
