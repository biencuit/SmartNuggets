"""Accès aux données : une classe par table, uniquement des requêtes SQLAlchemy paramétrées."""

from app.repositories.alerts import AlertRepository
from app.repositories.coops import CoopRepository
from app.repositories.events import EventRepository
from app.repositories.users import UserRepository

__all__ = ["AlertRepository", "CoopRepository", "EventRepository", "UserRepository"]
