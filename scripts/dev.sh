#!/usr/bin/env bash
# Lance tout SmartNuggets en local pour tester : broker MQTT, API, faux Raspberry Pi
# et application web. Ctrl+C (ou la touche q) arrête tout.
#
#   bash scripts/dev.sh              tout lancer
#   bash scripts/dev.sh --sans-pi    sans le faux Pi (pour brancher le vrai)
#   bash scripts/dev.sh --sans-web   sans l'application web
#   bash scripts/dev.sh --reset      repartir d'une base de démo neuve
#   bash scripts/dev.sh --demo       le vrai programme du Pi rejoue une journée (scénario)
#
# Prévu pour Linux / WSL. Il faut Python 3.11+, Mosquitto (sudo apt install mosquitto)
# et Node.js (celui de Windows convient depuis WSL). Tout ce qui est généré (base SQLite,
# config du broker, file d'attente du Pi, photos) va dans le dossier .dev/ (ignoré par git).
#
# Variables utiles : API_PORT (8000), MQTT_PORT (1883), DEVICE_OFFLINE_AFTER_S (60),
# MOSQUITTO (chemin du binaire), SN_BACKEND_VENV et SN_EDGE_VENV (environnements Python),
# DEMO_SCENARIO (scénario de --demo) et DEMO_CAMERA (ex. video:/chemin/poule.mp4).

set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
STATE="$ROOT/.dev"
API_PORT="${API_PORT:-8000}"
MQTT_PORT="${MQTT_PORT:-1883}"
WEB_PORT=5173
OFFLINE_AFTER_S="${DEVICE_OFFLINE_AFTER_S:-60}"
COOP_ID="coop_01"
DEMO_EMAIL="demo@smartnuggets.be"
DEMO_PASSWORD="poulailler" # compte de démo créé par app.seed, local uniquement
DEMO_FREE_COOP="coop_02"   # Pi de démo pas encore sur un compte (app.seed)
DEMO_CLAIM_CODE="DEMO-DEMO-0002"
API_URL="http://127.0.0.1:$API_PORT/api/v1"

WITH_PI=1
WITH_WEB=1
RESET=0
DEMO=0
DEMO_SCENARIO="${DEMO_SCENARIO:-scenarios/journee.json}"
for arg in "$@"; do
  case "$arg" in
    --sans-pi) WITH_PI=0 ;;
    --sans-web) WITH_WEB=0 ;;
    --reset) RESET=1 ;;
    --demo) DEMO=1 RESET=1 ;;
    -h | --help)
      sed -n '2,17p' "${BASH_SOURCE[0]}" | sed 's/^# \{0,1\}//'
      exit 0
      ;;
    *)
      echo "Option inconnue : $arg (voir --help)" >&2
      exit 2
      ;;
  esac
done

# ---------------------------------------------------------------------------- affichage

if [[ -t 1 ]]; then
  BOLD=$'\e[1m' DIM=$'\e[2m' RED=$'\e[31m' GREEN=$'\e[32m' YELLOW=$'\e[33m'
  BLUE=$'\e[34m' MAGENTA=$'\e[35m' RESET_COLOR=$'\e[0m'
else
  BOLD="" DIM="" RED="" GREEN="" YELLOW="" BLUE="" MAGENTA="" RESET_COLOR=""
fi

say() { printf '%s==> %s%s\n' "$BOLD$YELLOW" "$*" "$RESET_COLOR"; }
fail() {
  printf '%sErreur : %s%s\n' "$BOLD$RED" "$*" "$RESET_COLOR" >&2
  exit 1
}

# Préfixe chaque ligne de sortie d'un service : [api] ..., [pi] ...
prefix() { awk -v p="$1" '{ print p $0; fflush() }'; }

port_open() { (exec 3<>"/dev/tcp/127.0.0.1/$1") 2>/dev/null; }

# ---------------------------------------------------------------------------- prérequis

