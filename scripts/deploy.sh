#!/usr/bin/env bash
# Déploiement sur le VPS : récupère la dernière version de la branche suivie, reconstruit
# les images et relance les conteneurs (les migrations Alembic sont appliquées au démarrage
# de l'API). Lancé à la main ou par .github/workflows/deploy.yml.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"
COMPOSE=(docker compose -f docker-compose.prod.yml)

for f in backend/.env mosquitto/config/passwd mosquitto/certs/fullchain.pem mosquitto/certs/privkey.pem; do
  [[ -e "$f" ]] || { echo "Fichier manquant : $f (voir le wiki, page 16)" >&2; exit 1; }
done

echo "==> git pull ($(git rev-parse --abbrev-ref HEAD))"
git pull --ff-only

echo "==> build et redémarrage"
"${COMPOSE[@]}" up -d --build --remove-orphans

echo "==> attente de l'API"
for _ in $(seq 1 30); do
  if curl -fsS http://127.0.0.1/api/v1/health >/dev/null 2>&1; then
    echo "API OK - version $(git rev-parse --short HEAD) déployée"
    docker image prune -f >/dev/null
    "${COMPOSE[@]}" ps
    exit 0
  fi
  sleep 3
done

echo "L'API ne répond pas après 90 s" >&2
"${COMPOSE[@]}" ps >&2
"${COMPOSE[@]}" logs --tail 50 backend >&2
exit 1
