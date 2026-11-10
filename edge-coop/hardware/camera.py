"""Caméras : Pi Camera (réelle), vidéo enregistrée, ou dossier d'images.

Tant que la caméra du poulailler n'est pas livrée, `VideoCamera` rejoue une vidéo
(par exemple d'une vraie poule) : le reste du code ne voit pas la différence.
"""

import io
import logging
from collections.abc import Callable
from pathlib import Path
from typing import Any

from hardware.interfaces import Camera, Frame

logger = logging.getLogger(__name__)

AIDE_CAMERA = (
    "vérifier la nappe et /boot/firmware/config.txt (edge-coop/README.md, section Caméra), "
    "puis tester avec : rpicam-hello"
)


def _picamera2() -> Any:
    """Ouvre la caméra avec Picamera2 (installé avec apt sur le Pi, pas avec pip)."""
    try:
        from picamera2 import Picamera2
    except ImportError as exc:
        raise RuntimeError(
            "picamera2 introuvable : sudo apt install python3-picamera2, et un "
            "environnement Python créé avec --system-site-packages"
        ) from exc
    return Picamera2()


class PiCamera(Camera):
    """Module caméra du Raspberry Pi (Freenove OV5647 ou IMX219, Camera Module v2…), via Picamera2.

    Si la caméra ne répond pas (nappe débranchée, config.txt incomplet), le programme continue
    sans elle : `capture()` renvoie None (camera_ok = False dans l'application) et réessaie
    d'ouvrir la caméra au prochain appel. La porte et le comptage marchent toujours.
    """

    def __init__(
        self,
        width: int = 640,
        height: int = 480,
        open_camera: Callable[[], Any] = _picamera2,
    ) -> None:
        self._size = (width, height)
        self._open_camera = open_camera
        self._camera: Any = None
        self._failed_before = False
        self._open()

    def _open(self) -> bool:
        camera: Any = None
        try:
            camera = self._open_camera()
            camera.configure(camera.create_still_configuration(main={"size": self._size}))
            camera.start()
        except Exception as exc:
            if camera is not None:
                self._close_quietly(camera)
            if not self._failed_before:  # un seul message détaillé, pas un par mouvement
                logger.error("Caméra introuvable (%s) : %s", exc, AIDE_CAMERA)
                self._failed_before = True
            return False
        if self._failed_before:
            logger.info("Caméra de nouveau disponible")
            self._failed_before = False
        self._camera = camera
        return True

    def capture(self) -> Frame | None:
        if self._camera is None and not self._open():
            return None
        buffer = io.BytesIO()
        try:
            self._camera.capture_file(buffer, format="jpeg")
        except Exception:
            logger.exception("La caméra ne répond pas")
            self.close()
            return None
        return Frame(buffer.getvalue())

    def close(self) -> None:
        if self._camera is not None:
            self._close_quietly(self._camera)
            self._camera = None

    @staticmethod
    def _close_quietly(camera: Any) -> None:
        try:
            camera.close()
        except Exception:
            logger.debug("Fermeture de la caméra impossible", exc_info=True)


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
