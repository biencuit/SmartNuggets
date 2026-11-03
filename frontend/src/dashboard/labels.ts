/** Libellés en français des valeurs renvoyées par l'API. */

import type { AlertType, CoopAlert, DoorState, EventType, TriggerSource } from "../api/client";

export const DOOR_STATE_LABELS: Record<DoorState, string> = {
  OPEN: "Ouverte",
  CLOSED: "Fermée",
  OPENING: "En train de s'ouvrir",
  CLOSING: "En train de se fermer",
  ERROR: "En erreur",
};

export const EVENT_LABELS: Record<EventType, string> = {
  HEN_ENTRY: "Une poule est rentrée",
  HEN_EXIT: "Une poule est sortie",
  DOOR_OPEN: "Porte ouverte",
  DOOR_CLOSE: "Porte fermée",
  OBSTACLE: "Obstacle devant la porte",
};

export const TRIGGER_LABELS: Record<TriggerSource, string> = {
  AI_AUTO: "Caméra",
  MANUAL_APP: "Application",
  SCHEDULE: "Horaire",
  FAILSAFE: "Sécurité",
};

export const ALERT_TITLES: Record<AlertType, string> = {
  PREDATOR_DETECTED: "Prédateur détecté",
  MISSING_HEN: "Poule pas rentrée",
  DOOR_BLOCKED: "Porte bloquée",
  LOW_BATTERY: "Batterie faible",
  DEVICE_OFFLINE: "Poulailler hors ligne",
};

export const ALERT_ADVICE: Record<AlertType, string> = {
  PREDATOR_DETECTED: "La porte reste fermée tant que le prédateur est là. Regardez la photo.",
  MISSING_HEN: "Le compteur indique qu'une poule n'est pas rentrée à l'heure de fermeture.",
  DOOR_BLOCKED: "La porte n'a pas pu finir son mouvement. Vérifiez qu'aucun obstacle ne la gêne.",
  LOW_BATTERY: "Rechargez ou remplacez la batterie du poulailler.",
  DEVICE_OFFLINE: "Le Raspberry Pi ne donne plus de nouvelles. Vérifiez le câble et le courant.",
};

/** Un prédateur signalé récemment et pas encore lu rend l'ouverture manuelle risquée. */
export const PREDATOR_WINDOW_MS = 30 * 60_000;

export function recentPredator(alerts: CoopAlert[], now: Date): CoopAlert | undefined {
  return alerts.find(
    (alert) =>
      alert.alert_type === "PREDATOR_DETECTED" &&
      !alert.acknowledged &&
      now.getTime() - new Date(alert.created_at).getTime() < PREDATOR_WINDOW_MS,
  );
}

export function formatTime(iso: string): string {
  return new Date(iso).toLocaleTimeString("fr-BE", { hour: "2-digit", minute: "2-digit" });
}

export function formatDateTime(iso: string): string {
  const date = new Date(iso);
  const day = date.toLocaleDateString("fr-BE", { day: "numeric", month: "short" });
  return `${day} à ${formatTime(iso)}`;
}
