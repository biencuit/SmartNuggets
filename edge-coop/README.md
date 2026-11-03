# Code embarqué du poulailler (Raspberry Pi)

## `mqtt_uplink` : liaison avec le serveur

Le Raspberry Pi est relié à Internet par câble RJ45 et publie directement sur le broker
MQTT du VPS, en TLS (port 8883). Topics et droits : voir `mosquitto/README.md`.

- **File d'attente locale** : chaque message passe par une base SQLite (`Outbox`). Si Internet
  ou le serveur tombe, les messages s'accumulent et repartent dans l'ordre dès le retour de
  la connexion, même après un redémarrage du Pi. Un message n'est retiré qu'après l'accusé
  de réception du broker.
- **État de connexion** : le Pi publie `online` (retenu) à chaque connexion ; s'il disparaît
  (câble, courant), le broker publie `offline` à sa place (Last Will).
- **Commandes** : une commande plus vieille que `COMMAND_MAX_AGE_S` (60 s) est ignorée, pour que
  la porte ne s'ouvre pas des heures après un clic ; une commande reçue deux fois n'est
  exécutée qu'une fois.

```python
from mqtt_uplink import MqttUplink, Outbox, UplinkConfig

config = UplinkConfig.from_env()          # voir .env.example
uplink = MqttUplink(config, Outbox(config.outbox_path), on_command=file_de_commandes.put)
uplink.start()

uplink.send_event("HEN_ENTRY", inside_count=9, trigger_source="AI_AUTO", ai_confidence=0.93)
uplink.send_alert("PREDATOR_DETECTED", "CRITICAL", ai_confidence=0.88, image=jpeg_bytes)
uplink.send_telemetry(battery_level=76, camera_ok=True)   # battement de cœur
```

**Battement de cœur** : envoyer une télémétrie au moins toutes les 5 minutes (batterie,
état de la caméra). Sans nouvelles pendant 15 minutes, l'application affiche le poulailler
« hors ligne » et crée une alerte.

`on_command` est appelé depuis le thread réseau : il doit rendre la main tout de suite
(par exemple en déposant la commande dans une file lue par le contrôleur de porte).

Démo sans le reste du code : `python -m mqtt_uplink --interval 30`.

## Installation et tests

```bash
cd edge-coop
python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
pytest --cov
ruff check . && black --check . && bandit -r mqtt_uplink
```
