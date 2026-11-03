"""Démo de la liaison : `python -m mqtt_uplink` (configuration : variables d'environnement).

Envoie une télémétrie à intervalle régulier (battement de cœur) et affiche les commandes
reçues. Utile pour tester le broker et l'API sans le reste du code du poulailler.
"""

import argparse
import logging
import time

from mqtt_uplink import MqttUplink, Outbox, UplinkConfig
from mqtt_uplink.client import Command


def print_command(command: Command) -> None:
    extra = f" (inside_count={command.inside_count})" if command.inside_count is not None else ""
    print(f"Commande reçue : {command.action}{extra}")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--interval", type=float, default=60.0, help="secondes entre 2 envois")
    parser.add_argument("--inside", type=int, default=0, help="poules à l'intérieur")
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    config = UplinkConfig.from_env()
    outbox = Outbox(config.outbox_path)
    uplink = MqttUplink(config, outbox, on_command=print_command)
    uplink.start()
    try:
        while True:
            uplink.send_telemetry(door_state="CLOSED", inside_count=args.inside)
            time.sleep(args.interval)
    except KeyboardInterrupt:
        pass
    finally:
        uplink.stop()
        outbox.close()


if __name__ == "__main__":
    main()