find_venv() { # $1 : choix imposé (peut être vide), $2... : emplacements possibles
  local override="$1" dir
  shift
  if [[ -n "$override" ]]; then
    echo "$override"
    return
  fi
  for dir in "$@"; do
    if [[ -x "$dir/bin/python" ]]; then
      echo "$dir"
      return
    fi
  done
}

# Crée l'environnement Python si besoin et (ré)installe les dépendances quand
# pyproject.toml a changé depuis la dernière installation.
ensure_venv() { # $1 : dossier de l'environnement, $2 : projet (backend ou edge-coop)
  local venv="$1" project="$ROOT/$2"
  local stamp="$venv/.smartnuggets-stamp"
  local wanted
  wanted="$(cksum <"$project/pyproject.toml")"
  if [[ ! -x "$venv/bin/python" ]]; then
    say "Création de l'environnement Python de $2 ($venv)"
    if command -v uv >/dev/null; then
      uv venv --quiet --python 3.11 "$venv"
    else
      python3 -m venv "$venv" || fail "impossible de créer $venv (installe uv ou python3-venv)"
    fi
  fi
  if [[ ! -f "$stamp" || "$(cat "$stamp")" != "$wanted" ]]; then
    say "Installation des dépendances de $2"
    if command -v uv >/dev/null; then
      uv pip install --quiet --python "$venv/bin/python" -e "$project[dev]"
    else
      "$venv/bin/python" -m pip install --quiet -e "$project[dev]"
    fi
    echo "$wanted" >"$stamp"
  fi
}

BACKEND_VENV="$(find_venv "${SN_BACKEND_VENV:-}" "$ROOT/backend/.venv" "$HOME/.venvs/sn-backend")"
EDGE_VENV="$(find_venv "${SN_EDGE_VENV:-}" "$ROOT/edge-coop/.venv" "$HOME/.venvs/sn-edge")"
# Aucun environnement trouvé : on le crée hors du dépôt (bien plus rapide sous WSL).
[[ -n "$BACKEND_VENV" ]] || BACKEND_VENV="$HOME/.venvs/sn-backend"
[[ -n "$EDGE_VENV" ]] || EDGE_VENV="$HOME/.venvs/sn-edge"
ensure_venv "$BACKEND_VENV" backend
ensure_venv "$EDGE_VENV" edge-coop
API_PY="$BACKEND_VENV/bin/python"
EDGE_PY="$EDGE_VENV/bin/python"

MOSQUITTO="${MOSQUITTO:-$(command -v mosquitto || true)}"
if [[ -z "$MOSQUITTO" && -x /usr/sbin/mosquitto ]]; then
  MOSQUITTO=/usr/sbin/mosquitto
fi

NODE=""
if ((WITH_WEB)); then
  NODE="$(command -v node || command -v node.exe || true)"
  [[ -n "$NODE" ]] || fail "Node.js introuvable (ou lance avec --sans-web)"
  if [[ ! -d "$ROOT/frontend/node_modules" ]]; then
    say "Installation des dépendances du frontend (npm install)"
    NPM="$(command -v npm || command -v npm.cmd || true)"
    [[ -n "$NPM" ]] || fail "npm introuvable"
    (cd "$ROOT/frontend" && "$NPM" install)
  fi
fi

port_open "$API_PORT" && fail "le port $API_PORT est déjà pris (une API lancée à la main ?)"

mkdir -p "$STATE"
if ((RESET)); then
  say "Remise à zéro des données de démo"
  rm -rf "$STATE/smartnuggets.db" "$STATE/outbox.db" "$STATE/media"
fi

# Clé de signature des jetons, gardée d'un lancement à l'autre pour ne pas devoir se
# reconnecter à chaque redémarrage de l'API.
if [[ ! -s "$STATE/jwt_secret" ]]; then
  (umask 077 && "$API_PY" -c 'import secrets; print(secrets.token_urlsafe(48))' >"$STATE/jwt_secret")
fi

