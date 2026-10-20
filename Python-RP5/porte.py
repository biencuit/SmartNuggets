#!/usr/bin/env python3
"""

Guide de Commandes de Diego pour utilisation de la porte avec moteur , expliquée avec des Leds.

Commande de la porte de poulailler (treuil) - Raspberry Pi 5.

Le code est identique pour la démo (LEDs) et pour le vrai moteur :
seule la sortie physique change, pas la logique.

  GPIO17 -> sens "monter"    (démo : LED 1 / vrai montage : IN1 du driver)
  GPIO27 -> sens "descendre" (démo : LED 2 / vrai montage : IN2 du driver)

Câblage démo : GPIO -> résistance 220-330 ohms -> LED (patte longue +)
               -> patte courte vers GND du Pi. Une résistance par LED.

Commandes :
  m = monter    (LED 1 allumée = la porte se lève)
  d = descendre (LED 2 allumée = la porte se ferme)
  s = stop      (les deux LEDs éteintes = la porte est à l'arrêt)
  q = quitter   (tout est coupé automatiquement)
"""

from gpiozero import Motor
from threading import Timer

PIN_MONTER = 17
PIN_DESCENDRE = 27
DUREE_MAX_S = 10  # sécurité : arrêt automatique après ce délai
                  # (à remplacer plus tard par des fins de course)

moteur = Motor(forward=PIN_MONTER, backward=PIN_DESCENDRE)
minuteur = None


def annuler_minuteur():
    global minuteur
    if minuteur:
        minuteur.cancel()
        minuteur = None


def stop():
    annuler_minuteur()
    moteur.stop()
    print("Arrêt : la porte est immobile.")


def demarrer(sens):
    global minuteur
    annuler_minuteur()
    if sens == "monter":
        moteur.forward()
        print("LED 1 / sens monter : la porte se lève.")
    else:
        moteur.backward()
        print("LED 2 / sens descendre : la porte se ferme.")
    print(f"(arrêt automatique dans {DUREE_MAX_S} s)")
    minuteur = Timer(DUREE_MAX_S, stop)
    minuteur.start()


def main():
    print(__doc__)
    try:
        while True:
            cmd = input("> ").strip().lower()
            if cmd == "m":
                demarrer("monter")
            elif cmd == "d":
                demarrer("descendre")
            elif cmd == "s":
                stop()
            elif cmd == "q":
                break
            else:
                print("Commande inconnue (m / d / s / q)")
    except (KeyboardInterrupt, EOFError):
        pass
    finally:
        stop()
        moteur.close()


if __name__ == "__main__":
    main()