#!/usr/bin/env bash
# Certificats TLS du broker MQTT quand le VPS n'a pas de nom de domaine (pas de Let's Encrypt).
# Crée une autorité de certification privée (une seule fois) et un certificat serveur pour
# l'IP ou le nom donné. Le Raspberry Pi doit recevoir ca.crt (MQTT_CA_CERT dans son .env).
#
#   bash scripts/mqtt-certs.sh 15.235.251.11
#
# La clé de la CA reste hors du dépôt (CA_DIR, par défaut ~/smartnuggets-ca).
set -euo pipefail

HOST="${1:?usage : $0 <ip-ou-domaine>}"
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
CA_DIR="${CA_DIR:-$HOME/smartnuggets-ca}"
OUT="$ROOT/mosquitto/certs"
DAYS=825

if [[ "$HOST" =~ ^[0-9.]+$ ]]; then SAN="IP:$HOST"; else SAN="DNS:$HOST"; fi

mkdir -p "$CA_DIR" "$OUT"
chmod 700 "$CA_DIR"

if [[ ! -f "$CA_DIR/ca.key" ]]; then
  echo "==> nouvelle autorité de certification dans $CA_DIR"
  openssl genpkey -algorithm EC -pkeyopt ec_paramgen_curve:P-256 -out "$CA_DIR/ca.key"
  openssl req -x509 -new -key "$CA_DIR/ca.key" -sha256 -days 3650 \
    -subj "/CN=SmartNuggets MQTT CA" -out "$CA_DIR/ca.crt"
fi

echo "==> certificat serveur pour $SAN ($DAYS jours)"
TMP="$(mktemp -d)"
trap 'rm -rf "$TMP"' EXIT
openssl genpkey -algorithm EC -pkeyopt ec_paramgen_curve:P-256 -out "$TMP/privkey.pem"
openssl req -new -key "$TMP/privkey.pem" -subj "/CN=$HOST" -out "$TMP/server.csr"
cat >"$TMP/ext.cnf" <<EXT
basicConstraints = CA:FALSE
keyUsage = digitalSignature, keyEncipherment
extendedKeyUsage = serverAuth
subjectAltName = $SAN
EXT
openssl x509 -req -in "$TMP/server.csr" -CA "$CA_DIR/ca.crt" -CAkey "$CA_DIR/ca.key" \
  -CAcreateserial -days "$DAYS" -sha256 -extfile "$TMP/ext.cnf" -out "$TMP/server.crt"

cat "$TMP/server.crt" "$CA_DIR/ca.crt" >"$OUT/fullchain.pem"
cp "$TMP/privkey.pem" "$OUT/privkey.pem"
cp "$CA_DIR/ca.crt" "$OUT/ca.crt"

# Le conteneur eclipse-mosquitto tourne avec l'utilisateur mosquitto (uid 1883).
sudo chown 1883:1883 "$OUT/fullchain.pem" "$OUT/privkey.pem" "$OUT/ca.crt"
sudo chmod 600 "$OUT/privkey.pem"
sudo chmod 644 "$OUT/fullchain.pem" "$OUT/ca.crt"

openssl x509 -in "$TMP/server.crt" -noout -subject -enddate -ext subjectAltName
echo "Certificat installé dans $OUT. Redémarrer le broker : docker compose -f docker-compose.prod.yml restart mosquitto"
