"""Routes des poulaillers : état, historique, alertes et commandes manuelles."""

from collections.abc import AsyncIterator
from datetime import datetime
from pathlib import Path
from typing import Annotated

from fastapi import APIRouter, HTTPException, Query, Request, status
from fastapi.responses import FileResponse, StreamingResponse

from app.deps import (
    BroadcasterDep,
    CoopServiceDep,
    CoopServiceHeaderOrQueryDep,
    SettingsDep,
)
from app.errors import NotFoundError
from app.models import EventType
from app.schemas import (
    AlertRead,
    CommandAccepted,
    CommandRequest,
    CoopCreate,
    CoopRead,
    CoopStatus,
    EventRead,
    HabitsRead,
    HistoryCategory,
    HistoryPage,
)
from app.services.habits import DEFAULT_TIMEZONE, UnknownTimezoneError, load_timezone
from app.services.sse import event_stream, format_sse
from app.timeutils import ensure_utc

router = APIRouter(prefix="/api/v1/coops", tags=["poulaillers"])

Limit = Annotated[int, Query(ge=1, le=200, description="Nombre maximum d'éléments")]
Offset = Annotated[int, Query(ge=0, description="Nombre d'éléments à sauter (pagination)")]


@router.get("", response_model=list[CoopRead], summary="Poulaillers de l'utilisateur connecté")
async def list_coops(service: CoopServiceDep) -> list[CoopRead]:
    coops = await service.list_coops()
    return [CoopRead.model_validate(coop) for coop in coops]


@router.post(
    "",
    response_model=CoopRead,
    status_code=status.HTTP_201_CREATED,
    summary="Ajouter un poulailler à son compte",
    description=(
        "Il faut l'identifiant du Raspberry Pi **et** son code d'appairage (étiquette du "
        "boîtier). Le code ne marche qu'une fois."
    ),
    responses={403: {"description": "Identifiant ou code d'appairage incorrect"}},
)
async def create_coop(data: CoopCreate, service: CoopServiceDep) -> CoopRead:
    coop = await service.create_coop(data)
    return CoopRead.model_validate(coop)


@router.get("/{coop_id}/status", response_model=CoopStatus, summary="État actuel du poulailler")
async def get_status(coop_id: str, service: CoopServiceDep) -> CoopStatus:
    return await service.get_status(coop_id)


@router.get(
    "/{coop_id}/events",
    response_model=list[EventRead],
    summary="Historique paginé des passages et événements",
)
async def list_events(
    coop_id: str,
    service: CoopServiceDep,
    event_type: Annotated[EventType | None, Query(alias="type")] = None,
    limit: Limit = 50,
    offset: Offset = 0,
) -> list[EventRead]:
    events = await service.list_events(coop_id, event_type=event_type, limit=limit, offset=offset)
    return [EventRead.model_validate(event) for event in events]


@router.get(
    "/{coop_id}/history",
    response_model=HistoryPage,
    summary="Historique complet : passages, porte et alertes",
    description=(
        "Événements et alertes dans une seule liste, du plus récent au plus ancien. "
        "`category` peut être répété (`?category=entries&category=alerts`) ; sans catégorie, "
        "tout est renvoyé. `since` est inclus, `until` est exclu (dates ISO 8601, UTC si "
        "aucun fuseau n'est indiqué). `total` compte tous les résultats, pas seulement la page."
    ),
    responses={422: {"description": "Catégorie inconnue, dates incohérentes ou limite invalide"}},
)
async def get_history(
    coop_id: str,
    service: CoopServiceDep,
    category: Annotated[
        list[HistoryCategory] | None, Query(description="entries, exits, door ou alerts")
    ] = None,
    since: Annotated[datetime | None, Query(description="Début de la période (inclus)")] = None,
    until: Annotated[datetime | None, Query(description="Fin de la période (exclue)")] = None,
    limit: Annotated[int, Query(ge=1, le=100, description="Taille de la page")] = 50,
    offset: Offset = 0,
) -> HistoryPage:
    if since is not None and until is not None and ensure_utc(since) >= ensure_utc(until):
        raise HTTPException(
            status_code=422,
            detail="La fin de la période doit être après son début",
        )
    return await service.history_page(
        coop_id, categories=category, since=since, until=until, limit=limit, offset=offset
    )


