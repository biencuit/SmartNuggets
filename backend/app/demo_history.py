"""Historique de démonstration : deux semaines de passages réalistes (US-APP-4, #27).

Utilisé par `python -m app.seed`, pour montrer la page Historique et les habitudes sans le
Raspberry Pi. L'historique s'arrête hier : aujourd'hui reste aux vraies données (le Pi, ou le
scénario de `scripts/dev.sh --demo`). Chaque journée est simulée à l'heure de Bruxelles puis
stockée en UTC :
- le matin, les poules sortent peu après l'ouverture ; en novembre, un peu plus tard chaque jour ;
- en fin de matinée, quelques allers-retours pour aller pondre ;
- en fin de journée, elles rentrent, un peu plus tôt chaque jour ;
- la porte suit les règles du Pi : elle s'ouvre quand une poule se présente (AI_AUTO), se
  referme quand plus personne ne passe (AI_AUTO) et se ferme le soir à l'horaire (SCHEDULE) ;
- il y a trois jours, un renard : alerte avec photo et porte fermée par sécurité (FAILSAFE).

Le tirage est pseudo-aléatoire à graine fixe : la démo est la même à chaque fois.
"""

import asyncio
import random
from dataclasses import dataclass
from datetime import UTC, date, datetime, time, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

from sqlalchemy import delete
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Alert, AlertType, Coop, DoorState, Event, EventType, Severity, TriggerSource
from app.timeutils import ensure_utc, utcnow

DEMO_TIMEZONE = ZoneInfo("Europe/Brussels")
DEMO_DAYS = 14
DEMO_SEED = 27
TOTAL_HENS = 10
CLOSE_AT_MIN = 21 * 60 + 30  # fermeture du soir (auto_close_time du poulailler de démo)
AUTO_CLOSE_MIN = 10  # la porte se referme quand plus aucune poule ne passe (comme dev.sh --demo)
PREDATOR_DAYS_AGO = 3
PREDATOR_AT_MIN = 14 * 60 + 12
LATE_HEN_DAYS_AGO = (5, 10)  # jours où une poule rentre juste avant la fermeture du soir
PHOTO = Path(__file__).parent / "demo" / "renard.jpg"


@dataclass(frozen=True)
class DemoEvent:
    at: datetime  # UTC
    event_type: EventType
    trigger_source: TriggerSource
    inside_after: int
    confidence: float | None


@dataclass(frozen=True)
class DemoAlert:
    at: datetime  # UTC
    alert_type: AlertType
    severity: Severity
    confidence: float | None
    with_photo: bool
    acknowledged: bool


@dataclass
class DemoHistory:
    events: list[DemoEvent]
    alerts: list[DemoAlert]
    inside_count: int
    door_state: DoorState


def _at(day: date, minutes: float, tz: ZoneInfo) -> datetime:
    """`minutes` après minuit (heure locale) ce jour-là, en UTC."""
    local = datetime.combine(day, time(0), tzinfo=tz) + timedelta(minutes=minutes)
    return local.astimezone(UTC).replace(microsecond=0)


def _passages(day_index: int, days_ago: int, rng: random.Random) -> list[tuple[float, EventType]]:
    """Heures (en minutes locales) des sorties et entrées d'une journée."""
    opening = 7 * 60 + day_index * 1.2 + rng.uniform(-8, 8)
    evening = 18 * 60 + 40 - day_index * 1.5 + rng.uniform(-10, 10)
    out = rng.randint(8, TOTAL_HENS)
    passages = [(opening + rng.uniform(0.5, 45), EventType.HEN_EXIT) for _ in range(out)]
    for _ in range(rng.randint(2, 4)):  # aller pondre puis ressortir
        back_in = rng.uniform(10 * 60, 13 * 60 + 30)
        passages.append((back_in, EventType.HEN_ENTRY))
        passages.append((back_in + rng.uniform(15, 45), EventType.HEN_EXIT))
    returns = [evening + rng.uniform(-50, 40) for _ in range(out)]
    if days_ago in LATE_HEN_DAYS_AGO:
        returns[-1] = CLOSE_AT_MIN - rng.uniform(1, 3)
    if days_ago == PREDATOR_DAYS_AGO:
        # Une poule rentre en courant juste avant le renard : la porte est encore ouverte.
        passages.append((PREDATOR_AT_MIN - 1.5, EventType.HEN_ENTRY))
    passages += [(t, EventType.HEN_ENTRY) for t in returns]
    return sorted(passages)


