# SmartNuggets

[![CI](https://github.com/biencuit/SmartNuggets/actions/workflows/ci.yml/badge.svg)](https://github.com/biencuit/SmartNuggets/actions/workflows/ci.yml)

Projet d'intégration - EPHEC, Bac 3.

## Le projet

SmartNuggets est une porte de poulailler intelligente. L'idée est simple : la porte s'ouvre toute seule quand une poule veut entrer ou sortir, et reste fermée quand un prédateur traîne autour.

Concrètement :

- un capteur de présence réveille une caméra quand quelque chose s'approche de la porte ;
- la caméra reconnaît s'il s'agit d'une poule, et si c'est le cas la porte s'ouvre ;
- chaque passage est compté, ce qui permet de savoir combien de poules sont dans le poulailler et combien sont dehors ;
- si un renard (ou un autre prédateur) est détecté, la porte reste verrouillée et on reçoit une alerte ;
- une application permet de suivre tout ça : nombre de poules, historique, alertes, ouverture manuelle de la porte.

## Architecture

Schéma provisoire, il sera détaillé dans le wiki.

```
Capteur de présence -> Caméra -> Unité de traitement (détection)
                                        |
                  +---------------------+---------------------+
                  |                     |                     |
           Moteur de porte        Backend / API            Alertes
                                        |
                                   Application
```

## Contenu du dépôt

| Dossier | Contenu |
|---|---|
| `backend/` | API FastAPI + PostgreSQL (voir `backend/README.md`) |
| `frontend/` | Application web React (voir `frontend/README.md`) |
| `edge-coop/` | Code du Raspberry Pi du poulailler : liaison MQTT avec le serveur |
| `mosquitto/` | Configuration du broker MQTT (TLS, comptes, droits) |
| `Python-RP5/` | Commande du moteur de la porte |

## Intégration continue

À chaque pull request (et sur `main`), GitHub Actions lance `.github/workflows/ci.yml` :

- Python (backend et Raspberry Pi) : ruff, black, bandit et pip-audit ;
- backend : migrations Alembic et tests pytest sur une base PostgreSQL éphémère ;
- Raspberry Pi : tests pytest ;
- frontend : ESLint, Prettier, tests Vitest, build TypeScript/Vite et npm audit.

Une PR ne doit être fusionnée que si tous ces contrôles sont verts.

## Organisation

- Le backlog se trouve dans les issues et dans le GitHub Project du repo.
- La documentation est dans le wiki.

## Équipe

À compléter.
