"""Matériel réel sur le Raspberry Pi 5, via gpiozero.

Sur le Pi 5, `RPi.GPIO` ne fonctionne plus : gpiozero passe par `lgpio`. gpiozero n'est
importé qu'ici, à l'intérieur des fonctions, pour que le reste tourne sur un PC.

Câblage par défaut (numéros BCM, voir le wiki page 8) :
  ULN2003 IN1..IN4 -> GPIO 5, 6, 13, 19     fin de course haut -> GPIO 23, bas -> GPIO 24
  barrière IR extérieure -> GPIO 27, intérieure -> GPIO 22     PIR -> GPIO 17
"""

from collections.abc import Callable, Sequence
from typing import Any

from hardware.interfaces import Switch
from hardware.stepper import HalfStepper


def stepper(pins: Sequence[int], step_delay_s: float) -> HalfStepper:
    from gpiozero import OutputDevice

    outputs = [OutputDevice(pin, initial_value=False) for pin in pins]
    return HalfStepper([_setter(output) for output in outputs], step_delay_s=step_delay_s)


def _setter(output: Any) -> Callable[[int], None]:
    def set_level(level: int) -> None:
        output.value = bool(level)

    return set_level


class GpioSwitch(Switch):
    """Contact relié entre un GPIO et la masse (résistance de tirage interne du Pi)."""

    def __init__(self, pin: int, active_low: bool = True) -> None:
        from gpiozero import Button

        self._button = Button(pin, pull_up=active_low, bounce_time=0.02)

    @property
    def active(self) -> bool:
        return bool(self._button.is_pressed)


class GpioMotionSensor(Switch):
    """Capteur PIR HC-SR501 : sortie à 1 quand il voit un mouvement."""

    def __init__(self, pin: int) -> None:
        from gpiozero import MotionSensor

        self._sensor = MotionSensor(pin)

    @property
    def active(self) -> bool:
        return bool(self._sensor.motion_detected)
