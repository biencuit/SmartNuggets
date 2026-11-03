"""File d'attente persistante (SQLite) des messages à envoyer au serveur."""

import sqlite3
import threading
import time
from dataclasses import dataclass


@dataclass(frozen=True)
class OutboxMessage:
    id: int
    topic: str
    payload: bytes
    qos: int
    retain: bool


class Outbox:
    """FIFO qui survit aux redémarrages du Pi.

    Un message n'est retiré qu'après l'accusé de réception du broker (PUBACK) : la livraison
    est donc garantie "au moins une fois". Au-delà de `max_messages`, les plus anciens sont
    supprimés pour ne pas remplir la carte SD pendant une très longue coupure.
    """

    def __init__(self, path: str, max_messages: int = 10_000) -> None:
        self._lock = threading.Lock()
        self._max_messages = max_messages
        self._db = sqlite3.connect(path, check_same_thread=False, isolation_level=None)
        self._db.execute("PRAGMA journal_mode=WAL")
        self._db.execute("""
            CREATE TABLE IF NOT EXISTS outbox (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                topic TEXT NOT NULL,
                payload BLOB NOT NULL,
                qos INTEGER NOT NULL,
                retain INTEGER NOT NULL,
                created_at REAL NOT NULL
            )
            """)

    def enqueue(self, topic: str, payload: bytes, qos: int = 1, retain: bool = False) -> int:
        with self._lock:
            cursor = self._db.execute(
                "INSERT INTO outbox (topic, payload, qos, retain, created_at) "
                "VALUES (?, ?, ?, ?, ?)",
                (topic, payload, qos, int(retain), time.time()),
            )
            self._db.execute(
                "DELETE FROM outbox WHERE id <= " "(SELECT MAX(id) FROM outbox) - ?",
                (self._max_messages,),
            )
            return int(cursor.lastrowid or 0)

    def peek(self, limit: int = 50) -> list[OutboxMessage]:
        """Les plus anciens messages en attente, sans les retirer."""
        with self._lock:
            rows = self._db.execute(
                "SELECT id, topic, payload, qos, retain FROM outbox ORDER BY id LIMIT ?", (limit,)
            ).fetchall()
        return [OutboxMessage(row[0], row[1], bytes(row[2]), row[3], bool(row[4])) for row in rows]

    def remove(self, message_id: int) -> None:
        with self._lock:
            self._db.execute("DELETE FROM outbox WHERE id = ?", (message_id,))

    def __len__(self) -> int:
        with self._lock:
            return int(self._db.execute("SELECT COUNT(*) FROM outbox").fetchone()[0])

    def close(self) -> None:
        with self._lock:
            self._db.close()
