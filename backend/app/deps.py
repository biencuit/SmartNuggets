"""Dépendances FastAPI partagées par les routes."""

from collections.abc import AsyncIterator
from typing import Annotated

from fastapi import Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import Settings
from app.services.broadcaster import Broadcaster
from app.services.commands import CommandPublisher
from app.services.coop_service import CoopService


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


def get_coop_service(session: SessionDep, publisher: PublisherDep) -> CoopService:
    return CoopService(session, publisher)


CoopServiceDep = Annotated[CoopService, Depends(get_coop_service)]
