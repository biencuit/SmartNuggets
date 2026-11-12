# Code embarqué du poulailler (Raspberry Pi)

## `mqtt_uplink` : liaison avec le serveur

Le Raspberry Pi est relié à Internet par câble RJ45 et publie directement sur le broker
MQTT du VPS, en TLS (port 8883). Topics et droits : voir `mosquitto/README.md`.

**Installer un nouveau Pi** : sur le VPS, `bash scripts/new-coop.sh coop_02` affiche le `.env`
à copier sur le Pi (compte MQTT et mot de passe) et le code d'appairage à coller sur le
boîtier. L'éleveur tape ce code dans l'application pour ajouter le poulailler à son compte.
Le programme lit ses réglages dans les variables d'environnement, pas dans le fichier : les
charger avant de le lancer (`set -a; . ./.env; set +a; python -m coop_app`).

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
ruff check . && black --check . && bandit -r mqtt_uplink hardware ai_detector door_controller coop_app
```

## Couche matérielle (`hardware/`)

Le reste du code ne parle jamais directement aux GPIO : il passe par des interfaces
(`hardware/interfaces.py`) qui existent en deux versions.

| Interface | Raspberry Pi 5 | Simulateur (PC, tests) |
|---|---|---|
| `StepperMotor` : moteur de la porte | `gpio.stepper()` : 28BYJ-48 + ULN2003 (`HalfStepper`) | `mock.FakeStepper` |
| `Switch` : fins de course, barrières IR | `gpio.GpioSwitch` | `mock.FakeSwitch`, `mock.LimitSwitch` |
| `Switch` : capteur de présence PIR | `gpio.GpioMotionSensor` | `mock.FakeSwitch` |
| `Camera` | `camera.PiCamera` (Picamera2) | `camera.VideoCamera` (vidéo), `camera.FolderCamera`, `mock.FakeCamera` |

**Moteur 28BYJ-48.** Séquence de 8 demi-pas sur IN1 à IN4 de l'ULN2003, 4096 demi-pas par
tour de l'axe, au moins 1 ms entre deux pas (1,5 ms par défaut). Le moteur est alimenté en
5 V à part (pas par le 5 V du Pi), masse commune avec le Pi. `release()` coupe les bobines
à l'arrêt pour que le moteur ne chauffe pas.

**Raspberry Pi 5.** `RPi.GPIO` ne fonctionne pas sur le Pi 5 : on utilise `gpiozero`
(qui passe par `lgpio`). Installation : `pip install -e ".[pi]"` et
`sudo apt install python3-picamera2` pour la caméra.

Câblage par défaut (numéros BCM) :

| Élément | GPIO |
|---|---|
| ULN2003 IN1, IN2, IN3, IN4 | 5, 6, 13, 19 |
| Fin de course haut / bas | 23 / 24 |
| Barrière IR extérieure / intérieure | 27 / 22 |
| Capteur PIR | 17 |

## Détection d'image (`ai_detector/`)

Tout détecteur a une méthode `detect(frame) -> list[Detection]`, où une `Detection` est une
catégorie (`hen`, `predator`, `other`), une confiance entre 0 et 1 et un nom libre.

- `ScriptedDetector` : renvoie ce qu'on lui demande (tests, mode démo).
- Vrai modèle : écrire une classe avec `detect`, puis `DETECTOR=module:Classe` dans `.env`.
  Les poids du modèle (`*.pt`, `*.onnx`) et les jeux d'images (`datasets/`) restent hors de Git.
- `YoloDetector` (`ai_detector/yolo.py`, US-DET-2) : YOLO11-nano d'Ultralytics, entraîné sur
  COCO. Il n'y a pas de classe « poule » dans COCO : il garde la classe « bird » (n° 14) et
  renvoie une détection `hen` par oiseau vu.

  ```bash
  pip install -e ".[yolo]"
  # .env : DETECTOR=ai_detector.yolo:YoloDetector
  yolo export model=yolo11n.pt format=ncnn   # sur le Pi, puis YOLO_MODEL=yolo11n_ncnn_model
  python prototypes/detection_poule.py chemin/vers/images   # verdict et temps par image
  ```

  Limites : n'importe quel oiseau est pris pour une poule, le modèle nano rate certaines
  photos, et **aucun prédateur n'est reconnu** (prévu avec US-SECU-1). Un fine-tuning sur nos
  propres images corrigerait les deux premiers points.

## Programme du poulailler (`coop_app/`, `door_controller/`)

`python -m coop_app` relie le matériel, la détection, la porte et le serveur. Règles, dans
l'ordre de priorité :

1. **Prédateur vu** : la porte se ferme si elle est ouverte et refuse de s'ouvrir pendant
   `PREDATOR_LOCK_S` (même sur commande de l'application). Alerte avec photo.
2. **Nuit** (hors de `OPEN_FROM`-`CLOSE_AT`) : la porte se ferme et ne s'ouvre plus seule.
3. **Poule vue** (le PIR réveille la caméra) : la porte s'ouvre ; elle se referme quand
   aucune poule n'est passée depuis `AUTO_CLOSE_AFTER_S`.
4. **Commandes de l'application** : OPEN, CLOSE, CALIBRATE (correction du compteur).
5. **Comptage** : deux barrières IR dans l'encadrement donnent le sens de passage.

`door_controller/` ne dépend pas du matériel : `Door` (machine à états CLOSED, OPENING,
OPEN, CLOSING, ERROR, fins de course, anti-pincement), `PassageCounter` (sens de passage)
et `Schedule` (plage horaire). Au démarrage, la porte est recalée en bas.

```bash
HARDWARE=mock CAMERA=mock COOP_ID=coop_01 MQTT_HOST=127.0.0.1 MQTT_PORT=1883 MQTT_TLS=false \
  python -m coop_app       # sur un PC, avec le broker de scripts/dev.sh
```

## Mode démo

`python -m coop_app --demo scenarios/journee.json` (ou `bash scripts/dev.sh --demo` à la
racine) : le scénario pilote les capteurs simulés et le détecteur simulé, le reste du
programme est le vrai. Actions possibles : `hen`, `predator`, `exit`, `enter` (avec
`count`), `evening` (avance l'horloge jusqu'à `CLOSE_AT`), `morning`. Le test
`tests/test_demo.py` rejoue ce scénario en accéléré à chaque CI.

## Prototype de la porte

`prototypes/porte.py` (Diego, PR #32) : premier essai de commande de la porte au clavier
(`m` monter, `d` descendre, `s` stop), avec deux LED à la place du moteur. Il utilise
`gpiozero.Motor`, prévu pour un moteur à courant continu sur deux broches. Le moteur réel
(28BYJ-48 + ULN2003) est un moteur pas-à-pas sur quatre broches : ce prototype sert de
référence, il n'est pas utilisé par le reste du code.

```bash
python prototypes/porte.py   # sur le Raspberry Pi, avec gpiozero installé
```
