"""Mise en forme d'un flux Server-Sent Events."""

import asyncio
import json
from collections.abc import AsyncIterator, Awaitable, Callable
from typing import Any

from app.services.broadcaster import Message


def format_sse(event: str, data: Any) -> str:
    return f"event: {event}\ndata: {json.dumps(data, separators=(',', ':'))}\n\n"


async def event_stream(
    queue: asyncio.Queue[Message],
    is_disconnected: Callable[[], Awaitable[bool]],
    ping_interval: float = 15.0,
) -> AsyncIterator[str]:
    """Relaye les messages de la file.

    Sans message pendant `ping_interval`, un événement `ping` garde la connexion ouverte. C'est
    un vrai événement et pas un commentaire SSE : la page le voit passer et sait ainsi que le
    flux est vivant (sinon, elle le rouvre).
    """
    yield ": connecté\n\n"
    while not await is_disconnected():
        try:
            message = await asyncio.wait_for(queue.get(), timeout=ping_interval)
        except TimeoutError:
            yield format_sse("ping", {})
            continue
        yield format_sse(message["event"], message["data"])
