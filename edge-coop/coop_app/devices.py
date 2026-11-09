"""Construit le matériel réel ou simulé selon la configuration."""

from dataclasses import dataclass

from coop_app.config import AppConfig
from hardware.interfaces import Camera, StepperMotor, Switch
from hardware.mock import FakeCamera, FakeStepper, FakeSwitch, LimitSwitch


@dataclass
class Devices:
    motor: StepperMotor
    top: Switch | None
    bottom: Switch | None
    beam_outer: Switch
    beam_inner: Switch
    motion: Switch
    camera: Camera


def build_camera(spec: str) -> Camera:
    kind, _, arg = spec.partition(":")
    if kind == "mock":
        return FakeCamera()
    if kind == "pi":
        from hardware.camera import PiCamera

        return PiCamera()
    if kind == "video":
        from hardware.camera import VideoCamera

        return VideoCamera(arg)
    if kind == "folder":
        from hardware.camera import FolderCamera

        return FolderCamera(arg)
    raise ValueError(f"CAMERA inconnue : {spec!r} (mock, pi, video:<fichier>, folder:<dossier>)")


def build_devices(config: AppConfig) -> Devices:
    if config.hardware == "pi":
        from hardware import gpio

        return Devices(
            motor=gpio.stepper(config.motor_pins, config.step_delay_s),
            top=gpio.GpioSwitch(config.top_pin),
            bottom=gpio.GpioSwitch(config.bottom_pin),
            beam_outer=gpio.GpioSwitch(config.beam_outer_pin),
            beam_inner=gpio.GpioSwitch(config.beam_inner_pin),
            motion=gpio.GpioMotionSensor(config.motion_pin),
            camera=build_camera(config.camera),
        )
    if config.hardware == "mock":
        motor = FakeStepper()
        return Devices(
            motor=motor,
            top=LimitSwitch(motor, config.door.travel_steps, above=True),
            bottom=LimitSwitch(motor, 0, above=False),
            beam_outer=FakeSwitch(),
            beam_inner=FakeSwitch(),
            motion=FakeSwitch(),
            camera=build_camera(config.camera),
        )
    raise ValueError(f"HARDWARE inconnu : {config.hardware!r} (mock ou pi)")
