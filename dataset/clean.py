"""Nettoyage de raw/ : images illisibles, trop petites, floues, doublons exacts ou quasi-doublons.

Par défaut le script ne fait que lister (simulation). Avec --apply, les images rejetées
(et leur fichier .txt) sont déplacées dans rejected/<raison>/ : rien n'est supprimé.
"""
from __future__ import annotations

import argparse
import shutil
from collections import Counter
from pathlib import Path

import cv2

from common import add_data_arg, file_md5, iter_images, load_config


def blur_score(img) -> float:
    """Variance du Laplacien (plus c'est bas, plus l'image est floue)."""
    g = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    h, w = g.shape
    scale = 640 / max(h, w)
    if scale < 1:
        g = cv2.resize(g, None, fx=scale, fy=scale, interpolation=cv2.INTER_AREA)
    return float(cv2.Laplacian(g, cv2.CV_64F).var())


def dhash(img, size: int = 8) -> int:
    """Empreinte perceptuelle 64 bits : deux images quasi identiques ont des empreintes proches."""
    g = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    g = cv2.resize(g, (size + 1, size), interpolation=cv2.INTER_AREA)
    bits = (g[:, 1:] > g[:, :-1]).flatten()
    return int("".join("1" if b else "0" for b in bits), 2)


def hamming(a: int, b: int) -> int:
    return bin(a ^ b).count("1")


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    add_data_arg(ap)
    ap.add_argument("--apply", action="store_true", help="déplace réellement les images rejetées")
    args = ap.parse_args()

    data = Path(args.data)
    cfg = load_config(data)
    th = cfg["thresholds"]
    raw, rejected = data / "raw", data / "rejected"
    if not raw.exists():
        raise SystemExit(f"Dossier introuvable : {raw}")

    kept_md5: set[str] = set()
    kept_hashes: list[int] = []
    stats: Counter = Counter()
    to_move: list[tuple[Path, str]] = []

    for img_path in iter_images(raw):
        img = cv2.imread(str(img_path))
        reason = None
        if img is None:
            reason = "illisible"
        else:
            h, w = img.shape[:2]
            if w < th["min_resolution"][0] or h < th["min_resolution"][1]:
                reason = "trop_petite"
            elif blur_score(img) < th["blur_threshold"]:
                reason = "floue"
            else:
                md5 = file_md5(img_path)
                if md5 in kept_md5:
                    reason = "doublon_exact"
                else:
                    dh = dhash(img)
                    if any(hamming(dh, k) <= th["near_duplicate_hamming"] for k in kept_hashes):
                        reason = "doublon_proche"
                    else:
                        kept_md5.add(md5)
                        kept_hashes.append(dh)
        if reason:
            to_move.append((img_path, reason))
            stats[reason] += 1
        else:
            stats["conservée"] += 1

    for img_path, reason in to_move:
        print(f"  {reason:15s} {img_path.relative_to(raw)}")
        if args.apply:
            rel = img_path.relative_to(raw)
            dest = rejected / reason / rel
            dest.parent.mkdir(parents=True, exist_ok=True)
            shutil.move(str(img_path), dest)
            label = img_path.with_suffix(".txt")
            if label.exists():
                shutil.move(str(label), dest.with_suffix(".txt"))

    print("\nBilan :", dict(stats))
    if to_move and not args.apply:
        print("Simulation seulement. Relancez avec --apply pour déplacer les images rejetées.")


if __name__ == "__main__":
    main()
