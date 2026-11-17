#!/usr/bin/env bash
# Lancé par certbot (en root) après chaque renouvellement du certificat Let's Encrypt de
# smartnuggets.be, environ tous les deux mois :
#   1. copie le certificat pour Mosquitto (son conteneur ne lit pas /etc/letsencrypt) ;
#   2. redémarre Mosquitto (les Raspberry Pi se reconnectent tout seuls) ;
#   3. recharge nginx, sans couper les visiteurs.
#
# Installé une seule fois (voir le wiki, page 16) :
#   sudo certbot reconfigure --cert-name smartnuggets.be --webroot -w /var/www/certbot \
#     --deploy-hook "bash /home/ubuntu/SmartNuggets/scripts/cert-hook.sh"
#
# À la main : sudo bash scripts/cert-hook.sh
set -euo pipefail

[[ $EUID -eq 0 ]] || { echo "À lancer en root : sudo bash $0" >&2; exit 1; }

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
# Dossier du certificat : donné par certbot, sinon celui de smartnuggets.be.
LIVE="${RENEWED_LINEAGE:-/etc/letsencrypt/live/smartnuggets.be}"
OUT="$ROOT/mosquitto/certs"
COMPOSE=(docker compose -f "$ROOT/docker-compose.prod.yml")

echo "==> copie du certificat pour Mosquitto"
install -d -m 755 "$OUT"
# Le conteneur eclipse-mosquitto lit les fichiers avec l'utilisateur mosquitto (uid 1883).
install -m 644 -o 1883 -g 1883 "$LIVE/fullchain.pem" "$OUT/fullchain.pem"
install -m 600 -o 1883 -g 1883 "$LIVE/privkey.pem" "$OUT/privkey.pem"

running() { "${COMPOSE[@]}" ps --services --status running | grep -qx "$1"; }

if running mosquitto; then
  echo "==> redémarrage de Mosquitto"
  "${COMPOSE[@]}" restart mosquitto
fi
if running nginx; then
  echo "==> rechargement de nginx"
  "${COMPOSE[@]}" exec -T nginx nginx -s reload
fi
