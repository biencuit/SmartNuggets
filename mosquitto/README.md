# Broker MQTT (Mosquitto)

Relie les Raspberry Pi des poulaillers (connectés à Internet par câble RJ45) à l'API.

| Topic | Sens | Contenu |
|---|---|---|
| `smartnuggets/{coop_id}/telemetry` | Pi → API, QoS 1 | état de la porte, compteur, batterie, événement éventuel |
| `smartnuggets/{coop_id}/alerts` | Pi → API, QoS 1 | alerte (prédateur, porte bloquée…) + photo JPEG/WebP en base64 |
| `smartnuggets/{coop_id}/status` | Pi → API, retenu | `online` à la connexion, `offline` via le Last Will |
| `smartnuggets/{coop_id}/commands` | API → Pi, QoS 1 | `OPEN`, `CLOSE`, `CALIBRATE` ; ignorée par le Pi après 60 s |

## Sécurité

- Le port public est le **8883 en TLS** ; le 1883 n'existe que sur le réseau Docker interne
  pour l'API et n'est pas publié.
- Aucun accès anonyme : un compte pour l'API (`backend_service`) et **un compte par
  poulailler**, dont le nom d'utilisateur est l'identifiant du poulailler (`coop_01`…).
- `config/acl` limite chaque Raspberry Pi aux topics de son propre poulailler.

## Créer les comptes

Le fichier `config/passwd` contient les mots de passe hachés : il n'est jamais commité.

**Nouveau Raspberry Pi sur le VPS** : `bash scripts/new-coop.sh coop_02`. Le script crée le
compte MQTT avec un mot de passe aléatoire, enregistre le Pi dans la base avec son code
d'appairage, puis affiche le `.env` du Pi et le code. Le broker relit les mots de passe sans
couper les autres Pi.

À la main (par exemple pour le compte de l'API) :

```bash
docker run --rm -it -v "$PWD/config:/mosquitto/config" eclipse-mosquitto:2 \
  mosquitto_passwd -c /mosquitto/config/passwd backend_service
docker run --rm -it -v "$PWD/config:/mosquitto/config" eclipse-mosquitto:2 \
  mosquitto_passwd /mosquitto/config/passwd coop_01
```

Les mêmes mots de passe vont dans `backend/.env` (`MQTT_PASSWORD`) et dans le `.env` du
Raspberry Pi (`edge-coop/.env.example`).

## Certificats TLS

`mosquitto.conf` attend `fullchain.pem` et `privkey.pem` dans `/mosquitto/certs`. Sur le VPS,
c'est le certificat Let's Encrypt de `smartnuggets.be`, le même que pour le site web. Le
conteneur ne lit pas `/etc/letsencrypt` : après chaque renouvellement, certbot lance
`scripts/cert-hook.sh`, qui copie le certificat dans `mosquitto/certs/` puis redémarre le
broker. Le Raspberry Pi n'a donc besoin d'aucun fichier de certificat (`MQTT_CA_CERT` vide).

## Tester à la main

```bash
mosquitto_sub -h smartnuggets.be -p 8883 --capath /etc/ssl/certs -u backend_service -P '<mdp>' -t 'smartnuggets/#' -v
mosquitto_pub -h smartnuggets.be -p 8883 --capath /etc/ssl/certs -u coop_01 -P '<mdp>' \
  -t smartnuggets/coop_01/telemetry -m '{"sent_at": "2026-11-03T08:00:00Z", "inside_count": 4}'
```
