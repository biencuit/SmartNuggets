"""Fonctions communes aux scripts du jeu d'images SmartNuggets."""
from __future__ import annotations

import argparse
import hashlib
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent
IMG_EXT = {".jpg", ".jpeg", ".png"}


def add_data_arg(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--data",
        default=str(ROOT),
        help="dossier de travail contenant classes.yaml, raw/, yolo/ ... (défaut : dossier du script)",
    )


def load_config(data: Path) -> dict:
    with open(data / "classes.yaml", encoding="utf-8") as f:
        return yaml.safe_load(f)


def main_classes(cfg: dict) -> list[str]:
    """Classes principales : poule + prédateurs."""
    return list(cfg["groups"]["poule"]) + list(cfg["groups"]["predateur"])


def iter_images(root: Path):
    for p in sorted(root.rglob("*")):
        if p.is_file() and p.suffix.lower() in IMG_EXT:
            yield p


def file_md5(path: Path) -> str:
    h = hashlib.md5()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def read_labels(path: Path, n_classes: int) -> list[tuple[int, float, float, float, float]]:
    """Lit un fichier d'annotations YOLO. Lève ValueError si le format est invalide.

    Un fichier vide est valide : c'est une image sans objet ("porte vide").
    """
    rows = []
    for n, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        line = line.strip()
        if not line:
            continue
        parts = line.split()
        where = f"{path.name}:{n}"
        if len(parts) != 5:
            raise ValueError(f"{where}: 5 valeurs attendues, {len(parts)} trouvées")
        try:
            cls = int(parts[0])
            x, y, w, h = (float(v) for v in parts[1:])
        except ValueError:
            raise ValueError(f"{where}: valeurs non numériques") from None
        if not 0 <= cls < n_classes:
            raise ValueError(f"{where}: id de classe {cls} inconnu")
        if not all(0.0 <= v <= 1.0 for v in (x, y, w, h)) or w <= 0 or h <= 0:
            raise ValueError(f"{where}: coordonnées hors de [0, 1]")
        if x - w / 2 < -0.01 or x + w / 2 > 1.01 or y - h / 2 < -0.01 or y + h / 2 > 1.01:
            raise ValueError(f"{where}: boîte qui dépasse de l'image")
        rows.append((cls, x, y, w, h))
    return rows


def describe_origin(rel: Path, cfg: dict) -> tuple[str, str, str]:
    """Pour une image raw/<rel>, renvoie (source, origine, groupe).

    source : "real" ou "public" (1er dossier)
    origine: "real" ou "public/<nom>" (sert à documenter licences et sources)
    groupe : unité qui ne doit jamais être coupée entre train/val/test
    """
    parts = rel.parts
    source = parts[0] if len(parts) > 1 else "real"
    origin = "/".join(parts[:2]) if source in cfg.get("per_image_groups", []) and len(parts) > 2 else source
    if source in cfg.get("per_image_groups", []):
        group = "/".join(parts[:-1] + (rel.stem,))
    else:
        group = "/".join(parts[:-1]) or source
    return source, origin, group
