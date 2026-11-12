"""Mode démo : rejoue une journée du poulailler sur le matériel simulé.

Le vrai programme tourne (porte, comptage, règles, envoi au serveur) ; seuls les capteurs
et la détection sont pilotés par un scénario. Format du scénario (JSON) :

    {"steps": [
      {"at": 5,  "do": "hen",      "say": "Une poule se présente devant la porte"},
      {"at": 9,  "do": "exit",     "count": 3},
      {"at": 20, "do": "predator", "name": "renard", "image": "renard.jpg"},
      {"at": 60, "do": "evening"}
    ]}

`at` : secondes depuis le début. Actions : hen, predator, exit, enter, evening, morning.
`image` (hen, predator) : photo JPEG que la caméra simulée prend à ce moment, chemin relatif
au fichier du scénario. C'est elle qui part avec l'alerte prédateur (#23).
"""

import json
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import datetime, time, timedelta
from pathlib import Path
from typing import Any

from ai_detector import Label, ScriptedDetector
from coop_app.devices import Devices
from hardware.mock import TINY_JPEG, FakeCamera, FakeSwitch

# Une poule met 4 lectures (extérieure, les deux, intérieure, aucune) pour passer.
CROSSING_IN = [(True, False), (True, True), (False, True), (False, False)]
CROSSING_OUT = [(False, True), (True, True), (True, False), (False, False)]
ACTIONS = {"hen", "predator", "exit", "enter", "evening", "morning"}


@dataclass
class Step:
    at: float
    do: str
    say: str = ""
    count: int = 1
    name: str = ""
    confidence: float = 0.9
    image: str = ""

    def __post_init__(self) -> None:
        if self.do not in ACTIONS:
            raise ValueError(f"Action inconnue dans le scénario : {self.do!r}")
        if self.image and self.do not in ("hen", "predator"):
            raise ValueError(f"Une image n'a de sens que pour hen et predator, pas {self.do!r}")


def load_scenario(path: str | Path) -> list[Step]:
    path = Path(path)
    data = json.loads(path.read_text(encoding="utf-8"))
    steps = [Step(**step) for step in data["steps"]]
    for step in steps:
        if step.image:
            image = (path.parent / step.image).resolve()
            if not image.is_file():
                raise FileNotFoundError(f"Image du scénario introuvable : {image}")
            step.image = str(image)
    return sorted(steps, key=lambda s: s.at)


@dataclass
class DemoScenario:
    """Pilote les simulateurs ; `update()` est appelé à chaque tour de la boucle principale."""

    steps: list[Step]
    devices: Devices
    detector: ScriptedDetector
    clock: Callable[[], float]
    close_at: time = time(21, 0)  # heure de fermeture, pour l'action « evening »
    real_now: Callable[[], datetime] = lambda: datetime.now().astimezone()
    say: Callable[[str], None] = print
    _start: float | None = None
    _next: int = 0
    _pending: list[Callable[[], None]] = field(default_factory=list)
    time_offset: timedelta = timedelta(0)

    @property
    def finished(self) -> bool:
        return self._next >= len(self.steps) and not self._pending

    def now(self) -> datetime:
        """Heure vue par le programme : l'heure réelle, décalée par « evening »/« morning »."""
        return self.real_now() + self.time_offset

    def update(self) -> None:
        if self._start is None:
            self._start = self.clock()
        if self._pending:
            self._pending.pop(0)()
            return
        elapsed = self.clock() - self._start
        while self._next < len(self.steps) and self.steps[self._next].at <= elapsed:
            self._run(self.steps[self._next])
            self._next += 1

    # ------------------------------------------------------------------ actions

    def _run(self, step: Step) -> None:
        if step.say:
            self.say(f"[démo] {step.say}")
        if step.do in ("hen", "predator"):
            label = Label.HEN if step.do == "hen" else Label.PREDATOR
            self._photo(step.image)
            self.detector.show(label, step.confidence, step.name or str(label))
            self._pulse(self._motion)
        elif step.do in ("exit", "enter"):
            crossing = CROSSING_OUT if step.do == "exit" else CROSSING_IN
            for _ in range(step.count):
                for outer, inner in crossing:
                    self._pending.append(self._beams(outer, inner))
        elif step.do == "evening":
            self.time_offset += self._until_evening()
        elif step.do == "morning":
            self.time_offset = timedelta(0)

    def _photo(self, image: str) -> None:
        """La caméra simulée prend la photo de l'étape (un pixel gris s'il n'y en a pas).

        Avec une vraie vidéo (`DEMO_CAMERA=video:…`), c'est elle qui fournit la photo.
        """
        camera = self.devices.camera
        if isinstance(camera, FakeCamera):
            camera.jpeg = Path(image).read_bytes() if image else TINY_JPEG

    def _pulse(self, switch: FakeSwitch) -> None:
        switch.active = True

        def release() -> None:
            switch.active = False

        self._pending.append(release)

    def _beams(self, outer: bool, inner: bool) -> Callable[[], None]:
        def apply() -> None:
            self._outer.active, self._inner.active = outer, inner

        return apply

    def _until_evening(self) -> timedelta:
        now = self.now()
        target = now.replace(hour=self.close_at.hour, minute=self.close_at.minute, second=0)
        delta = target - now + timedelta(seconds=1)
        return max(delta, timedelta(0))

    @property
    def _motion(self) -> Any:
        return self.devices.motion

    @property
    def _outer(self) -> Any:
        return self.devices.beam_outer

    @property
    def _inner(self) -> Any:
        return self.devices.beam_inner
