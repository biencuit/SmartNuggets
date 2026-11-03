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
python -m app.seed        # données de démo : poulailler coop_01
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

## Endpoints (préfixe `/api/v1`)

| Méthode | Route | Description |
|---|---|---|
| GET | `/health` | L'API répond |
| GET | `/coops` | Liste des poulaillers |
| GET | `/coops/{coop_id}/status` | État actuel : porte, compteurs, batterie, dernière communication |
| GET | `/coops/{coop_id}/events?type=&limit=&offset=` | Historique paginé des passages et événements |
| GET | `/coops/{coop_id}/alerts?acknowledged=&limit=&offset=` | Alertes, de la plus récente à la plus ancienne |
| POST | `/coops/{coop_id}/alerts/{alert_id}/ack` | Marquer une alerte comme lue |
| GET | `/coops/{coop_id}/alerts/{alert_id}/image` | Photo associée à une alerte |
| POST | `/coops/{coop_id}/command` | Commande manuelle `OPEN`, `CLOSE` ou `CALIBRATE` (+ `inside_count`) |
| GET | `/coops/{coop_id}/stream` | Flux temps réel (Server-Sent Events) : `status`, `event`, `alert` |

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

## Organisation du code

```
app/
├── main.py          # create_app() : assemblage de l'application
├── config.py        # variables d'environnement (pydantic-settings)
├── db.py            # moteur SQLAlchemy async
├── models.py        # tables : users, coops, events, alerts
├── mqtt/            # topics, format des messages, client MQTT
├── schemas.py       # entrées / sorties de l'API (Pydantic)
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
