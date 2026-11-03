"""Dépendances FastAPI partagées par les routes."""

from collections.abc import AsyncIterator
from typing import Annotated

from fastapi import Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.services.commands import CommandPublisher
from app.services.coop_service import CoopService


async def get_session(request: Request) -> AsyncIterator[AsyncSession]:
    async with request.app.state.sessionmaker() as session:
        yield session


def get_command_publisher(request: Request) -> CommandPublisher:
    return request.app.state.command_publisher


SessionDep = Annotated[AsyncSession, Depends(get_session)]
PublisherDep = Annotated[CommandPublisher, Depends(get_command_publisher)]


def get_coop_service(session: SessionDep, publisher: PublisherDep) -> CoopService:
    return CoopService(session, publisher)


CoopServiceDep = Annotated[CoopService, Depends(get_coop_service)]
