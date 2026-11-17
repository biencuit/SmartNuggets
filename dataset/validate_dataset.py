"""Valide le jeu d'images contre les critères d'acceptation de US-DET-3.

Produit :
  - un tableau de contrôle dans le terminal (✅ / ❌)
  - DATASET_CARD.md : fiche du jeu, à copier dans le wiki
  - validation_report.json : résultat brut (utile en CI ou comme preuve)

Code de sortie : 0 si tous les critères sont remplis, 1 sinon.
"""
from __future__ import annotations

import argparse
import csv
import json
import math
from collections import Counter, defaultdict
from datetime import date
from pathlib import Path

import yaml

from common import add_data_arg, load_config, main_classes, read_labels

OK_VALUES = {"y", "yes", "o", "oui"}
KO_VALUES = {"n", "no", "non"}


def read_csv(path: Path) -> list[dict]:
    with open(path, encoding="utf-8") as f:
        return list(csv.DictReader(f))


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    add_data_arg(ap)
    args = ap.parse_args()

    data = Path(args.data)
    cfg = load_config(data)
    th = cfg["thresholds"]
    th["split_ratios"] = {s: th["split_ratios"][s] for s in ("train", "val", "test")}  # ordre d'affichage stable
    names: list[str] = cfg["classes"]
    groups_cfg: dict = cfg["groups"]
    mains = main_classes(cfg)
    yolo = data / "yolo"

    results: list[dict] = []

    def check(name: str, ok: bool, detail: str) -> None:
        results.append({"critere": name, "ok": bool(ok), "detail": detail})

    splits_csv = yolo / "splits.csv"
    if not splits_csv.exists():
        raise SystemExit("yolo/splits.csv introuvable : lancez d'abord split.py.")
    rows = read_csv(splits_csv)
    total = len(rows)

    # --- Lecture de toutes les annotations --------------------------------------------------
    errors: list[str] = []
    img_classes: dict[str, set[str]] = {}
    instances: Counter = Counter()
    per_split_img: dict[str, Counter] = defaultdict(Counter)  # split -> classe -> nb d'images
    split_count: Counter = Counter()
    for r in rows:
        split, image = r["split"], r["image"]
        img_path = yolo / "images" / split / image
        lbl_path = yolo / "labels" / split / (Path(image).stem + ".txt")
        split_count[split] += 1
        if not img_path.exists():
            errors.append(f"{image} : image absente de yolo/images/{split}")
            continue
        if not lbl_path.exists():
            errors.append(f"{image} : annotation absente")
            continue
        try:
            labels = read_labels(lbl_path, len(names))
        except ValueError as e:
            errors.append(str(e))
            continue
        classes = {names[c] for c, *_ in labels}
        img_classes[image] = classes
        for c, *_ in labels:
            instances[names[c]] += 1
        for c in classes or {"__fond__"}:
            per_split_img[split][c] += 1

    # --- 1. Annotations valides -------------------------------------------------------------
    check("Toutes les images sont annotées, au bon format (une classe valide, boîtes dans l'image)",
          not errors,
          "OK" if not errors else f"{len(errors)} erreur(s), ex. : " + " | ".join(errors[:3]))

    # --- 2. Classes principales -------------------------------------------------------------
    img_per_class = Counter()
    for classes in img_classes.values():
        img_per_class.update(classes)
    need = th["min_images_per_main_class"]
    low = {c: img_per_class[c] for c in mains if img_per_class[c] < need}
    check(f"≥ {need} images annotées par classe principale ({', '.join(mains)})",
          not low,
          ", ".join(f"{c}={img_per_class[c]}" for c in mains) + ("" if not low else f"  → manque : {', '.join(low)}"))

    # --- 3. Autres + porte vide -------------------------------------------------------------
    autre = set(groups_cfg["autre"])
    n_background = sum(1 for c in img_classes.values() if not c)
    n_autre = sum(1 for c in img_classes.values() if c & autre)
    need_o = th["min_images_other_or_background"]
    check(f"≥ {need_o} images « autres / porte vide »",
          n_autre + n_background >= need_o,
          f"autres={n_autre}, porte vide (sans objet)={n_background}, total={n_autre + n_background}")

    # --- 4. Trois groupes représentés -------------------------------------------------------
    has_poule = any(c & set(groups_cfg["poule"]) for c in img_classes.values())
    has_pred = any(c & set(groups_cfg["predateur"]) for c in img_classes.values())
    has_autre = (n_autre + n_background) > 0
    check("Les trois groupes sont représentés (poule, prédateur, autre)",
          has_poule and has_pred and has_autre,
          f"poule={'oui' if has_poule else 'NON'}, prédateur={'oui' if has_pred else 'NON'}, autre={'oui' if has_autre else 'NON'}")

    # --- 5. Part d'images réelles -----------------------------------------------------------
    real = sum(1 for r in rows if r["source"] == "real")
    ratio_real = real / total if total else 0
    check(f"≥ {th['min_real_ratio']:.0%} d'images du vrai dispositif (caméra et angle réels)",
          ratio_real >= th["min_real_ratio"],
          f"{real}/{total} = {ratio_real:.0%}")

    # --- 6. Répartition ---------------------------------------------------------------------
    tol = th["split_tolerance"]
    bad = {s: split_count[s] / total for s, t in th["split_ratios"].items()
           if total and abs(split_count[s] / total - t) > tol}
    check(f"Répartition train/val/test proche de {'/'.join(str(round(v * 100)) for v in th['split_ratios'].values())} (±{tol:.0%})",
          not bad and total > 0,
          ", ".join(f"{s}={split_count[s]} ({split_count[s] / total:.0%})" for s in th["split_ratios"]) if total else "aucune image")

    # --- 7. Pas de fuite entre jeux ---------------------------------------------------------
    group_splits: dict[str, set[str]] = defaultdict(set)
    md5_splits: dict[str, set[str]] = defaultdict(set)
    for r in rows:
        group_splits[r["group"]].add(r["split"])
        md5_splits[r["md5"]].add(r["split"])
    leak_g = [g for g, s in group_splits.items() if len(s) > 1]
    leak_m = [m for m, s in md5_splits.items() if len(s) > 1]
    check("Aucune fuite entre jeux (même session ou même image dans plusieurs jeux)",
          not leak_g and not leak_m,
          "OK" if not (leak_g or leak_m) else f"{len(leak_g)} groupe(s) et {len(leak_m)} image(s) en double entre jeux")

    # --- 8. Classes principales dans val et test --------------------------------------------
    missing = [f"{c}/{s}" for s in ("val", "test") for c in mains if per_split_img[s][c] == 0]
    check("Chaque classe principale est présente dans val et test",
          not missing,
          "OK" if not missing else "absente de : " + ", ".join(missing))

    # --- 9. Export compatible ---------------------------------------------------------------
    dy = yolo / "data.yaml"
    export_ok, export_detail = False, "data.yaml absent"
    if dy.exists():
        d = yaml.safe_load(dy.read_text(encoding="utf-8"))
        got = [d["names"][i] for i in sorted(d["names"])]
        dirs_ok = all((yolo / d[k]).exists() for k in ("train", "val", "test"))
        export_ok = got == names and dirs_ok
        export_detail = "OK (format YOLO / Ultralytics)" if export_ok else "noms de classes ou dossiers incohérents avec classes.yaml"
    check("Export au format YOLO prêt pour US-DET-4 (yolo/data.yaml)", export_ok, export_detail)

    # --- 10. Relecture croisée --------------------------------------------------------------
    log = data / "review_log.csv"
    required = min(total, max(th["min_review_count"], math.ceil(th["min_review_fraction"] * total))) if total else 0
    if not log.exists():
        check("Relecture croisée d'un échantillon par un second membre", False, "review_log.csv absent (lancez review_sample.py)")
    else:
        lrows = read_csv(log)
        known = {r["image"] for r in rows}
        done = [r for r in lrows if r["image"] in known and (r.get("ok") or "").strip().lower() in OK_VALUES | KO_VALUES]
        rejected = [r for r in done if r["ok"].strip().lower() in KO_VALUES]
        anonymous = [r for r in done if not (r.get("reviewer") or "").strip()]
        good = len(done) >= required and not rejected and not anonymous
        detail = f"{len(done)}/{required} images relues"
        if rejected:
            detail += f", {len(rejected)} marquée(s) n à corriger puis à passer en y"
        if anonymous:
            detail += f", {len(anonymous)} ligne(s) sans nom de relecteur"
        check("Relecture croisée d'un échantillon par un second membre", good, detail)

    # --- 11. Documentation ------------------------------------------------------------------
    src_file = data / "sources.csv"
    origins = sorted({r["origin"] for r in rows})
    if not src_file.exists():
        check("Sources et licences documentées (sources.csv)", False, "sources.csv absent")
        sources: list[dict] = []
    else:
        sources = read_csv(src_file)
        by_origin = {s["origin"]: s for s in sources}
        undocumented = [o for o in origins if not (by_origin.get(o, {}).get("licence") or "").strip()]
        check("Sources et licences documentées (sources.csv)",
              not undocumented,
              "OK" if not undocumented else "licence manquante pour : " + ", ".join(undocumented))

    # --- Fiche du jeu -----------------------------------------------------------------------
    lines = [
        "# Jeu d'images SmartNuggets",
        "",
        f"_Généré le {date.today().isoformat()} par `validate_dataset.py` (US-DET-3)._",
        "",
        f"**{total} images** · format YOLO · classes : {', '.join(names)}",
        "",
        "## Répartition",
        "",
        "| Jeu | Images | Part |",
        "|---|---:|---:|",
    ]
    for s in th["split_ratios"]:
        lines.append(f"| {s} | {split_count[s]} | {split_count[s] / total:.0%} |" if total else f"| {s} | 0 | - |")
    lines += ["", "## Classes", "", "| Classe | Groupe | Images | Instances | train | val | test |", "|---|---|---:|---:|---:|---:|---:|"]
    group_of = {c: g for g, cl in groups_cfg.items() for c in cl}
    for c in names:
        lines.append(f"| {c} | {group_of.get(c, '-')} | {img_per_class[c]} | {instances[c]} | "
                     f"{per_split_img['train'][c]} | {per_split_img['val'][c]} | {per_split_img['test'][c]} |")
    lines.append(f"| _porte vide (sans objet)_ | autre | {n_background} | 0 | "
                 f"{per_split_img['train']['__fond__']} | {per_split_img['val']['__fond__']} | {per_split_img['test']['__fond__']} |")
    origin_count = Counter(r["origin"] for r in rows)
    by_origin = {s["origin"]: s for s in sources}
    lines += ["", "## Sources et licences", "", "| Origine | Images | Description | Licence | Lien |", "|---|---:|---|---|---|"]
    for o in origins:
        s = by_origin.get(o, {})
        lines.append(f"| {o} | {origin_count[o]} | {s.get('description', '')} | {s.get('licence', '')} | {s.get('url', '')} |")
    lines += [
        "",
        f"Images du vrai dispositif : {real}/{total} ({ratio_real:.0%}).",
        "",
        "## Conventions d'annotation",
        "",
        "- Une boîte englobante serrée par animal visible, même partiellement.",
        "- Format YOLO : `classe x_centre y_centre largeur hauteur`, valeurs normalisées entre 0 et 1.",
        "- Image sans animal : fichier `.txt` vide (« porte vide »).",
        "- Animal trop flou ou trop petit pour être identifié : ne pas annoter, ou retirer l'image.",
        "- Une session de capture reste entièrement dans un seul jeu (train, val ou test).",
        "",
        "## Contrôles US-DET-3",
        "",
        "| | Critère | Détail |",
        "|---|---|---|",
    ]
    for r in results:
        lines.append(f"| {'✅' if r['ok'] else '❌'} | {r['critere']} | {r['detail']} |")
    (data / "DATASET_CARD.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    (data / "validation_report.json").write_text(json.dumps(
        {"date": date.today().isoformat(), "images": total, "tous_criteres_ok": all(r["ok"] for r in results), "criteres": results},
        ensure_ascii=False, indent=2), encoding="utf-8")

    # --- Affichage --------------------------------------------------------------------------
    print(f"\nValidation US-DET-3 : {total} images\n")
    for r in results:
        print(f"{'✅' if r['ok'] else '❌'} {r['critere']}\n     {r['detail']}")
    n_ok = sum(r["ok"] for r in results)
    print(f"\n{n_ok}/{len(results)} critères remplis.")
    print("Fiche du jeu : DATASET_CARD.md  ·  Rapport : validation_report.json")
    raise SystemExit(0 if n_ok == len(results) else 1)


if __name__ == "__main__":
    main()
