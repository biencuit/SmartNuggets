"""Diffusion en temps réel des changements d'un poulailler vers les clients connectés (SSE)."""

import asyncio
from collections import defaultdict
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Any

Message = dict[str, Any]


class Broadcaster:
    """Une file par abonné ; un client trop lent perd les messages les plus anciens."""

    def __init__(self, max_queue_size: int = 100) -> None:
        self._max_queue_size = max_queue_size
        self._subscribers: dict[str, set[asyncio.Queue[Message]]] = defaultdict(set)

    @asynccontextmanager
    async def subscribe(self, coop_id: str) -> AsyncIterator[asyncio.Queue[Message]]:
        queue: asyncio.Queue[Message] = asyncio.Queue(maxsize=self._max_queue_size)
        self._subscribers[coop_id].add(queue)
        try:
            yield queue
        finally:
            self._subscribers[coop_id].discard(queue)
            if not self._subscribers[coop_id]:
                del self._subscribers[coop_id]

    def publish(self, coop_id: str, event: str, data: Any) -> None:
        message = {"event": event, "data": data}
        for queue in list(self._subscribers.get(coop_id, ())):
            if queue.full():
                queue.get_nowait()
            queue.put_nowait(message)

    def subscriber_count(self, coop_id: str) -> int:
        return len(self._subscribers.get(coop_id, ()))