def _simulate_day(
    day: date,
    day_index: int,
    days_ago: int,
    rng: random.Random,
    tz: ZoneInfo,
) -> tuple[list[DemoEvent], list[DemoAlert]]:
    events: list[DemoEvent] = []
    alerts: list[DemoAlert] = []
    inside = TOTAL_HENS
    door_open = False
    last_passage = 0.0

    def door(minutes: float, event_type: EventType, source: TriggerSource) -> None:
        confidence = (
            round(rng.uniform(0.88, 0.98), 2) if event_type == EventType.DOOR_OPEN else None
        )
        if source != TriggerSource.AI_AUTO:
            confidence = None
        events.append(DemoEvent(_at(day, minutes, tz), event_type, source, inside, confidence))

    def close_if_idle(until: float) -> None:
        """Referme la porte si plus personne n'est passé depuis AUTO_CLOSE_MIN avant `until`."""
        nonlocal door_open
        # La porte s'ouvre 0,2 min avant un passage : la fermeture doit avoir lieu avant.
        if door_open and last_passage + AUTO_CLOSE_MIN < min(until - 0.2, CLOSE_AT_MIN):
            door(last_passage + AUTO_CLOSE_MIN, EventType.DOOR_CLOSE, TriggerSource.AI_AUTO)
            door_open = False

    predator_day = days_ago == PREDATOR_DAYS_AGO
    predator_pending = predator_day
    for minutes, event_type in _passages(day_index, days_ago, rng):
        if predator_pending and minutes > PREDATOR_AT_MIN:
            predator_pending = False
            close_if_idle(PREDATOR_AT_MIN)
            alerts.append(
                DemoAlert(
                    _at(day, PREDATOR_AT_MIN, tz),
                    AlertType.PREDATOR_DETECTED,
                    Severity.CRITICAL,
                    0.87,
                    with_photo=True,
                    acknowledged=False,
                )
            )
            if door_open:
                door(PREDATOR_AT_MIN, EventType.DOOR_CLOSE, TriggerSource.FAILSAFE)
                door_open = False
        # Porte verrouillée 5 minutes après le renard (US-SECU-2) : personne ne passe.
        if predator_day and PREDATOR_AT_MIN <= minutes < PREDATOR_AT_MIN + 5:
            continue
        close_if_idle(minutes)
        if event_type == EventType.HEN_EXIT and inside == 0:
            continue
        if event_type == EventType.HEN_ENTRY and inside == TOTAL_HENS:
            continue
        if not door_open:
            door(minutes - 0.2, EventType.DOOR_OPEN, TriggerSource.AI_AUTO)
            door_open = True
        inside += 1 if event_type == EventType.HEN_ENTRY else -1
        events.append(
            DemoEvent(
                _at(day, minutes, tz),
                event_type,
                TriggerSource.AI_AUTO,
                inside,
                round(rng.uniform(0.82, 0.98), 2),
            )
        )
        last_passage = minutes

    close_if_idle(CLOSE_AT_MIN)
    if door_open:
        door(CLOSE_AT_MIN, EventType.DOOR_CLOSE, TriggerSource.SCHEDULE)
    if day_index == 2:
        alerts.append(
            DemoAlert(
                _at(day, 5 * 60 + 40, tz),
                AlertType.LOW_BATTERY,
                Severity.WARNING,
                None,
                with_photo=False,
                acknowledged=True,
            )
        )
    return events, alerts


def build_demo_history(
    now: datetime,
    *,
    days: int = DEMO_DAYS,
    tz: ZoneInfo = DEMO_TIMEZONE,
    seed: int = DEMO_SEED,
) -> DemoHistory:
    """Les `days` jours complets avant aujourd'hui (d'avant-hier il y a `days` jours à hier)."""
    now = ensure_utc(now)
    # Données de démo, pas de cryptographie : un générateur simple à graine fixe suffit.
    rng = random.Random(seed)  # nosec B311
    today = now.astimezone(tz).date()
    events: list[DemoEvent] = []
    alerts: list[DemoAlert] = []
    for index in range(days):
        days_ago = days - index
        day_events, day_alerts = _simulate_day(
            today - timedelta(days=days_ago), index, days_ago, rng, tz
        )
        events += day_events
        alerts += day_alerts

    events = [e for e in events if e.at <= now]
    alerts = [a for a in alerts if a.at <= now]
    doors = [e for e in events if e.event_type in (EventType.DOOR_OPEN, EventType.DOOR_CLOSE)]
    door_open = bool(doors) and doors[-1].event_type == EventType.DOOR_OPEN
    return DemoHistory(
        events=events,
        alerts=alerts,
        inside_count=events[-1].inside_after if events else TOTAL_HENS,
        door_state=DoorState.OPEN if door_open else DoorState.CLOSED,
    )


def _copy_photo(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(PHOTO.read_bytes())


async def add_demo_history(
    session: AsyncSession,
    coop: Coop,
    media_dir: str | Path,
    now: datetime | None = None,
    *,
    replace: bool = False,
) -> DemoHistory:
    """Enregistre l'historique de démo du poulailler (et la photo du renard dans `media_dir`).

    `replace=True` efface d'abord les événements et alertes du poulailler.
    """
    now = now or utcnow()
    if replace:
        await session.execute(delete(Event).where(Event.coop_id == coop.id))
        await session.execute(delete(Alert).where(Alert.coop_id == coop.id))
    history = build_demo_history(now)
    session.add_all(
        Event(
            coop_id=coop.id,
            event_type=e.event_type,
            trigger_source=e.trigger_source,
            inside_count_after=e.inside_after,
            ai_confidence=e.confidence,
            occurred_at=e.at,
        )
        for e in history.events
    )
    for demo_alert in history.alerts:
        alert = Alert(
            coop_id=coop.id,
            alert_type=demo_alert.alert_type,
            severity=demo_alert.severity,
            ai_confidence=demo_alert.confidence,
            acknowledged=demo_alert.acknowledged,
            created_at=demo_alert.at,
        )
        session.add(alert)
        if demo_alert.with_photo:
            await session.flush()  # pour connaître alert.id
            # Même emplacement et même URL que les photos envoyées par le Pi (ingestion.py).
            path = Path(media_dir) / coop.id / f"{alert.id}.jpeg"
            await asyncio.to_thread(_copy_photo, path)
            alert.image_url = f"/api/v1/coops/{coop.id}/alerts/{alert.id}/image"
    coop.inside_count = history.inside_count
    coop.door_state = history.door_state
    coop.last_seen_at = now
    await session.flush()
    return history
