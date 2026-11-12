import asyncio

from httpx import AsyncClient

from app.services.broadcaster import Broadcaster
from app.services.sse import event_stream, format_sse


def test_format_sse() -> None:
    assert format_sse("status", {"a": 1}) == 'event: status\ndata: {"a":1}\n\n'


async def test_broadcaster_diffuse_aux_abonnes_du_poulailler() -> None:
    broadcaster = Broadcaster()
    async with broadcaster.subscribe("coop_01") as queue, broadcaster.subscribe("coop_02") as other:
        broadcaster.publish("coop_01", "status", {"inside_count": 3})
        assert queue.get_nowait() == {"event": "status", "data": {"inside_count": 3}}
        assert other.empty()
    assert broadcaster.subscriber_count("coop_01") == 0


async def test_broadcaster_jette_les_plus_anciens_si_client_trop_lent() -> None:
    broadcaster = Broadcaster(max_queue_size=2)
    async with broadcaster.subscribe("coop_01") as queue:
        for i in range(3):
            broadcaster.publish("coop_01", "event", i)
        assert [queue.get_nowait()["data"] for _ in range(2)] == [1, 2]


async def test_event_stream() -> None:
    queue: asyncio.Queue = asyncio.Queue()
    disconnected = False

    async def is_disconnected() -> bool:
        return disconnected

    stream = event_stream(queue, is_disconnected, ping_interval=0.01)
    assert await anext(stream) == ": connecté\n\n"
    assert await anext(stream) == "event: ping\ndata: {}\n\n"
    await queue.put({"event": "alert", "data": {"id": 1}})
    assert await anext(stream) == 'event: alert\ndata: {"id":1}\n\n'
    disconnected = True
    assert [chunk async for chunk in stream] == []


async def test_stream_poulailler_inconnu(client: AsyncClient) -> None:
    response = await client.get("/api/v1/coops/inconnu/stream")
    assert response.status_code == 404
