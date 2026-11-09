"""Programme du poulailler : `python -m coop_app` (configuration : variables d'environnement).

Sur le Raspberry Pi : HARDWARE=pi CAMERA=pi. Sur un PC : HARDWARE=mock (par défaut).
"""

import logging
import signal
import time

from ai_detector import load_detector
from coop_app.app import CoopApp, local_now
from coop_app.config import AppConfig
from coop_app.controller import CoopController
from coop_app.devices import build_devices
from mqtt_uplink import MqttUplink, Outbox, UplinkConfig


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    config = AppConfig.from_env()
    uplink_config = UplinkConfig.from_env()
    devices = build_devices(config)
    outbox = Outbox(uplink_config.outbox_path)
    app: CoopApp | None = None
    uplink = MqttUplink(uplink_config, outbox, on_command=lambda c: app and app.submit(c))
    controller = CoopController(
        config, devices, load_detector(config.detector), uplink, time.monotonic, local_now
    )
    app = CoopApp(controller, config.poll_s)
    signal.signal(signal.SIGTERM, lambda *_: app.stop())
    uplink.start()
    logging.info("Poulailler %s démarré (matériel : %s)", uplink_config.coop_id, config.hardware)
    try:
        app.run()
    except KeyboardInterrupt:
        pass
    finally:
        uplink.stop()
        outbox.close()
        devices.camera.close()


if __name__ == "__main__":
    main()
