# Jeu d'images SmartNuggets (US-DET-3)

Outils pour constituer, nettoyer, séparer et **valider** le jeu d'images (poules, prédateurs, autres)
utilisé par l'entraînement du modèle (US-DET-4).

```
pip install -r requirements.txt
```

## Dossiers

```
dataset/
├── classes.yaml        classes, groupes et seuils d'acceptation (à relire en équipe)
├── sources.csv         origine + licence de chaque source d'images
├── raw/                images + annotations .txt (NON versionné)
│   ├── real/<session>/     photos du vrai poulailler  → 1 dossier par session
│   └── public/<source>/    images libres de droits    → 1 groupe par image
├── yolo/               export final (généré par split.py)
├── review/             images annotées pour la relecture (généré)
├── review_log.csv      journal de relecture croisée (à remplir)
├── DATASET_CARD.md     fiche du jeu, à copier dans le wiki (générée)
└── validation_report.json
```

## Procédure

| # | Étape | Commande |
|---|---|---|
| 1 | Capturer des images du poulailler (plusieurs sessions : matin, midi, soir, météo variée) | `python capture.py --session 2026-11-20_matin --interval 5 --count 100` |
| 2 | Ajouter des images publiques (renard, fouine, chat…) dans `raw/public/<source>/` et les lister dans `sources.csv` avec leur licence | à la main |
| 3 | Annoter (Roboflow, CVAT ou Label Studio), exporter en **YOLO** et déposer chaque `.txt` à côté de son image | outil d'annotation |
| 4 | Nettoyer (simulation, puis réel) | `python clean.py` puis `python clean.py --apply` |
| 5 | Séparer en train / val / test et exporter | `python split.py` |
| 6 | Préparer la relecture par un 2e membre, qui remplit `review_log.csv` (`reviewer`, `ok` = y/n) | `python review_sample.py` |
| 7 | **Valider l'US** | `python validate_dataset.py` |

Après correction d'annotations ou ajout d'images : refaire 4 → 7 (`python split.py --force` pour régénérer `yolo/`).

## Correspondance avec les critères d'acceptation

| Critère de l'US | Vérifié par |
|---|---|
| Les trois groupes sont représentés | `validate_dataset.py` (contrôles 3 et 4) |
| ~300 images par classe principale, ~200 « autres / porte vide » | `validate_dataset.py` (contrôles 2 et 3), seuils dans `classes.yaml` |
| ≥ 30 % d'images du vrai dispositif | `validate_dataset.py` (contrôle 5) |
| Annotations homogènes + relecture croisée | contrôle 1 (format) + `review_sample.py` / `review_log.csv` (contrôle 10) |
| Séparation train/val/test sans fuite | `split.py` (par groupe) + contrôles 6, 7 et 8 |
| Export au format attendu par US-DET-4 | `yolo/data.yaml` (contrôle 9) |
| Documentation dans le wiki | `DATASET_CARD.md` + `sources.csv` (contrôle 11) : copier la fiche dans le wiki |

`validate_dataset.py` renvoie le code 0 quand tout est ✅. Joignez `DATASET_CARD.md` à l'issue #7 pour la clôturer.

## Conventions d'annotation

- Une boîte serrée par animal visible, même partiellement masqué.
- Ne pas modifier l'ordre des classes de `classes.yaml` après le début de l'annotation.
- Image sans animal : fichier `.txt` **vide** (c'est ce qui compte comme « porte vide »).
- Les captures d'une même session restent ensemble : faites plusieurs sessions, jamais une seule très longue.

## Ce que les scripts ne font pas

Ils ne collectent ni n'annotent les images à votre place : l'US n'est « terminée » que quand les vrais volumes
(~300 images par classe, etc.) sont atteints. Le test `python tests/test_pipeline.py` vérifie seulement que la chaîne
fonctionne, sur des images synthétiques.

## Prochaine étape : US-DET-4

```
yolo train data=yolo/data.yaml model=yolov8n.pt imgsz=640 epochs=50
```