export PYTHONUNBUFFERED=1
export DATABASE_URL="sqlite+aiosqlite:///$STATE/smartnuggets.db"
export JWT_SECRET_KEY
JWT_SECRET_KEY="$(cat "$STATE/jwt_secret")"

# ---------------------------------------------------------------------------- arrêt

BROKER_PID="" API_PID="" PI_PID="" WEB_PID=""

stop_pid() { # $1 : PID ; laisse 5 s au processus pour s'arrêter proprement
  local pid="$1" i
  [[ -n "$pid" ]] || return 0
  kill -TERM "$pid" 2>/dev/null || return 0
  for i in {1..50}; do
    kill -0 "$pid" 2>/dev/null || break
    sleep 0.1
  done
  kill -KILL "$pid" 2>/dev/null || true
  wait "$pid" 2>/dev/null || true
}

cleanup() {
  trap - EXIT INT TERM
  if [[ -n "$BROKER_PID$API_PID$PI_PID$WEB_PID" ]]; then
    echo
    say "Arrêt…"
  fi
  stop_pid "$PI_PID"
  stop_pid "$WEB_PID"
  stop_pid "$API_PID"
  stop_pid "$BROKER_PID"
  if [[ -t 0 ]]; then stty echo 2>/dev/null || true; fi
}
trap cleanup EXIT
trap 'exit 130' INT TERM

# ---------------------------------------------------------------------------- services

start_broker() {
  if port_open "$MQTT_PORT"; then
    say "Un broker MQTT tourne déjà sur le port $MQTT_PORT : je l'utilise"
    return
  fi
  [[ -n "$MOSQUITTO" ]] || fail "Mosquitto n'est pas installé : sudo apt install -y mosquitto"
  # Broker de développement : local uniquement, sans mot de passe et sans persistance
  # (il redémarre avec le script). La configuration du VPS (TLS, comptes, droits) est
  # dans mosquitto/config/.
  cat >"$STATE/mosquitto.conf" <<EOF
listener $MQTT_PORT 127.0.0.1
allow_anonymous true
persistence false
log_dest stdout
log_type error
log_type warning
log_type notice
log_timestamp_format %H:%M:%S
EOF
  say "Démarrage du broker MQTT (port $MQTT_PORT)"
  "$MOSQUITTO" -c "$STATE/mosquitto.conf" > >(prefix "$DIM[mqtt]$RESET_COLOR ") 2>&1 &
  BROKER_PID=$!
  local i
  for i in {1..50}; do
    port_open "$MQTT_PORT" && return
    kill -0 "$BROKER_PID" 2>/dev/null || fail "le broker MQTT n'a pas démarré"
    sleep 0.1
  done
  fail "le broker MQTT ne répond pas sur le port $MQTT_PORT"
}

start_api() {
  say "Base de données (migrations + données de démo)"
  (cd "$ROOT/backend" && "$API_PY" -m alembic upgrade head && "$API_PY" -m app.seed) 2>&1 |
    prefix "$BLUE[api]$RESET_COLOR " || fail "échec des migrations ou des données de démo"
  say "Démarrage de l'API (port $API_PORT)"
  (
    cd "$ROOT/backend"
    exec env MQTT_ENABLED=true MQTT_HOST=127.0.0.1 MQTT_PORT="$MQTT_PORT" MQTT_TLS=false \
      MEDIA_DIR="$STATE/media" DEVICE_OFFLINE_AFTER_S="$OFFLINE_AFTER_S" \
      HEALTH_CHECK_INTERVAL_S=10 \
      "$API_PY" -m uvicorn app.main:create_app --factory --host 127.0.0.1 --port "$API_PORT"
  ) > >(prefix "$BLUE[api]$RESET_COLOR ") 2>&1 &
  API_PID=$!
  local i
  for i in {1..100}; do
    curl -sf "$API_URL/health" >/dev/null 2>&1 && return
    kill -0 "$API_PID" 2>/dev/null || fail "l'API s'est arrêtée au démarrage (voir les lignes [api])"
    sleep 0.2
  done
  fail "l'API ne répond pas sur le port $API_PORT"
}

