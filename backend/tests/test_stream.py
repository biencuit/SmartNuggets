"""Flux temps réel (/stream) : du message MQTT du Pi jusqu'à la page ouverte (US-COMPT-2).

`httpx.ASGITransport` attend la fin de la réponse avant de la rendre, or un flux SSE ne se
termine jamais. On appelle donc l'application en ASGI brut, comme le ferait uvicorn, et on lit
les messages un par un ; la déconnexion du navigateur ferme le flux à la fin du test.
"""

import asyncio
import json
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Any

from fastapi import FastAPI

from app.models import Coop, User
from app.mqtt.worker import MqttWorker

from .conftest import token_for

SENT_AT = "2026-11-12T08:00:00Z"
WAIT_S = 2.0  # largement assez en local ; un test bloqué échoue au lieu de pendre


class SseReader:
    """Découpe les morceaux reçus en messages `(event, data)` ; ignore les commentaires."""

    def __init__(self, chunks: asyncio.Queue[str]) -> None:
        self._chunks = chunks
        self._buffer = ""

    async def next_message(self) -> tuple[str, Any]:
        while True:
            while "\n\n" not in self._buffer:
                self._buffer += await asyncio.wait_for(self._chunks.get(), WAIT_S)
            block, self._buffer = self._buffer.split("\n\n", 1)
            fields = dict(
                line.split(": ", 1) for line in block.splitlines() if not line.startswith(":")
            )
            if "event" in fields:
                return fields["event"], json.loads(fields["data"])


@asynccontextmanager
async def open_stream(app: FastAPI, coop_id: str, token: str) -> AsyncIterator[SseReader]:
    chunks: asyncio.Queue[str] = asyncio.Queue()
    started: asyncio.Future[int] = asyncio.get_running_loop().create_future()
    disconnected = asyncio.Event()
    request_sent = False

    async def receive() -> dict[str, Any]:
        nonlocal request_sent
        if not request_sent:
            request_sent = True
            return {"type": "http.request", "body": b"", "more_body": False}
        await disconnected.wait()
        return {"type": "http.disconnect"}

    async def send(message: dict[str, Any]) -> None:
        if message["type"] == "http.response.start":
            started.set_result(message["status"])
        elif message["type"] == "http.response.body" and message.get("body"):
            chunks.put_nowait(message["body"].decode())

    path = f"/api/v1/coops/{coop_id}/stream"
    scope = {
        "type": "http",
        "asgi": {"version": "3.0"},
        "http_version": "1.1",
        "method": "GET",
        "scheme": "http",
        "path": path,
        "raw_path": path.encode(),
        "root_path": "",
        "query_string": f"token={token}".encode(),
        "headers": [(b"host", b"test")],
        "client": ("127.0.0.1", 50000),
        "server": ("test", 80),
    }
    task = asyncio.create_task(app(scope, receive, send))
    try:
        assert await asyncio.wait_for(started, WAIT_S) == 200
        yield SseReader(chunks)
    finally:
        disconnected.set()  # le navigateur ferme la page
        await asyncio.wait_for(task, WAIT_S)


async def hen_enters(app: FastAPI, inside_count: int) -> None:
    """Le Pi annonce une entrée par MQTT, avec le compteur à jour."""
    payload = {
        "sent_at": SENT_AT,
        "door_state": "OPEN",
        "inside_count": inside_count,
        "event": {
            "event_type": "HEN_ENTRY",
            "trigger_source": "AI_AUTO",
            "ai_confidence": 0.91,
            "occurred_at": SENT_AT,
        },
    }
    worker = MqttWorker(app.state.settings, app.state.sessionmaker, app.state.broadcaster)
    await worker.handle_message("smartnuggets/coop_01/telemetry", json.dumps(payload).encode())


async def test_stream_envoie_l_etat_actuel_a_la_connexion(
    app: FastAPI, owner: User, coop: Coop
) -> None:
    async with open_stream(app, "coop_01", token_for(owner)) as stream:
        event, status = await stream.next_message()

    assert event == "status"
    # 10 poules au total, 7 dedans : la page affiche 7 dedans et 3 dehors.
    assert (status["total_hens"], status["inside_count"], status["outside_count"]) == (10, 7, 3)


async def test_stream_relaie_un_passage_en_direct(app: FastAPI, owner: User, coop: Coop) -> None:
    async with open_stream(app, "coop_01", token_for(owner)) as stream:
        assert (await stream.next_message())[0] == "status"

        await hen_enters(app, inside_count=8)

        event, status = await stream.next_message()
        assert event == "status"
        assert (status["inside_count"], status["outside_count"]) == (8, 2)
        event, passage = await stream.next_message()
        assert event == "event"
        assert (passage["event_type"], passage["inside_count_after"]) == ("HEN_ENTRY", 8)


async def test_stream_se_recale_apres_une_coupure(app: FastAPI, owner: User, coop: Coop) -> None:
    # Une poule entre pendant que la page est déconnectée (réseau coupé, API redémarrée).
    await hen_enters(app, inside_count=8)

    # EventSource se reconnecte : le premier message donne déjà le bon compte.
    async with open_stream(app, "coop_01", token_for(owner)) as stream:
        event, status = await stream.next_message()

    assert event == "status"
    assert (status["inside_count"], status["outside_count"]) == (8, 2)
