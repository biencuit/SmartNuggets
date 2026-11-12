"""Habitudes des poules : à quelle heure elles sortent, à quelle heure elles rentrent.

Le calcul se fait en Python plutôt qu'en SQL :
- la conversion de fuseau horaire n'existe pas sous SQLite (développement et tests) et s'écrit
  différemment sous PostgreSQL (production) ; ici, le même code marche partout ;
- `zoneinfo` gère l'heure d'été : le 25/10/2026, la journée dure 25 h à Bruxelles et le passage
  de 2 h 30 a lieu deux fois ; chaque passage est rangé sur l'heure affichée par l'horloge.

Les dates restent stockées en UTC ; seule la présentation (jour, heure) est locale.
"""

from collections.abc import Iterable
from dataclasses import dataclass, field
from datetime import UTC, date, datetime, time, timedelta
from typing import Protocol
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from app.models import EventType
from app.schemas import HabitDay, HabitHour, HabitsRead
from app.timeutils import ensure_utc

DEFAULT_TIMEZONE = "Europe/Brussels"
PASSAGE_TYPES = (EventType.HEN_ENTRY, EventType.HEN_EXIT)


class UnknownTimezoneError(ValueError):
    """Nom de fuseau horaire inconnu (ex. « Europe/Bruxelles » au lieu de « Europe/Brussels »)."""


class Passage(Protocol):
    """Ce dont le calcul a besoin d'un événement (le modèle `Event` convient)."""

    event_type: str
    occurred_at: datetime


def load_timezone(name: str) -> ZoneInfo:
    try:
        return ZoneInfo(name)
    # ValueError : chemin refusé par zoneinfo (« ../ ») ; OSError : dossier (« Europe »).
    except (ZoneInfoNotFoundError, ValueError, OSError) as exc:
        raise UnknownTimezoneError(f"Fuseau horaire inconnu : {name!r}") from exc


def period_start(now: datetime, tz: ZoneInfo, days: int) -> date:
    """Premier jour (local) d'une période de `days` jours qui se termine aujourd'hui."""
    today = ensure_utc(now).astimezone(tz).date()
    return today - timedelta(days=days - 1)


def utc_bounds(first_day: date, days: int, tz: ZoneInfo) -> tuple[datetime, datetime]:
    """Minuit local du premier jour → minuit local après le dernier jour, convertis en UTC.

    Un jour de changement d'heure dure 23 h ou 25 h : on ne peut pas ajouter 24 h en UTC.
    """
    start = datetime.combine(first_day, time(0), tzinfo=tz)
    end = datetime.combine(first_day + timedelta(days=days), time(0), tzinfo=tz)
    return start.astimezone(UTC), end.astimezone(UTC)


@dataclass
class _Day:
    exits: int = 0
    entries: int = 0
    # Dates locales complètes, comparées en UTC (voir `_earlier`) : l'ordre reste juste même
    # quand l'horloge recule d'une heure.
    first_exit_at: datetime | None = None
    last_entry_at: datetime | None = None

    @property
    def first_exit(self) -> time | None:
        return _clock(self.first_exit_at)

    @property
    def last_entry(self) -> time | None:
        return _clock(self.last_entry_at)


@dataclass
class _Totals:
    exits: list[int] = field(default_factory=lambda: [0] * 24)
    entries: list[int] = field(default_factory=lambda: [0] * 24)


def _earlier(a: datetime, b: datetime) -> bool:
    # Deux dates du même fuseau se comparent sur l'heure affichée (Python ignore `fold`) :
    # 02:30 (1re fois) et 02:30 (2e fois) seraient égales. En UTC, l'ordre est le vrai.
    return a.astimezone(UTC) < b.astimezone(UTC)


def _clock(value: datetime | None) -> time | None:
    """Heure affichée par l'horloge locale, à la minute."""
    return None if value is None else time(value.hour, value.minute)


def _minutes(value: time) -> int:
    return value.hour * 60 + value.minute


def _average_time(values: list[time]) -> time | None:
    if not values:
        return None
    minutes = round(sum(_minutes(v) for v in values) / len(values))
    return time(minutes // 60, minutes % 60)


def compute_habits(
    passages: Iterable[Passage], tz: ZoneInfo, first_day: date, days: int
) -> HabitsRead:
    """Résume les entrées et sorties de `days` jours à partir de `first_day` (heure locale).

    Les passages hors période sont ignorés. Les jours sans passage restent dans la liste : une
    journée sans sortie est une information (porte bloquée, mauvais temps, prédateur…).
    """
    per_day = {first_day + timedelta(days=i): _Day() for i in range(days)}
    totals = _Totals()

    for passage in passages:
        local = ensure_utc(passage.occurred_at).astimezone(tz)
        day = per_day.get(local.date())
        if day is None:
            continue
        if passage.event_type == EventType.HEN_EXIT:
            day.exits += 1
            totals.exits[local.hour] += 1
            if day.first_exit_at is None or _earlier(local, day.first_exit_at):
                day.first_exit_at = local
        elif passage.event_type == EventType.HEN_ENTRY:
            day.entries += 1
            totals.entries[local.hour] += 1
            if day.last_entry_at is None or _earlier(day.last_entry_at, local):
                day.last_entry_at = local

    total_exits = sum(totals.exits)
    # Jours avec au moins un passage : aujourd'hui qui commence (ou une journée sans aucun
    # mouvement) ne fait pas baisser la moyenne ; ces jours restent visibles dans `days`.
    active_days = sum(1 for d in per_day.values() if d.exits or d.entries)
    return HabitsRead(
        timezone=tz.key,
        days=[
            HabitDay(
                day=key,
                exits=value.exits,
                entries=value.entries,
                first_exit=value.first_exit,
                last_entry=value.last_entry,
            )
            for key, value in per_day.items()
        ],
        hours=[
            HabitHour(hour=hour, exits=totals.exits[hour], entries=totals.entries[hour])
            for hour in range(24)
        ],
        average_first_exit=_average_time(
            [d.first_exit for d in per_day.values() if d.first_exit is not None]
        ),
        average_last_entry=_average_time(
            [d.last_entry for d in per_day.values() if d.last_entry is not None]
        ),
        exits_per_day=round(total_exits / active_days, 1) if active_days else 0.0,
        active_days=active_days,
        total_exits=total_exits,
        total_entries=sum(totals.entries),
    )
