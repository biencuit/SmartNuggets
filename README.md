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
| `edge-coop/` | Code du Raspberry Pi du poulailler : liaison MQTT avec le serveur, prototype de la porte (`prototypes/`) |
| `mosquitto/` | Configuration du broker MQTT (TLS, comptes, droits) |
| `nginx/` | Image du serveur web (site React + reverse proxy de l'API) |
| `docs/` | Présentation, maquette et images |
| `scripts/` | Outils de développement et de déploiement (`dev.sh` : tout lancer en local) |

## Lancer le projet en local

Sous Linux ou WSL, une seule commande lance le broker MQTT, l'API, un faux Raspberry Pi
et l'application web :

```bash
sudo apt install -y mosquitto   # une seule fois
bash scripts/dev.sh             # --reset pour repartir d'une base neuve, --help pour les options
```

L'application est alors sur http://localhost:5173 (compte `demo@smartnuggets.be`,
mot de passe `poulailler` ; pour tester l'ajout d'un poulailler : `coop_02`, code
`DEMO-DEMO-0002`) et l'API sur http://localhost:8000/docs. Des touches permettent
de tester sans matériel : `p` coupe ou rallume le faux Pi, `b` simule une batterie faible
et une caméra en panne, `r` remet tout en ordre, `o`/`f` ouvrent ou ferment la porte
depuis l'API, `q` arrête tout. Le script crée les environnements Python au premier
lancement ; depuis WSL, il utilise le Node.js de Windows si besoin.

### Mode démo

```bash
bash scripts/dev.sh --demo
```

Le vrai programme du Raspberry Pi (`edge-coop/coop_app`) tourne sur du matériel simulé et
rejoue une journée en 2 minutes (`edge-coop/scenarios/journee.json`) : une poule fait
ouvrir la porte, quatre sortent, un renard fait fermer la porte (alerte avec photo), la
porte reste verrouillée, puis trois poules rentrent et la porte se ferme le soir avec une
poule dehors. Tout s'affiche en direct dans l'application. Pour montrer une vraie vidéo à
la place de l'image fixe : `DEMO_CAMERA=video:/chemin/poule.mp4 bash scripts/dev.sh --demo`
(il faut l'extra `video` d'edge-coop : `pip install -e "edge-coop[video]"`).

## Déploiement

Le serveur (VPS Ubuntu) fait tourner `docker-compose.prod.yml` : nginx (application web et
reverse proxy de l'API), l'API, PostgreSQL et le broker Mosquitto. L'application est en ligne
sur https://smartnuggets.be. Seuls les ports 80 (renvoie vers HTTPS), 443 (HTTPS) et 8883 (MQTT
en TLS, pour les Raspberry Pi) sont ouverts. Le certificat Let's Encrypt se renouvelle tout seul
(certbot).

Après chaque CI verte sur `main`, `.github/workflows/deploy.yml` se connecte au VPS et lance
`scripts/deploy.sh`. Installation complète du serveur : voir le wiki, pages 11 (Hébergement -
Déploiement) et 16 (Manuel d'installation).

Pour ajouter un nouveau Raspberry Pi, lancer `bash scripts/new-coop.sh coop_02` sur le VPS. Le
script affiche le `.env` à copier sur le Pi et le code d'appairage à écrire sur l'étiquette du
boîtier. L'éleveur tape ce code dans l'application pour ajouter le poulailler à son compte.

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
