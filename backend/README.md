# Backend SmartNuggets

API REST (FastAPI) et base de données (PostgreSQL en production, SQLite en local) du projet.
Architecture et choix techniques : voir le wiki, pages 6 (Technologies) et 8 (Architecture).

## Installation

Python 3.11 ou plus récent.

```bash
cd backend
python -m venv .venv
source .venv/bin/activate        # Windows : .venv\Scripts\activate
pip install -e ".[dev]"
```

## Base de données

Le schéma est géré par Alembic (`alembic/versions/`). Sans fichier `.env`, la base est un
fichier SQLite local `smartnuggets.db`.

```bash
alembic upgrade head      # crée / met à jour le schéma
python -m app.seed        # compte demo@smartnuggets.be / poulailler + poulailler coop_01
                          # + Pi coop_02 à ajouter avec le code DEMO-DEMO-0002
```

Pour PostgreSQL, copier `.env.example` en `.env` et adapter `DATABASE_URL`.

Après une modification de `app/models.py` :

```bash
alembic revision --autogenerate -m "description"   # puis relire le fichier généré
alembic check                                      # vérifie que modèles et migrations concordent
```

## Lancer l'API

```bash
uvicorn app.main:create_app --factory --reload
```

- Documentation interactive (OpenAPI / Swagger) : http://localhost:8000/docs
- Schéma OpenAPI brut : http://localhost:8000/openapi.json

## Authentification

- `POST /api/v1/auth/register` crée un compte (`email`, `password` de 8 caractères minimum).
  Le mot de passe est haché avec **Argon2id** ; il n'est jamais stocké ni renvoyé.
- `POST /api/v1/auth/login` (formulaire `username` = email, `password`) renvoie un jeton JWT
  valable 24 h, à envoyer ensuite dans l'en-tête `Authorization: Bearer <jeton>`.
  Dans Swagger (`/docs`), le bouton **Authorize** fait la même chose.
- Toutes les routes `/coops` exigent ce jeton et ne donnent accès qu'aux poulaillers de
  l'utilisateur connecté (ceux d'un autre éleveur répondent `404`).
- Pour ajouter un poulailler à son compte, il faut l'identifiant du Pi **et** son code
  d'appairage (étiquette du boîtier). Le code ne marche qu'une fois et n'est gardé que sous
  forme de hash, comme un mot de passe. Si l'identifiant n'existe pas, si le code est faux ou
  si le poulailler est déjà sur un compte, la réponse est la même (`403`) : on ne peut pas
  deviner quels identifiants existent.
- Un nouveau Pi s'enregistre avec `python -m app.new_coop coop_02`, qui affiche son code
  (sur le VPS : `scripts/new-coop.sh`, qui crée aussi le compte MQTT). Code perdu avant
  d'avoir servi : `python -m app.new_coop coop_02 --new-code`.
- `/stream` et `/image` acceptent aussi `?token=<jeton>`, parce qu'`EventSource` et `<img>`
  ne peuvent pas envoyer d'en-tête.
- En production, `JWT_SECRET_KEY` doit être définie. Sans elle, une clé temporaire est générée
  et les sessions sont perdues à chaque redémarrage.

## Endpoints (préfixe `/api/v1`)

| Méthode | Route | Description |
|---|---|---|
| GET | `/health` | L'API répond (public) |
| POST | `/auth/register` | Créer un compte (public) |
| POST | `/auth/login` | Se connecter, renvoie un jeton (public) |
| GET | `/auth/me` | Profil de l'utilisateur connecté |
| GET | `/coops` | Poulaillers de l'utilisateur connecté |
| POST | `/coops` | Ajouter un poulailler à son compte : `id` du Raspberry Pi + `claim_code` (code d'appairage) |
| GET | `/coops/{coop_id}/status` | État actuel : porte, compteurs, batterie, dernière communication |
| GET | `/coops/{coop_id}/events?type=&limit=&offset=` | Historique paginé des passages et événements |
| GET | `/coops/{coop_id}/alerts?acknowledged=&limit=&offset=` | Alertes, de la plus récente à la plus ancienne |
| POST | `/coops/{coop_id}/alerts/{alert_id}/ack` | Marquer une alerte comme lue |
| GET | `/coops/{coop_id}/alerts/{alert_id}/image` | Photo associée à une alerte |
| POST | `/coops/{coop_id}/command` | Commande manuelle `OPEN`, `CLOSE` ou `CALIBRATE` (+ `inside_count`) |
| GET | `/coops/{coop_id}/stream` | Flux temps réel (Server-Sent Events) : `status` (aussi envoyé dès la connexion), `event`, `alert`, et `ping` toutes les 15 s sans autre message |

## Communication avec le Raspberry Pi (MQTT)

Le Pi du poulailler est relié à Internet par câble RJ45 et parle directement au broker
Mosquitto du VPS (topics et sécurité : voir `mosquitto/README.md`). Avec `MQTT_ENABLED=true`,
l'API lance au démarrage un client MQTT (`app/mqtt/worker.py`) qui :

- écoute `smartnuggets/+/telemetry`, `alerts` et `status`, met la base à jour
  (`app/services/ingestion.py`) et pousse chaque changement sur le flux SSE ;
- publie les commandes manuelles sur `smartnuggets/{coop_id}/commands` (QoS 1) ;
  si le broker est injoignable, `POST /command` répond `503` ;
- se reconnecte tout seul et garde une session persistante : les messages envoyés par les
  poulaillers pendant un redémarrage de l'API ne sont pas perdus.

Sans `MQTT_ENABLED`, l'API fonctionne seule et les commandes sont simplement gardées en mémoire.

## État du système (santé du Raspberry Pi)

`GET /coops/{id}/status` renvoie aussi :

- `online` : vrai si le Pi est connecté au broker (topic `status`, Last Will) **et** s'il a
  donné des nouvelles depuis moins de `DEVICE_OFFLINE_AFTER_S` (15 min par défaut) ;
- `battery` (%) et `camera_ok`, envoyés par le Pi dans sa télémétrie ;
- `last_seen_at` : heure du dernier message reçu.

Alertes automatiques :

| Alerte | Quand |
|---|---|
| `DEVICE_OFFLINE` | aucune nouvelle depuis 15 min (vérifié chaque minute, une alerte par coupure) |
| `LOW_BATTERY` | la batterie passe sous 20 % (une alerte par décharge, pas à chaque message) |

## Organisation du code

```
app/
├── main.py          # create_app() : assemblage de l'application
├── config.py        # variables d'environnement (pydantic-settings)
├── db.py            # moteur SQLAlchemy async
├── models.py        # tables : users, devices, coops, events, alerts
├── new_coop.py      # python -m app.new_coop : enregistrer un nouveau Raspberry Pi
├── mqtt/            # topics, format des messages, client MQTT
├── schemas.py       # entrées / sorties de l'API (Pydantic)
├── security.py      # hachage Argon2id, codes d'appairage, jetons JWT
├── routers/         # routes HTTP
├── services/        # logique métier
└── repositories/    # requêtes SQL (via l'ORM, jamais de SQL concaténé)
```

## Qualité

```bash
pytest --cov              # tests (SQLite temporaire)
ruff check . && black --check .
bandit -r app
```

Pour lancer les tests sur PostgreSQL : `TEST_DATABASE_URL=postgresql+asyncpg://... pytest`.