start_pi() {
  if ((DEMO)); then
    # Le vrai programme du Pi (porte, comptage, règles) sur du matériel simulé, piloté par
    # un scénario. Délais raccourcis pour que la journée tienne en 2 minutes.
    (
      cd "$ROOT/edge-coop"
      exec env COOP_ID="$COOP_ID" MQTT_HOST=127.0.0.1 MQTT_PORT="$MQTT_PORT" MQTT_TLS=false \
        OUTBOX_PATH="$STATE/outbox.db" HARDWARE=mock CAMERA="${DEMO_CAMERA:-mock}" \
        STEP_DELAY_S=0.001 DOOR_TRAVEL_STEPS=2048 PREDATOR_LOCK_S=30 AUTO_CLOSE_AFTER_S=600 \
        HEARTBEAT_S=10 INSIDE_AT_START=10 \
        "$EDGE_PY" -m coop_app --demo "$DEMO_SCENARIO"
    ) > >(prefix "$GREEN[pi]$RESET_COLOR ") 2>&1 &
    PI_PID=$!
    return
  fi
  (
    cd "$ROOT/edge-coop"
    exec env COOP_ID="$COOP_ID" MQTT_HOST=127.0.0.1 MQTT_PORT="$MQTT_PORT" MQTT_TLS=false \
      OUTBOX_PATH="$STATE/outbox.db" \
      "$EDGE_PY" -m mqtt_uplink --interval 10 --inside 7
  ) > >(prefix "$GREEN[pi]$RESET_COLOR ") 2>&1 &
  PI_PID=$!
}

start_web() {
  # Vite lancé directement (sans npm) : un seul processus, facile à arrêter, même quand
  # c'est le Node de Windows qui tourne depuis WSL.
  say "Démarrage de l'application web (port $WEB_PORT)"
  (
    cd "$ROOT/frontend"
    exec "$NODE" node_modules/vite/bin/vite.js --port "$WEB_PORT" --strictPort
  ) > >(prefix "$MAGENTA[web]$RESET_COLOR ") 2>&1 &
  WEB_PID=$!
}

# ---------------------------------------------------------------------------- actions

publish() { # $1 : canal (telemetry, alerts…), $2 : JSON
  "$EDGE_PY" - "smartnuggets/$COOP_ID/$1" "$2" "$MQTT_PORT" <<'PY'
import sys

from paho.mqtt import publish

publish.single(sys.argv[1], sys.argv[2], qos=1, hostname="127.0.0.1", port=int(sys.argv[3]))
PY
}

now_utc() { date -u +%Y-%m-%dT%H:%M:%SZ; }

TOKEN=""
api_command() { # $1 : OPEN ou CLOSE
  if [[ -z "$TOKEN" ]]; then
    TOKEN="$(curl -sf "$API_URL/auth/login" \
      --data-urlencode "username=$DEMO_EMAIL" --data-urlencode "password=$DEMO_PASSWORD" |
      "$API_PY" -c 'import json, sys; print(json.load(sys.stdin)["access_token"])')" ||
      {
        TOKEN=""
        say "Connexion à l'API impossible"
        return
      }
  fi
  local code
  code="$(curl -s -o /dev/null -w '%{http_code}' "$API_URL/coops/$COOP_ID/command" \
    -H "Authorization: Bearer $TOKEN" -H 'Content-Type: application/json' \
    -d "{\"action\": \"$1\"}")"
  case "$code" in
    202) say "Commande $1 envoyée (le faux Pi doit afficher « Commande reçue : $1 »)" ;;
    401) TOKEN="" && say "Session expirée, réessaie" ;;
    503) say "Commande $1 refusée : l'API n'est pas connectée au broker" ;;
    *) say "Commande $1 : réponse HTTP $code" ;;
  esac
}

