"""Point d'entrée de l'API : `uvicorn app.main:create_app --factory`."""

import asyncio
import contextlib
import logging
import secrets
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import Settings, get_settings
from app.db import create_engine, create_sessionmaker
from app.errors import register_exception_handlers
from app.mqtt.worker import MqttCommandPublisher, MqttWorker
from app.routers import auth, coops, health
from app.services.broadcaster import Broadcaster
from app.services.commands import InMemoryCommandPublisher
from app.services.health import DeviceWatchdog
from app.services.retention import RetentionJob

logger = logging.getLogger(__name__)


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or get_settings()
    if settings.jwt_secret_key is None:
        logger.warning("JWT_SECRET_KEY absente : clé temporaire générée (dev uniquement)")
        settings = settings.model_copy(update={"jwt_secret_key": secrets.token_hex(32)})
    engine = create_engine(settings.database_url)
    sessionmaker = create_sessionmaker(engine)
    broadcaster = Broadcaster()

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        watchdog = DeviceWatchdog(
            sessionmaker,
            broadcaster,
            settings.device_offline_after_s,
            settings.health_check_interval_s,
        )
        retention = RetentionJob(
            sessionmaker,
            settings.media_dir,
            settings.photo_retention_days,
            settings.data_retention_days,
            settings.retention_interval_s,
        )
        tasks: list[asyncio.Task[None]] = [
            asyncio.create_task(watchdog.run(), name="watchdog"),
            asyncio.create_task(retention.run(), name="retention"),
        ]
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

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_methods=["*"],
        allow_headers=["Authorization", "Content-Type"],
    )
    register_exception_handlers(app)
    app.include_router(health.router)
    app.include_router(auth.router)
    app.include_router(coops.router)
    return app
