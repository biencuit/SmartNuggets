"""Programme du poulailler : `python -m coop_app` (configuration : variables d'environnement).

Sur le Raspberry Pi : HARDWARE=pi CAMERA=pi. Sur un PC : HARDWARE=mock (par défaut).
Mode démo : `python -m coop_app --demo scenarios/journee.json` (matériel simulé).
"""

import argparse
import dataclasses
import logging
import signal
import time

from ai_detector import ScriptedDetector, load_detector
from coop_app.app import CoopApp, local_now
from coop_app.config import AppConfig
from coop_app.controller import CoopController
from coop_app.demo import DemoScenario, load_scenario
from coop_app.devices import build_devices
from mqtt_uplink import MqttUplink, Outbox, UplinkConfig


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--demo", metavar="SCENARIO", help="rejouer un scénario (fichier JSON)")
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    config = AppConfig.from_env()
    if args.demo:
        config = dataclasses.replace(config, hardware="mock", detector="scripted")
    uplink_config = UplinkConfig.from_env()
    devices = build_devices(config)
    detector = load_detector(config.detector)
    scenario = None
    now = local_now
    if args.demo:
        if not isinstance(detector, ScriptedDetector):
            raise SystemExit("Le mode démo a besoin de DETECTOR=scripted")
        scenario = DemoScenario(
            load_scenario(args.demo),
            devices,
            detector,
            time.monotonic,
            close_at=config.schedule.close_at,
        )
        now = scenario.now

    outbox = Outbox(uplink_config.outbox_path)
    app: CoopApp | None = None
    uplink = MqttUplink(uplink_config, outbox, on_command=lambda c: app and app.submit(c))
    controller = CoopController(config, devices, detector, uplink, time.monotonic, now)
    app = CoopApp(controller, config.poll_s)
    signal.signal(signal.SIGTERM, lambda *_: app.stop())
    uplink.start()
    logging.info("Poulailler %s démarré (matériel : %s)", uplink_config.coop_id, config.hardware)
    try:
        app.run(before_step=scenario.update if scenario else None)
    except KeyboardInterrupt:
        pass
    finally:
        uplink.stop()
        outbox.close()
        devices.camera.close()


if __name__ == "__main__":
    main()
