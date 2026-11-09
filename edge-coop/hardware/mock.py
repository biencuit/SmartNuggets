"""Matériel simulé : même interface que le vrai, piloté par les tests et le mode démo."""

from hardware.interfaces import Camera, Direction, Frame, StepperMotor, Switch

# Plus petit JPEG valide (1 x 1 pixel gris) : sert d'image quand on n'a pas de caméra.
TINY_JPEG = bytes.fromhex(
    "ffd8ffe000104a46494600010100000100010000ffdb004300080606070605080707070909080a0c140d0c0b0b0c"
    "1912130f141d1a1f1e1d1a1c1c20242e2720222c231c1c2837292c30313434341f27393d38323c2e333432ffc0"
    "000b080001000101011100ffc4001f0000010501010101010100000000000000000102030405060708090a0bff"
    "c400b5100002010303020403050504040000017d01020300041105122131410613516107227114328191a10823"
    "42b1c11552d1f02433627282090a161718191a25262728292a3435363738393a434445464748494a5354555657"
    "58595a636465666768696a737475767778797a838485868788898a92939495969798999aa2a3a4a5a6a7a8a9aa"
    "b2b3b4b5b6b7b8b9bac2c3c4c5c6c7c8c9cad2d3d4d5d6d7d8d9dae1e2e3e4e5e6e7e8e9eaf1f2f3f4f5f6f7f8"
    "f9faffda0008010100003f00fbd3ffd9"
)


class FakeStepper(StepperMotor):
    """Compte les pas au lieu de faire tourner un moteur."""

    def __init__(self) -> None:
        self.position = 0
        self.steps = 0
        self.energized = False

    def step(self, direction: Direction) -> None:
        self.position += int(direction)
        self.steps += 1
        self.energized = True

    def release(self) -> None:
        self.energized = False


class FakeSwitch(Switch):
    """Contact qu'on ouvre ou ferme à la main : `switch.active = True`."""

    def __init__(self, active: bool = False) -> None:
        self._active = active

    @property
    def active(self) -> bool:
        return self._active

    @active.setter
    def active(self, value: bool) -> None:
        self._active = value


class LimitSwitch(Switch):
    """Fin de course simulé : actif quand le faux moteur atteint une position donnée."""

    def __init__(self, motor: FakeStepper, position: int, above: bool) -> None:
        self._motor = motor
        self._position = position
        self._above = above
        self.stuck = False  # True : le contact ne se ferme jamais (porte bloquée)

    @property
    def active(self) -> bool:
        if self.stuck:
            return False
        if self._above:
            return self._motor.position >= self._position
        return self._motor.position <= self._position


class FakeCamera(Camera):
    """Renvoie toujours la même petite image ; `broken = True` simule une panne."""

    def __init__(self, jpeg: bytes = TINY_JPEG) -> None:
        self.jpeg = jpeg
        self.broken = False
        self.captures = 0

    def capture(self) -> Frame | None:
        if self.broken:
            return None
        self.captures += 1
        return Frame(self.jpeg)

    def close(self) -> None:
        return None
