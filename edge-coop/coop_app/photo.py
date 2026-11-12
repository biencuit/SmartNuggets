"""Photo des alertes : réduite avant d'être envoyée au serveur (US-SECU-3, #23).

La caméra du Pi prend du 640 x 480, mais une vidéo ou un dossier d'images (démo, essais)
peut donner une image bien plus lourde. Le serveur refuse les photos de plus de 2 Mo, et
l'alerte doit arriver vite même sur une connexion faible : on vise moins de 200 Ko.

La photo ne doit jamais empêcher l'alerte de partir : en cas de problème, `reduce_jpeg`
renvoie None et l'alerte part sans photo.
"""

import io
import logging

logger = logging.getLogger(__name__)

MAX_BYTES = 200_000
MAX_SIDE = 640  # pixels, côté le plus long
QUALITIES = (80, 70, 60, 50, 40)
MIN_SIDE = 80  # en dessous, la photo ne montre plus rien d'utile


def reduce_jpeg(jpeg: bytes, max_bytes: int = MAX_BYTES, max_side: int = MAX_SIDE) -> bytes | None:
    """Renvoie un JPEG d'au plus `max_bytes` octets et `max_side` pixels de côté.

    Une image qui respecte déjà ces limites est renvoyée telle quelle (pas de perte de
    qualité). None si l'image est illisible ou ne peut pas être réduite assez.
    """
    try:
        from PIL import Image
    except ImportError:
        if len(jpeg) <= max_bytes:
            return jpeg
        logger.warning("Photo de %d octets et Pillow absent : alerte sans photo", len(jpeg))
        return None

    try:
        with Image.open(io.BytesIO(jpeg)) as image:
            if image.format == "JPEG" and len(jpeg) <= max_bytes and max(image.size) <= max_side:
                return jpeg
            picture = image.convert("RGB")
    except (OSError, Image.DecompressionBombError):
        logger.warning("Photo illisible : alerte sans photo")
        return None

    side = max_side
    while side >= MIN_SIDE:
        picture.thumbnail((side, side))
        for quality in QUALITIES:
            buffer = io.BytesIO()
            picture.save(buffer, format="JPEG", quality=quality, optimize=True)
            if buffer.tell() <= max_bytes:
                return buffer.getvalue()
        side //= 2
    logger.warning("Photo impossible à réduire sous %d octets : alerte sans photo", max_bytes)
    return None
