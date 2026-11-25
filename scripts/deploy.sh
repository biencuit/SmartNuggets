#!/usr/bin/env bash
# Déploiement sur le VPS : récupère la dernière version de la branche suivie, reconstruit
# les images et relance les conteneurs (les migrations Alembic sont appliquées au démarrage
# de l'API). Lancé à la main ou par .github/workflows/deploy.yml.
#
# Si la nouvelle version ne répond pas, le script remet seul la version d'avant (base de
# données, code et images Docker), puis s'arrête en erreur : le déploiement apparaît en
# rouge dans GitHub Actions, mais le site reste en ligne avec l'ancienne version.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"
COMPOSE=(docker compose -f docker-compose.prod.yml)
DOMAIN=smartnuggets.be
# Services dont on construit l'image nous-mêmes (db et mosquitto utilisent des images
# officielles qui ne changent pas à chaque déploiement).
NOS_IMAGES=(backend nginx)

# /etc/letsencrypt/renewal/<domaine>.conf existe dès que certbot a créé le certificat
# (le dossier live/ n'est lisible qu'en root).
for f in backend/.env mosquitto/config/passwd mosquitto/certs/fullchain.pem mosquitto/certs/privkey.pem \
  "/etc/letsencrypt/renewal/$DOMAIN.conf"; do
  [[ -e "$f" ]] || { echo "Fichier manquant : $f (voir le wiki, page 16)" >&2; exit 1; }
done

# L'API répond-elle en HTTPS ? --resolve : passe par nginx sur ce serveur, en vérifiant le
# certificat du domaine.
api_repond() {
  curl -fsS --resolve "$DOMAIN:443:127.0.0.1" "https://$DOMAIN/api/v1/health" >/dev/null 2>&1
}

# Attend que l'API réponde (90 s maximum).
attendre_api() {
  for _ in $(seq 1 30); do
    api_repond && return 0
    sleep 3
  done
  return 1
}

# Dernière migration appliquée à la base, lue directement dans PostgreSQL : ça marche même
# quand l'API est plantée. Vide si la lecture échoue.
version_base() {
  # Guillemets simples voulus : $POSTGRES_USER et $POSTGRES_DB sont lus dans le conteneur db.
  # shellcheck disable=SC2016
  "${COMPOSE[@]}" exec -T db sh -c \
    'psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" -tAc "SELECT version_num FROM alembic_version"' \
    2>/dev/null || true
}

# Remet la version d'avant : base de données, puis code et images.
revenir_en_arriere() {
  if [[ "$RETOUR_POSSIBLE" != true ]]; then
    echo "Le site ne marchait pas avant ce déploiement : pas de version d'avant à remettre," >&2
    echo "à réparer à la main (wiki, page 11)." >&2
    exit 1
  fi
  echo "==> retour à la version d'avant ($(git rev-parse --short "$ANCIENNE_VERSION"))" >&2

  # Arrêter l'API cassée : sinon elle redémarre en boucle et relance ses migrations.
  "${COMPOSE[@]}" stop backend

  # Si la nouvelle version a déjà changé la base, on défait ses migrations avec la nouvelle
  # image (c'est elle qui sait les défaire). L'ancienne API refuserait de démarrer sur une
  # base plus récente qu'elle.
  local version
  version=$(version_base)
  if [[ -n "$ANCIENNE_BASE" && -n "$version" && "$version" != "$ANCIENNE_BASE" ]]; then
    echo "==> base de données : migration $version -> $ANCIENNE_BASE" >&2
    if ! "${COMPOSE[@]}" run --rm --no-deps backend alembic downgrade "$ANCIENNE_BASE"; then
      echo "Impossible de défaire les migrations : à réparer à la main (wiki, page 11)." >&2
      exit 1
    fi
  fi

  # Code et images d'avant. --keep ne touche pas aux fichiers modifiés à la main sur le VPS.
  git reset --keep "$ANCIENNE_VERSION"
  local service
  for service in "${NOS_IMAGES[@]}"; do
    docker tag "smartnuggets-$service:precedente" "smartnuggets-$service:latest"
  done
  "${COMPOSE[@]}" up -d --remove-orphans || true

  if attendre_api; then
    echo "Site remis en ligne avec la version d'avant ($(git rev-parse --short HEAD))." >&2
    echo "La nouvelle version ($NOUVELLE_VERSION) est cassée : corriger, puis fusionner la correction." >&2
  else
    echo "La version d'avant ne répond pas non plus : à réparer à la main (wiki, page 11)." >&2
    "${COMPOSE[@]}" ps >&2 || true
  fi
  exit 1
}

# Avant de changer quoi que ce soit, on note ce qui tourne : le commit, la version de la base
# et les images (copiées sous le nom :precedente). Seulement si le site marche : on ne veut
# revenir qu'à une version qui fonctionnait.
ANCIENNE_VERSION=$(git rev-parse HEAD)
ANCIENNE_BASE=$(version_base)
RETOUR_POSSIBLE=false
if api_repond; then
  RETOUR_POSSIBLE=true
  for service in "${NOS_IMAGES[@]}"; do
    docker tag "smartnuggets-$service:latest" "smartnuggets-$service:precedente" || RETOUR_POSSIBLE=false
  done
fi

echo "==> git pull ($(git rev-parse --abbrev-ref HEAD))"
git pull --ff-only
NOUVELLE_VERSION=$(git rev-parse --short HEAD)

echo "==> build et redémarrage"
if "${COMPOSE[@]}" up -d --build --remove-orphans && attendre_api; then
  echo "API OK - version $NOUVELLE_VERSION déployée"
  # Supprime les images qui ne servent plus (garde :precedente pour un futur retour en arrière).
  docker image prune -f >/dev/null
  "${COMPOSE[@]}" ps
  exit 0
fi

echo "La nouvelle version ($NOUVELLE_VERSION) ne répond pas" >&2
"${COMPOSE[@]}" ps >&2 || true
"${COMPOSE[@]}" logs --tail 50 backend >&2 || true
revenir_en_arriere
