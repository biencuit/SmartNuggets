"""Sépare raw/ en train / val / test et exporte au format YOLO (compatible Ultralytics).

Règle clé : un groupe (session de capture, ou image isolée pour les sources publiques)
n'est jamais coupé entre plusieurs jeux. Sinon des images quasi identiques se retrouveraient
dans train ET test et l'évaluation du modèle (US-DET-4) serait faussée.

Le tirage est reproductible (--seed) et tient compte des classes pour que val et test
contiennent chacun des poules, des prédateurs et des images sans objet.

Prérequis : chaque image a un fichier .txt du même nom (annotations YOLO).
Un .txt vide = image sans objet ("porte vide").
"""
from __future__ import annotations

import argparse
import csv
import random
import shutil
from collections import Counter, defaultdict
from pathlib import Path

import yaml

from common import add_data_arg, describe_origin, file_md5, iter_images, load_config, read_labels

BG = "__fond__"


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    add_data_arg(ap)
    ap.add_argument("--seed", type=int, default=42)
    ap.add_argument("--force", action="store_true", help="écrase un export yolo/ existant")
    args = ap.parse_args()

    data = Path(args.data)
    cfg = load_config(data)
    names = cfg["classes"]
    ratios = cfg["thresholds"]["split_ratios"]
    raw, out = data / "raw", data / "yolo"
    if not raw.exists():
        raise SystemExit(f"Dossier introuvable : {raw}")
    if out.exists():
        if not args.force:
            raise SystemExit(f"{out} existe déjà. Utilisez --force pour le régénérer.")
        shutil.rmtree(out)

    # 1) Collecte + vérification des annotations
    items, problems = [], []
    for img in iter_images(raw):
        label = img.with_suffix(".txt")
        if not label.exists():
            problems.append(f"{img.relative_to(raw)} : pas de fichier d'annotation .txt")
            continue
        try:
            classes = {names[c] for c, *_ in read_labels(label, len(names))}
        except ValueError as e:
            problems.append(str(e))
            continue
        rel = img.relative_to(raw)
        source, origin, group = describe_origin(rel, cfg)
        items.append(dict(img=img, label=label, rel=rel, source=source, origin=origin, group=group, classes=classes))
    if problems:
        print(f"{len(problems)} problème(s) d'annotation :")
        for p in problems[:20]:
            print("  -", p)
        raise SystemExit("Corrigez les annotations avant de séparer le jeu.")
    if not items:
        raise SystemExit("Aucune image trouvée dans raw/.")

    # 2) Répartition par groupes, en équilibrant les classes
    groups: dict[str, list[dict]] = defaultdict(list)
    for it in items:
        groups[it["group"]].append(it)
    total: Counter = Counter()
    for it in items:
        total.update(it["classes"] or {BG})
    cur = {s: Counter() for s in ratios}
    rng = random.Random(args.seed)
    order = list(groups)
    rng.shuffle(order)
    order.sort(key=lambda g: -len(groups[g]))  # gros groupes d'abord, ordre aléatoire à taille égale
    assign: dict[str, str] = {}
    for g in order:
        gc: Counter = Counter()
        for it in groups[g]:
            gc.update(it["classes"] or {BG})

        def need(split: str) -> float:
            return sum(n * (ratios[split] * total[c] - cur[split][c]) / total[c] for c, n in gc.items())

        best = max(ratios, key=lambda s: (need(s), rng.random()))
        assign[g] = best
        cur[best].update(gc)

    biggest = max(len(v) for v in groups.values()) / len(items)
    if biggest > 0.5:
        print(f"Attention : un seul groupe contient {biggest:.0%} des images. "
              "Répartissez les captures en plusieurs sessions (raw/real/<session>/).")

    # 3) Export YOLO
    rows = []
    for split in ratios:
        (out / "images" / split).mkdir(parents=True, exist_ok=True)
        (out / "labels" / split).mkdir(parents=True, exist_ok=True)
    for it in items:
        split = assign[it["group"]]
        stem = "__".join(it["rel"].with_suffix("").parts)
        name = stem + it["img"].suffix.lower()
        shutil.copy2(it["img"], out / "images" / split / name)
        shutil.copy2(it["label"], out / "labels" / split / (stem + ".txt"))
        rows.append([name, split, it["source"], it["origin"], it["group"], file_md5(it["img"])])

    with open(out / "splits.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["image", "split", "source", "origin", "group", "md5"])
        w.writerows(rows)

    data_yaml = {
        "path": str(out.resolve()),
        "train": "images/train",
        "val": "images/val",
        "test": "images/test",
        "names": {i: n for i, n in enumerate(names)},
    }
    with open(out / "data.yaml", "w", encoding="utf-8") as f:
        yaml.safe_dump(data_yaml, f, allow_unicode=True, sort_keys=False)

    counts = Counter(r[1] for r in rows)
    print(f"{len(rows)} images exportées dans {out}")
    for s in ratios:
        print(f"  {s:5s}: {counts[s]:5d} ({counts[s] / len(rows):.0%})")
    print("Étape suivante : python review_sample.py, puis python validate_dataset.py")


if __name__ == "__main__":
    main()
