"""Point d'entrée de l'API : `uvicorn app.main:create_app --factory`."""

import asyncio
import contextlib
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.config import Settings, get_settings
from app.db import create_engine, create_sessionmaker
from app.errors import register_exception_handlers
from app.mqtt.worker import MqttCommandPublisher, MqttWorker
from app.routers import coops, health
from app.services.broadcaster import Broadcaster
from app.services.commands import InMemoryCommandPublisher


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or get_settings()
    engine = create_engine(settings.database_url)
    sessionmaker = create_sessionmaker(engine)
    broadcaster = Broadcaster()

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        tasks: list[asyncio.Task[None]] = []
        if settings.mqtt_enabled:
            worker = MqttWorker(settings, sessionmaker, broadcaster)
            app.state.command_publisher = MqttCommandPublisher(worker)
            tasks.append(asyncio.create_task(worker.run(), name="mqtt-worker"))
        yield
        for task in tasks:
            task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await task
        await engine.dispose()

    app = FastAPI(
        title=settings.app_name,
        version="0.1.0",
        description="API de la porte de poulailler intelligente SmartNuggets.",
        lifespan=lifespan,
    )
    app.state.settings = settings
    app.state.engine = engine
    app.state.sessionmaker = sessionmaker
    app.state.broadcaster = broadcaster
    app.state.command_publisher = InMemoryCommandPublisher()

    register_exception_handlers(app)
    app.include_router(health.router)
    app.include_router(coops.router)
    return app