toggle_pi() {
  if [[ -n "$PI_PID" ]] && kill -0 "$PI_PID" 2>/dev/null; then
    # SIGKILL : comme un câble arraché, le Pi ne dit pas au revoir. Le broker publie
    # alors son Last Will (offline) et l'application passe à « Hors ligne ».
    kill -KILL "$PI_PID" 2>/dev/null || true
    wait "$PI_PID" 2>/dev/null || true
    PI_PID=""
    say "Faux Pi coupé : « Hors ligne » tout de suite, alerte DEVICE_OFFLINE après ${OFFLINE_AFTER_S} s"
  else
    say "Faux Pi rallumé"
    start_pi
  fi
}

menu() {
  cat <<EOF

${BOLD}SmartNuggets tourne en local${RESET_COLOR}
  Application : http://localhost:$WEB_PORT   (compte $DEMO_EMAIL / $DEMO_PASSWORD)
  Poulailler à ajouter : $DEMO_FREE_COOP, code d'appairage $DEMO_CLAIM_CODE
  API (Swagger) : http://localhost:$API_PORT/docs
  Broker MQTT : localhost:$MQTT_PORT (sans mot de passe)

${BOLD}Touches${RESET_COLOR}
  p  couper / rallumer le faux Raspberry Pi (simule un câble débranché)
  b  batterie faible (15 %) et caméra en panne
  r  batterie pleine (95 %) et caméra OK
  o  ouvrir la porte depuis l'API     f  fermer la porte
  h  revoir cette aide                q  tout arrêter

EOF
}

handle_key() {
  case "$1" in
    p | P) toggle_pi ;;
    b | B)
      publish telemetry "{\"sent_at\": \"$(now_utc)\", \"battery_level\": 15, \"camera_ok\": false}"
      say "Télémétrie envoyée : batterie 15 %, caméra en panne (+ alerte LOW_BATTERY)"
      ;;
    r | R)
      publish telemetry "{\"sent_at\": \"$(now_utc)\", \"battery_level\": 95, \"camera_ok\": true}"
      say "Télémétrie envoyée : batterie 95 %, caméra OK"
      ;;
    o | O) api_command OPEN ;;
    f | F) api_command CLOSE ;;
    h | H | '?') menu ;;
    q | Q) exit 0 ;;
    '') ;;
    *) say "Touche inconnue : $1 (h pour l'aide)" ;;
  esac
}

# ---------------------------------------------------------------------------- lancement

start_broker
start_api
((WITH_PI)) && start_pi
((WITH_WEB)) && start_web
sleep 1
menu

KEYS=1
while true; do
  if ! kill -0 "$API_PID" 2>/dev/null; then
    fail "l'API s'est arrêtée (voir les lignes [api])"
  fi
  if [[ -n "$BROKER_PID" ]] && ! kill -0 "$BROKER_PID" 2>/dev/null; then
    fail "le broker MQTT s'est arrêté (voir les lignes [mqtt])"
  fi
  if [[ -n "$PI_PID" ]] && ! kill -0 "$PI_PID" 2>/dev/null; then
    wait "$PI_PID" 2>/dev/null || true
    PI_PID=""
    say "Le faux Pi s'est arrêté (touche p pour le relancer)"
  fi
  if [[ -n "$WEB_PID" ]] && ! kill -0 "$WEB_PID" 2>/dev/null; then
    wait "$WEB_PID" 2>/dev/null || true
    WEB_PID=""
    say "L'application web s'est arrêtée (port $WEB_PORT déjà pris ? voir les lignes [web])"
  fi

  if ((KEYS)); then
    key=""
    if read -rsn1 -t 1 key; then
      handle_key "$key"
    elif (($? <= 128)); then
      KEYS=0 # plus d'entrée clavier (stdin fermé) : on attend simplement Ctrl+C
    fi
  else
    sleep 1
  fi
done
