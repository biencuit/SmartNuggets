"""Gestion des dates : tout est stocké et renvoyé en UTC."""

from datetime import UTC, datetime


def utcnow() -> datetime:
    return datetime.now(UTC)


def ensure_utc(value: datetime) -> datetime:
    """SQLite ne conserve pas le fuseau horaire : une date "naïve" est considérée comme UTC."""
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)
