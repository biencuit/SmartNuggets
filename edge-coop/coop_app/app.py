"""Boucle principale : lit les capteurs et exécute les commandes, dans un seul thread."""

import logging
import queue
import threading
import time
from collections.abc import Callable
from datetime import datetime

from coop_app.controller import CoopController
from mqtt_uplink.client import Command, ScheduleDay

logger = logging.getLogger(__name__)


class CoopApp:
    def __init__(
        self,
        controller: CoopController,
        poll_s: float,
        sleep: Callable[[float], None] = time.sleep,
    ) -> None:
        self.controller = controller
        self.poll_s = poll_s
        self._sleep = sleep
        self._commands: queue.Queue[Command] = queue.Queue()
        self._schedules: queue.Queue[list[ScheduleDay]] = queue.Queue()
        self._predator_locks: queue.Queue[int] = queue.Queue()
        self._stop = threading.Event()

    def submit(self, command: Command) -> None:
        """À passer comme `on_command` à MqttUplink : appelé dans le thread réseau,
        il ne fait que déposer la commande, la boucle principale l'exécute."""
        self._commands.put(command)

    def submit_schedule(self, days: list[ScheduleDay]) -> None:
        """À passer comme `on_schedule` à MqttUplink : même principe que `submit`."""
        self._schedules.put(days)

    def submit_predator_lock(self, seconds: int) -> None:
        """À passer comme `on_predator_lock` à MqttUplink : même principe que `submit`."""
        self._predator_locks.put(seconds)

    def step(self) -> None:
        """Un tour de boucle : planning puis commandes en attente, puis capteurs et règles."""
        while True:
            try:
                days = self._schedules.get_nowait()
            except queue.Empty:
                break
            logger.info("Planning reçu du serveur")
            self.controller.on_schedule(days)
        while True:
            try:
                seconds = self._predator_locks.get_nowait()
            except queue.Empty:
                break
            logger.info("Verrouillage après un prédateur : %d s", seconds)
            self.controller.set_predator_lock_s(seconds)
        while True:
            try:
                command = self._commands.get_nowait()
            except queue.Empty:
                break
            logger.info("Commande reçue : %s", command.action)
            self.controller.on_command(command.action, command.inside_count, force=command.force)
        self.controller.poll()

    def run(
        self,
        until: Callable[[], bool] | None = None,
        before_step: Callable[[], None] | None = None,
    ) -> None:
        self.controller.start()
        while not self._stop.is_set() and not (until and until()):
            if before_step:
                before_step()  # mode démo : le scénario pilote les simulateurs
            self.step()
            self._sleep(self.poll_s)

    def stop(self) -> None:
        self._stop.set()


def local_now() -> datetime:
    return datetime.now().astimezone()
