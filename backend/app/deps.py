"""Dépendances FastAPI partagées par les routes."""

from collections.abc import AsyncIterator
from typing import Annotated

from fastapi import Depends, Query, Request
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import Settings
from app.errors import UnauthorizedError
from app.models import User
from app.repositories import UserRepository
from app.security import InvalidTokenError, decode_access_token
from app.services.auth_service import AuthService
from app.services.broadcaster import Broadcaster
from app.services.commands import CommandPublisher
from app.services.coop_service import CoopService

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/login", auto_error=False)


async def get_session(request: Request) -> AsyncIterator[AsyncSession]:
    async with request.app.state.sessionmaker() as session:
        yield session


def get_command_publisher(request: Request) -> CommandPublisher:
    return request.app.state.command_publisher


def get_broadcaster(request: Request) -> Broadcaster:
    return request.app.state.broadcaster


def get_app_settings(request: Request) -> Settings:
    return request.app.state.settings


SessionDep = Annotated[AsyncSession, Depends(get_session)]
PublisherDep = Annotated[CommandPublisher, Depends(get_command_publisher)]
BroadcasterDep = Annotated[Broadcaster, Depends(get_broadcaster)]
SettingsDep = Annotated[Settings, Depends(get_app_settings)]
BearerToken = Annotated[str | None, Depends(oauth2_scheme)]


async def _user_from_token(token: str | None, session: AsyncSession, settings: Settings) -> User:
    if not token or settings.jwt_secret_key is None:
        raise UnauthorizedError()
    try:
        user_id = decode_access_token(token, settings.jwt_secret_key, settings.jwt_algorithm)
    except InvalidTokenError as exc:
        raise UnauthorizedError("Session expirée ou invalide, reconnectez-vous") from exc
    user = await UserRepository(session).get(user_id)
    if user is None:
        raise UnauthorizedError("Compte introuvable")
    return user


async def get_current_user(token: BearerToken, session: SessionDep, settings: SettingsDep) -> User:
    """Utilisateur authentifié par l'en-tête `Authorization: Bearer <jeton>`."""
    return await _user_from_token(token, session, settings)


async def get_current_user_header_or_query(
    token: BearerToken,
    session: SessionDep,
    settings: SettingsDep,
    query_token: Annotated[
        str | None,
        Query(
            alias="token",
            description="Jeton d'accès, pour EventSource et <img> qui ne peuvent pas "
            "envoyer d'en-tête Authorization",
        ),
    ] = None,
) -> User:
    return await _user_from_token(token or query_token, session, settings)


CurrentUser = Annotated[User, Depends(get_current_user)]
CurrentUserHeaderOrQuery = Annotated[User, Depends(get_current_user_header_or_query)]


def get_auth_service(session: SessionDep, settings: SettingsDep) -> AuthService:
    return AuthService(session, settings)


def get_coop_service(
    session: SessionDep, publisher: PublisherDep, user: CurrentUser
) -> CoopService:
    return CoopService(session, publisher, owner_id=user.id)


def get_coop_service_header_or_query(
    session: SessionDep, publisher: PublisherDep, user: CurrentUserHeaderOrQuery
) -> CoopService:
    return CoopService(session, publisher, owner_id=user.id)


AuthServiceDep = Annotated[AuthService, Depends(get_auth_service)]
CoopServiceDep = Annotated[CoopService, Depends(get_coop_service)]
CoopServiceHeaderOrQueryDep = Annotated[CoopService, Depends(get_coop_service_header_or_query)]
