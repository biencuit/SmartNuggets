# Image de production de l'API SmartNuggets (FastAPI + Uvicorn).
FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /app

# Dépendances d'abord : cette couche n'est reconstruite que si pyproject.toml change.
# Le paquet lui-même est désinstallé ensuite : le code est lu depuis /app/app.
COPY pyproject.toml ./
RUN mkdir app && touch app/__init__.py \
    && pip install . \
    && pip uninstall -y smartnuggets-backend \
    && rm -rf app build *.egg-info

COPY alembic.ini ./
COPY alembic ./alembic
COPY app ./app

# Utilisateur sans privilèges ; /app/media reçoit les photos d'alertes (volume Docker).
RUN useradd --system --uid 10001 --home-dir /app smartnuggets \
    && mkdir -p /app/media \
    && chown smartnuggets:smartnuggets /app/media
USER smartnuggets

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/api/v1/health', timeout=4)"

# Migrations puis API. Un seul worker : le flux temps réel (SSE) est diffusé en mémoire.
CMD ["sh", "-c", "alembic upgrade head && exec uvicorn app.main:create_app --factory --host 0.0.0.0 --port 8000 --workers 1 --proxy-headers --forwarded-allow-ips='*'"]
