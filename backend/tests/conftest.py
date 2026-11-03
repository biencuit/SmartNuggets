"""Fixtures communes.

Par défaut les tests tournent sur une base SQLite temporaire ; en CI, `TEST_DATABASE_URL`
pointe vers un PostgreSQL éphémère. Le schéma est recréé à chaque test.
"""

import os
from collections.abc import AsyncIterator
from datetime import time

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import Settings
from app.db import Base
from app.main import create_app
from app.models import Coop, DoorState, User
from app.security import create_access_token, hash_password

TEST_SECRET = "test-secret-" + "x" * 52
OWNER_PASSWORD = "mot-de-passe-de-marc"


@pytest.fixture
def settings(tmp_path) -> Settings:
    url = os.environ.get("TEST_DATABASE_URL", f"sqlite+aiosqlite:///{tmp_path / 'test.db'}")
    return Settings(database_url=url, media_dir=str(tmp_path / "media"), jwt_secret_key=TEST_SECRET)


@pytest.fixture
async def app(settings: Settings) -> AsyncIterator[FastAPI]:
    application = create_app(settings)
    async with application.state.engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)
    yield application
    await application.state.engine.dispose()


@pytest.fixture
async def session(app: FastAPI) -> AsyncIterator[AsyncSession]:
    async with app.state.sessionmaker() as db_session:
        yield db_session


def token_for(user: User) -> str:
    return create_access_token(user.id, TEST_SECRET, "HS256", 60)


@pytest.fixture
async def anon_client(app: FastAPI) -> AsyncIterator[AsyncClient]:
    """Client HTTP sans authentification."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as http:
        yield http


@pytest.fixture
async def client(app: FastAPI, owner: User) -> AsyncIterator[AsyncClient]:
    """Client HTTP connecté en tant que `owner`."""
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
        headers={"Authorization": f"Bearer {token_for(owner)}"},
    ) as http:
        yield http


@pytest.fixture
async def owner(session: AsyncSession) -> User:
    user = User(email="marc@example.com", password_hash=hash_password(OWNER_PASSWORD))
    session.add(user)
    await session.commit()
    return user


@pytest.fixture
async def coop(session: AsyncSession, owner: User) -> Coop:
    coop = Coop(
        id="coop_01",
        owner_id=owner.id,
        name="Poulailler de Marc",
        total_hens=10,
        inside_count=7,
        door_state=DoorState.OPEN,
        auto_close_time=time(21, 30),
        battery_level=88,
    )
    session.add(coop)
    await session.commit()
    return coop
