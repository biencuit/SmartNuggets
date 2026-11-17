"""Prépare la relecture croisée des annotations par un second membre de l'équipe.

Tire un échantillon d'images dans yolo/, dessine les boîtes annotées dans review/
et crée review_log.csv. Le relecteur ouvre les images de review/ puis remplit,
pour chaque ligne du CSV : reviewer (son prénom), ok (y/n) et éventuellement comment.

Relancer le script complète l'échantillon sans effacer les lignes déjà relues.
"""
from __future__ import annotations

import argparse
import csv
import math
import random
from pathlib import Path

import cv2

from common import add_data_arg, load_config, read_labels

FIELDS = ["image", "split", "reviewer", "ok", "comment"]


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    add_data_arg(ap)
    ap.add_argument("--seed", type=int, default=7)
    args = ap.parse_args()

    data = Path(args.data)
    cfg = load_config(data)
    th = cfg["thresholds"]
    names = cfg["classes"]
    yolo, review = data / "yolo", data / "review"
    splits_csv = yolo / "splits.csv"
    if not splits_csv.exists():
        raise SystemExit("yolo/splits.csv introuvable : lancez d'abord split.py.")

    with open(splits_csv, encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    log_path = data / "review_log.csv"
    existing = []
    if log_path.exists():
        with open(log_path, encoding="utf-8") as f:
            existing = list(csv.DictReader(f))
    done = {r["image"] for r in existing}

    wanted = min(len(rows), max(th["min_review_count"], math.ceil(th["min_review_fraction"] * len(rows))))
    # marge de sécurité de 20 % : si le relecteur rejette ou saute des images, on a de quoi compléter
    wanted = min(len(rows), math.ceil(wanted * 1.2))
    candidates = [r for r in rows if r["image"] not in done]
    random.Random(args.seed).shuffle(candidates)
    new = candidates[: max(0, wanted - len(existing))]

    review.mkdir(exist_ok=True)
    for r in new:
        img_path = yolo / "images" / r["split"] / r["image"]
        lbl_path = yolo / "labels" / r["split"] / (Path(r["image"]).stem + ".txt")
        img = cv2.imread(str(img_path))
        if img is None:
            continue
        h, w = img.shape[:2]
        for cls, x, y, bw, bh in read_labels(lbl_path, len(names)):
            x1, y1 = int((x - bw / 2) * w), int((y - bh / 2) * h)
            x2, y2 = int((x + bw / 2) * w), int((y + bh / 2) * h)
            cv2.rectangle(img, (x1, y1), (x2, y2), (0, 255, 0), 2)
            cv2.putText(img, names[cls], (x1, max(15, y1 - 6)), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 0), 2)
        if not read_labels(lbl_path, len(names)):
            cv2.putText(img, "AUCUN OBJET (porte vide)", (10, 28), cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 200, 255), 2)
        cv2.imwrite(str(review / r["image"]), img)

    all_rows = existing + [{"image": r["image"], "split": r["split"], "reviewer": "", "ok": "", "comment": ""} for r in new]
    with open(log_path, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=FIELDS)
        w.writeheader()
        w.writerows(all_rows)
    print(f"{len(new)} image(s) ajoutée(s) à la relecture ({len(all_rows)} au total).")
    print(f"1) Ouvrez les images de {review}")
    print(f"2) Remplissez reviewer et ok (y/n) dans {log_path} ; corrigez les annotations marquées n")


if __name__ == "__main__":
    main()