@router.get(
    "/{coop_id}/habits",
    response_model=HabitsRead,
    summary="Habitudes des poules : sorties et retours par jour et par heure",
    description=(
        "Résumé des entrées et sorties des `days` derniers jours (aujourd'hui compris). "
        "Les jours et les heures sont ceux du fuseau `tz` (nom IANA, Europe/Brussels par "
        "défaut) : un passage à 23 h 30 à Bruxelles compte pour ce jour-là, même en hiver."
    ),
    responses={422: {"description": "Nombre de jours hors de 1..31 ou fuseau inconnu"}},
)
async def get_habits(
    coop_id: str,
    service: CoopServiceDep,
    days: Annotated[int, Query(ge=1, le=31, description="Nombre de jours")] = 7,
    tz: Annotated[
        str,
        Query(
            pattern=r"^[A-Za-z0-9_+/-]{1,64}$",
            description="Fuseau horaire IANA, par exemple Europe/Brussels",
        ),
    ] = DEFAULT_TIMEZONE,
) -> HabitsRead:
    try:
        zone = load_timezone(tz)
    except UnknownTimezoneError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return await service.get_habits(coop_id, days=days, tz=zone)


@router.get(
    "/{coop_id}/alerts",
    response_model=list[AlertRead],
    summary="Alertes, de la plus récente à la plus ancienne",
)
async def list_alerts(
    coop_id: str,
    service: CoopServiceDep,
    acknowledged: bool | None = None,
    limit: Limit = 50,
    offset: Offset = 0,
) -> list[AlertRead]:
    alerts = await service.list_alerts(
        coop_id, acknowledged=acknowledged, limit=limit, offset=offset
    )
    return [AlertRead.model_validate(alert) for alert in alerts]


@router.post(
    "/{coop_id}/alerts/{alert_id}/ack",
    response_model=AlertRead,
    summary="Marquer une alerte comme lue",
)
async def acknowledge_alert(coop_id: str, alert_id: int, service: CoopServiceDep) -> AlertRead:
    alert = await service.acknowledge_alert(coop_id, alert_id)
    return AlertRead.model_validate(alert)


@router.post(
    "/{coop_id}/command",
    response_model=CommandAccepted,
    status_code=status.HTTP_202_ACCEPTED,
    summary="Envoyer une commande manuelle à la porte",
    description=(
        "La commande est transmise au Raspberry Pi ; son effet réel (porte ouverte, "
        "compteur recalé) remonte ensuite par la télémétrie."
    ),
)
async def send_command(
    coop_id: str, request: CommandRequest, service: CoopServiceDep
) -> CommandAccepted:
    command = await service.send_command(coop_id, request)
    return CommandAccepted(
        command_id=command.command_id,
        coop_id=command.coop_id,
        action=command.action,
        inside_count=command.inside_count,
        issued_at=command.issued_at,
    )


@router.get(
    "/{coop_id}/alerts/{alert_id}/image",
    response_class=FileResponse,
    summary="Photo associée à une alerte",
)
async def get_alert_image(
    coop_id: str, alert_id: int, service: CoopServiceHeaderOrQueryDep, settings: SettingsDep
) -> FileResponse:
    alert = await service.get_alert(coop_id, alert_id)
    if alert.image_url is None:
        raise NotFoundError("Cette alerte n'a pas de photo")
    folder = Path(settings.media_dir) / coop_id
    for extension, media_type in (("jpeg", "image/jpeg"), ("webp", "image/webp")):
        path = folder / f"{alert.id}.{extension}"
        if path.is_file():
            return FileResponse(path, media_type=media_type)
    raise NotFoundError("Photo introuvable")


@router.get(
    "/{coop_id}/stream",
    response_class=StreamingResponse,
    summary="Flux temps réel (Server-Sent Events)",
    description=(
        "Événements `status` (état complet du poulailler, envoyé aussi dès la connexion), "
        "`event` (passage, porte) et `alert`. Sans autre message, un événement `ping` part "
        "toutes les 15 s : la page sait ainsi que le flux est vivant. EventSource ne pouvant "
        "pas envoyer d'en-tête, le jeton peut être passé en paramètre `?token=`."
    ),
)
async def stream(
    coop_id: str,
    request: Request,
    service: CoopServiceHeaderOrQueryDep,
    broadcaster: BroadcasterDep,
) -> StreamingResponse:
    await service.get_coop(coop_id)
    # Le flux peut rester ouvert des heures : on rend la connexion à la base tout de suite.
    await service.session.close()

    async def body() -> AsyncIterator[str]:
        async with broadcaster.subscribe(coop_id) as queue:
            # L'état actuel part en premier : après une coupure, EventSource se reconnecte et
            # la page se recale aussitôt, sans attendre le prochain message du Pi. On s'abonne
            # avant de le lire : un passage arrivé entre les deux est déjà dans la file.
            current = await service.get_status(coop_id)
            await service.session.close()
            yield format_sse("status", current.model_dump(mode="json"))
            async for chunk in event_stream(queue, request.is_disconnected):
                yield chunk

    return StreamingResponse(
        body(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )
