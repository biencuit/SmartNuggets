"""Capture d'images depuis la caméra du poulailler (Raspberry Pi 5 ou webcam USB).

Les images sont rangées par session : raw/real/<session>/<session>_<horodatage>_<n>.jpg
Une session = un groupe : toutes ses images iront dans le même jeu (train, val ou test).
Faites donc plusieurs sessions (matin, midi, soir, météo différente) plutôt qu'une seule longue.

Exemples :
    python capture.py --session 2026-11-18_matin --interval 5 --count 100
    python capture.py --session 2026-11-18_soir --motion 6 --count 200
"""
from __future__ import annotations

import argparse
import time
from datetime import datetime
from pathlib import Path

import cv2
import numpy as np

from common import ROOT, add_data_arg


class Camera:
    """Picamera2 si disponible (Raspberry Pi), sinon webcam OpenCV."""

    def __init__(self, device: int, width: int, height: int):
        self.picam = None
        self.cap = None
        try:
            from picamera2 import Picamera2

            self.picam = Picamera2()
            cfg = self.picam.create_still_configuration(main={"size": (width, height), "format": "RGB888"})
            self.picam.configure(cfg)
            self.picam.start()
            time.sleep(1.0)  # laisse l'auto-exposition se stabiliser
            print("Caméra : Picamera2")
        except Exception:
            self.picam = None
            self.cap = cv2.VideoCapture(device)
            self.cap.set(cv2.CAP_PROP_FRAME_WIDTH, width)
            self.cap.set(cv2.CAP_PROP_FRAME_HEIGHT, height)
            if not self.cap.isOpened():
                raise SystemExit(f"Impossible d'ouvrir la caméra (device {device}).")
            print(f"Caméra : OpenCV (device {device})")

    def read(self) -> np.ndarray:
        if self.picam is not None:
            # Le format "RGB888" de Picamera2 est en réalité rangé en BGR : directement utilisable par OpenCV.
            return self.picam.capture_array()
        ok, frame = self.cap.read()
        if not ok:
            raise RuntimeError("Lecture de la caméra impossible.")
        return frame

    def close(self) -> None:
        if self.picam is not None:
            self.picam.stop()
        if self.cap is not None:
            self.cap.release()


def motion_score(prev: np.ndarray, cur: np.ndarray) -> float:
    a = cv2.cvtColor(cv2.resize(prev, (160, 120)), cv2.COLOR_BGR2GRAY)
    b = cv2.cvtColor(cv2.resize(cur, (160, 120)), cv2.COLOR_BGR2GRAY)
    return float(np.mean(cv2.absdiff(a, b)))


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    add_data_arg(ap)
    ap.add_argument("--session", default=datetime.now().strftime("%Y-%m-%d_%H%M"), help="nom de la session")
    ap.add_argument("--source", default="real", help="sous-dossier de raw/ (défaut : real)")
    ap.add_argument("--count", type=int, default=100, help="nombre d'images à enregistrer")
    ap.add_argument("--interval", type=float, default=5.0, help="secondes entre deux images (mode périodique)")
    ap.add_argument("--motion", type=float, default=0.0,
                    help="si > 0 : n'enregistre que si le mouvement dépasse ce seuil (essayez 5 à 10)")
    ap.add_argument("--cooldown", type=float, default=1.5, help="délai minimal entre deux images en mode mouvement")
    ap.add_argument("--device", type=int, default=0)
    ap.add_argument("--width", type=int, default=1280)
    ap.add_argument("--height", type=int, default=720)
    args = ap.parse_args()

    out = Path(args.data) / "raw" / args.source / args.session
    out.mkdir(parents=True, exist_ok=True)
    cam = Camera(args.device, args.width, args.height)
    saved, last_save, prev = 0, 0.0, None
    print(f"Enregistrement dans {out} (Ctrl+C pour arrêter)")
    try:
        while saved < args.count:
            frame = cam.read()
            now = time.time()
            if args.motion > 0:
                moved = prev is not None and motion_score(prev, frame) > args.motion
                prev = frame
                take = moved and now - last_save >= args.cooldown
                time.sleep(0.1)
            else:
                take = now - last_save >= args.interval
            if take:
                name = f"{args.session}_{datetime.now().strftime('%H%M%S')}_{saved:04d}.jpg"
                cv2.imwrite(str(out / name), frame, [cv2.IMWRITE_JPEG_QUALITY, 95])
                saved, last_save = saved + 1, now
                print(f"[{saved}/{args.count}] {name}")
    except KeyboardInterrupt:
        print("\nArrêt demandé.")
    finally:
        cam.close()
    print(f"{saved} image(s) enregistrée(s). Étape suivante : annoter, puis lancer clean.py.")


if __name__ == "__main__":
    main()
