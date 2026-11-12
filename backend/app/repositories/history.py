"""Historique complet d'un poulailler : événements ET alertes dans une seule liste.

Les deux tables sont réunies par un `UNION ALL` SQL : la base trie et pagine directement la
liste mélangée, sans charger toutes les lignes en mémoire. Chaque partie de l'union est filtrée
de son côté (poulailler, types, période) pour profiter de son index `(coop_id, date)`.
"""

from collections.abc import Collection, Sequence
from datetime import datetime

from sqlalchemy import (
    Boolean,
    Integer,
    Row,
    Select,
    String,
    Subquery,
    cast,
    func,
    literal_column,
    null,
    select,
    union_all,
)
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Alert, Event
from app.timeutils import ensure_utc


class HistoryRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def page(
        self,
        coop_id: str,
        *,
        event_types: Collection[str] | None,
        include_alerts: bool,
        since: datetime | None = None,
        until: datetime | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> tuple[Sequence[Row], int]:
        """Une page de l'historique, du plus récent au plus ancien, et le nombre total de lignes.

        `event_types` : None = tous les événements, collection vide = aucun événement.
        `since` est inclus, `until` est exclu.
        """
        history = self._union(coop_id, event_types, include_alerts, since, until)
        if history is None:
            return [], 0
        total = (await self.session.execute(select(func.count()).select_from(history))).scalar_one()
        query = (
            select(history)
            # À la même seconde, l'ordre reste stable d'une page à l'autre.
            .order_by(history.c.occurred_at.desc(), history.c.kind, history.c.id.desc())
            .limit(limit)
            .offset(offset)
        )
        rows = (await self.session.execute(query)).all()
        return rows, total

    @staticmethod
    def _union(
        coop_id: str,
        event_types: Collection[str] | None,
        include_alerts: bool,
        since: datetime | None,
        until: datetime | None,
    ) -> Subquery | None:
        # SQLite ne garde pas le fuseau horaire : on compare toujours des dates UTC.
        since = ensure_utc(since) if since is not None else None
        until = ensure_utc(until) if until is not None else None
        parts: list[Select] = []

        if event_types is None or len(event_types) > 0:
            events = select(
                literal_column("'event'", String).label("kind"),
                Event.id.label("id"),
                Event.event_type.label("type"),
                Event.occurred_at.label("occurred_at"),
                Event.trigger_source.label("trigger_source"),
                Event.inside_count_after.label("inside_count_after"),
                # Colonnes propres aux alertes : NULL typé pour que l'union soit valide.
                cast(null(), String).label("severity"),
                cast(null(), String).label("image_url"),
                cast(null(), Boolean).label("acknowledged"),
            ).where(Event.coop_id == coop_id)
            if event_types is not None:
                events = events.where(Event.event_type.in_(sorted(event_types)))
            if since is not None:
                events = events.where(Event.occurred_at >= since)
            if until is not None:
                events = events.where(Event.occurred_at < until)
            parts.append(events)

        if include_alerts:
            alerts = select(
                literal_column("'alert'", String).label("kind"),
                Alert.id.label("id"),
                Alert.alert_type.label("type"),
                Alert.created_at.label("occurred_at"),
                cast(null(), String).label("trigger_source"),
                cast(null(), Integer).label("inside_count_after"),
                Alert.severity.label("severity"),
                Alert.image_url.label("image_url"),
                Alert.acknowledged.label("acknowledged"),
            ).where(Alert.coop_id == coop_id)
            if since is not None:
                alerts = alerts.where(Alert.created_at >= since)
            if until is not None:
                alerts = alerts.where(Alert.created_at < until)
            parts.append(alerts)

        if not parts:
            return None
        if len(parts) == 1:
            return parts[0].subquery("history")
        return union_all(*parts).subquery("history")
