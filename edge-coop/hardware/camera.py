"""Caméras : Pi Camera (réelle), vidéo enregistrée, ou dossier d'images.

Tant que la caméra du poulailler n'est pas livrée, `VideoCamera` rejoue une vidéo
(par exemple d'une vraie poule) : le reste du code ne voit pas la différence.
"""

import logging
from pathlib import Path
from typing import Any

from hardware.interfaces import Camera, Frame

logger = logging.getLogger(__name__)


class PiCamera(Camera):
    """Module caméra du Raspberry Pi (NoIR v2), via Picamera2 (installé avec apt sur le Pi)."""

    def __init__(self, width: int = 640, height: int = 480) -> None:
        from picamera2 import Picamera2

        self._camera: Any = Picamera2()
        self._camera.configure(
            self._camera.create_still_configuration(main={"size": (width, height)})
        )
        self._camera.start()

    def capture(self) -> Frame | None:
        import io

        buffer = io.BytesIO()
        try:
            self._camera.capture_file(buffer, format="jpeg")
        except Exception:
            logger.exception("La caméra ne répond pas")
            return None
        return Frame(buffer.getvalue())

    def close(self) -> None:
        self._camera.close()


class VideoCamera(Camera):
    """Rejoue une vidéo image par image (OpenCV, extra `video`). Reprend au début à la fin."""

    def __init__(self, path: str | Path, every_n_frames: int = 5) -> None:
        import cv2

        self._cv2 = cv2
        self._video = cv2.VideoCapture(str(path))
        if not self._video.isOpened():
            raise FileNotFoundError(f"Vidéo illisible : {path}")
        self._skip = max(1, every_n_frames)

    def capture(self) -> Frame | None:
        image = None
        for _ in range(self._skip):
            ok, image = self._video.read()
            if not ok:
                self._video.set(self._cv2.CAP_PROP_POS_FRAMES, 0)
                ok, image = self._video.read()
                if not ok:
                    return None
        ok, jpeg = self._cv2.imencode(".jpg", image)
        return Frame(jpeg.tobytes()) if ok else None

    def close(self) -> None:
        self._video.release()


class FolderCamera(Camera):
    """Renvoie tour à tour les images JPEG d'un dossier (aucune dépendance)."""

    def __init__(self, folder: str | Path) -> None:
        self._images = sorted(Path(folder).glob("*.jp*g"))
        if not self._images:
            raise FileNotFoundError(f"Aucune image JPEG dans {folder}")
        self._next = 0

    def capture(self) -> Frame | None:
        path = self._images[self._next % len(self._images)]
        self._next += 1
        return Frame(path.read_bytes())

    def close(self) -> None:
        return None
