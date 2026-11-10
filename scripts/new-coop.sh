#!/usr/bin/env bash
# Ajouter un nouveau Raspberry Pi, sur le VPS (dans ~/SmartNuggets) :
#
#   bash scripts/new-coop.sh coop_02
#
# 1. crée le compte MQTT du Pi, avec un mot de passe aléatoire ;
# 2. enregistre le Pi dans la base et crée son code d'appairage ;
# 3. affiche le .env à copier sur le Pi et le code à écrire sur l'étiquette du boîtier.
#
# Le mot de passe et le code ne sont affichés qu'une seule fois : seuls leurs hash sont gardés.
#
#   bash scripts/new-coop.sh coop_02 --code-only
#
# ne fait que l'étape 2 : nouveau code pour un Pi pas encore ajouté à un compte (code perdu),
# ou Pi dont le compte MQTT a été créé à la main.
set -euo pipefail

usage() {
  echo "usage : $0 <identifiant> [--code-only]   (exemple : $0 coop_02)" >&2
  exit 1
}

COOP_ID="${1:-}"
MODE="${2:-}"
[[ -n "$COOP_ID" ]] || usage
[[ -z "$MODE" || "$MODE" == "--code-only" ]] || usage
[[ "$COOP_ID" =~ ^[A-Za-z0-9_-]{1,64}$ ]] || {
  echo "Identifiant invalide : lettres sans accent, chiffres, _ et - (64 caractères au maximum)" >&2
  exit 1
}

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"
COMPOSE=(docker compose -f docker-compose.prod.yml)
PASSWD=mosquitto/config/passwd
# Adresse du broker vue par le Pi.
MQTT_PUBLIC_HOST="${MQTT_PUBLIC_HOST:-smartnuggets.be}"

if [[ "$MODE" == "--code-only" ]]; then
  "${COMPOSE[@]}" exec -T backend python -m app.new_coop "$COOP_ID" --new-code
  exit 0
fi

[[ -f "$PASSWD" ]] || { echo "Fichier manquant : $PASSWD (voir le wiki, page 16)" >&2; exit 1; }
if sudo grep -q "^$COOP_ID:" "$PASSWD"; then
  echo "Le compte MQTT $COOP_ID existe déjà. Pour un nouveau code : $0 $COOP_ID --code-only" >&2
  exit 1
fi

echo "==> enregistrement du Pi dans la base"
REGISTERED="$("${COMPOSE[@]}" exec -T backend python -m app.new_coop "$COOP_ID")"

echo "==> compte MQTT $COOP_ID"
# 32 caractères hexadécimaux : facile à copier dans le .env du Pi.
MQTT_PASSWORD="$(openssl rand -hex 16)"
docker run --rm -u 0 -e COOP_ID="$COOP_ID" -e MQTT_PASSWORD="$MQTT_PASSWORD" \
  -v "$ROOT/mosquitto/config:/mosquitto/config" eclipse-mosquitto:2 \
  sh -c 'mosquitto_passwd -b /mosquitto/config/passwd "$COOP_ID" "$MQTT_PASSWORD"'
sudo chown 1883:1883 "$PASSWD"
sudo chmod 600 "$PASSWD"
# SIGHUP : le broker relit les mots de passe sans couper les Pi déjà connectés.
"${COMPOSE[@]}" kill -s SIGHUP mosquitto >/dev/null

cat <<EOF

$REGISTERED

1) Sur le Raspberry Pi, dans edge-coop/.env :

COOP_ID=$COOP_ID
MQTT_HOST=$MQTT_PUBLIC_HOST
MQTT_PORT=8883
MQTT_TLS=true
MQTT_CA_CERT=
MQTT_USERNAME=$COOP_ID
MQTT_PASSWORD=$MQTT_PASSWORD

2) Le code d'appairage ci-dessus va sur l'étiquette du boîtier. L'éleveur le tape dans
   « Ajouter un poulailler » ; il ne marche qu'une fois.

Ces secrets ne seront plus affichés.
EOF
