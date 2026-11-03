"""Routes des poulaillers : état, historique, alertes et commandes manuelles."""

from typing import Annotated

from fastapi import APIRouter, Query, status

from app.deps import CoopServiceDep
from app.models import EventType
from app.schemas import (
    AlertRead,
    CommandAccepted,
    CommandRequest,
    CoopRead,
    CoopStatus,
    EventRead,
)

router = APIRouter(prefix="/api/v1/coops", tags=["poulaillers"])

Limit = Annotated[int, Query(ge=1, le=200, description="Nombre maximum d'éléments")]
Offset = Annotated[int, Query(ge=0, description="Nombre d'éléments à sauter (pagination)")]


@router.get("", response_model=list[CoopRead], summary="Liste des poulaillers")
async def list_coops(service: CoopServiceDep) -> list[CoopRead]:
    coops = await service.list_coops()
    return [CoopRead.model_validate(coop) for coop in coops]


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
