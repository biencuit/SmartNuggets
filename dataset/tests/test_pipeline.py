"""Test de bout en bout sur des images synthétiques : clean -> split -> review -> validate.

Lancer : python tests/test_pipeline.py
"""
import csv
import random
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

import cv2
import numpy as np
import yaml

HERE = Path(__file__).resolve().parent.parent
PY = sys.executable


def run(script, data, *extra, expect=0):
    r = subprocess.run([PY, str(HERE / script), "--data", str(data), *extra], capture_output=True, text=True)
    assert r.returncode == expect, f"{script} code {r.returncode}\n{r.stdout}\n{r.stderr}"
    return r.stdout


def fake_image(path, rng, label_classes, ids):
    img = rng.integers(0, 255, (480, 640, 3), dtype=np.uint8)  # bruit = net, jamais en doublon
    lines = []
    for c in label_classes:
        x, y, w, h = rng.uniform(0.3, 0.7), rng.uniform(0.3, 0.7), rng.uniform(0.1, 0.3), rng.uniform(0.1, 0.3)
        lines.append(f"{ids[c]} {x:.4f} {y:.4f} {w:.4f} {h:.4f}")
    path.parent.mkdir(parents=True, exist_ok=True)
    cv2.imwrite(str(path), img)
    path.with_suffix(".txt").write_text("\n".join(lines) + ("\n" if lines else ""))


def build(tmp):
    cfg = yaml.safe_load((HERE / "classes.yaml").read_text(encoding="utf-8"))
    t = cfg["thresholds"]
    t.update(min_images_per_main_class=6, min_images_other_or_background=6, min_review_count=5)
    (tmp / "classes.yaml").write_text(yaml.safe_dump(cfg, allow_unicode=True), encoding="utf-8")
    ids = {n: i for i, n in enumerate(cfg["classes"])}
    rng = np.random.default_rng(0)
    rnd = random.Random(0)
    n = 0
    for s in range(12):  # 12 sessions réelles
        for k in range(6):
            cls = rnd.choice([["poule"], ["poule", "poule"], ["renard"], ["fouine"], ["chat"], ["humain"], []])
            fake_image(tmp / "raw/real" / f"session{s:02d}" / f"img{k}.jpg", rng, cls, ids)
            n += 1
    for k in range(40):  # sources publiques : 1 groupe par image
        cls = rnd.choice([["renard"], ["fouine"], ["chat"], ["poule"], ["chien"], []])
        fake_image(tmp / "raw/public/demo" / f"p{k}.jpg", rng, cls, ids)
    (tmp / "sources.csv").write_text(
        "origin,description,licence,url\nreal,photos équipe,propriété équipe,\npublic/demo,test,CC0,https://x\n", encoding="utf-8")
    return n


def main():
    tmp = Path(tempfile.mkdtemp())
    try:
        build(tmp)
        # image floue + doublon + image sans annotation à gérer
        shutil.copy(tmp / "raw/real/session00/img0.jpg", tmp / "raw/real/session00/copie.jpg")
        shutil.copy(tmp / "raw/real/session00/img0.txt", tmp / "raw/real/session00/copie.txt")
        cv2.imwrite(str(tmp / "raw/real/session00/floue.jpg"), np.full((480, 640, 3), 128, np.uint8))
        out = run("clean.py", tmp, "--apply")
        assert "doublon_exact" in out and "floue" in out, out
        assert (tmp / "rejected/floue/real/session00/floue.jpg").exists()
        # erreur d'annotation détectée par split
        bad = tmp / "raw/real/session01/img0.txt"
        good = bad.read_text()
        bad.write_text("99 0.5 0.5 0.1 0.1\n")
        out = run("split.py", tmp, expect=1)
        assert "inconnu" in out, out
        bad.write_text(good)
        run("split.py", tmp)
        # sans relecture ni seuils atteints : doit échouer
        run("validate_dataset.py", tmp, expect=1)
        run("review_sample.py", tmp)
        log = tmp / "review_log.csv"
        rows = list(csv.DictReader(open(log, encoding="utf-8")))
        for r in rows:
            r["reviewer"], r["ok"] = "Marie", "y"
        with open(log, "w", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(f, fieldnames=list(rows[0]))
            w.writeheader()
            w.writerows(rows)
        out = run("validate_dataset.py", tmp)
        assert "critères remplis" in out
        assert (tmp / "DATASET_CARD.md").exists() and (tmp / "validation_report.json").exists()
        print(out)
        print("TEST OK")
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


if __name__ == "__main__":
    main()
