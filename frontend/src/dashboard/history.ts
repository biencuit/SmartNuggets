/** Regroupement de l'historique par jour (heure locale) pour le journal de la porte. */

import type { CoopEvent } from "../api/client";

const DAY_MS = 24 * 60 * 60_000;

/** Clé `AAAA-MM-JJ` du jour local d'une date. */
export function dayKey(date: Date): string {
  const month = String(date.getMonth() + 1).padStart(2, "0");
  const day = String(date.getDate()).padStart(2, "0");
  return `${String(date.getFullYear())}-${month}-${day}`;
}

export function startOfDay(key: string): Date {
  const [year = 0, month = 1, day = 1] = key.split("-").map(Number);
  return new Date(year, month - 1, day);
}

/** Jours présents dans l'historique, du plus récent au plus ancien ; aujourd'hui toujours inclus. */
export function availableDays(events: CoopEvent[], now: Date): string[] {
  const keys = new Set([dayKey(now)]);
  for (const event of events) {
    keys.add(dayKey(new Date(event.occurred_at)));
  }
  return [...keys].sort().reverse();
}

export function dayLabel(key: string, now: Date): string {
  if (key === dayKey(now)) {
    return "Aujourd'hui";
  }
  if (key === dayKey(new Date(now.getTime() - DAY_MS))) {
    return "Hier";
  }
  return startOfDay(key).toLocaleDateString("fr-BE", {
    weekday: "short",
    day: "numeric",
    month: "short",
  });
}

export interface OpenInterval {
  /** Début et fin en millisecondes depuis minuit. */
  start: number;
  end: number;
}

export interface DaySummary {
  /** Événements du jour, du plus ancien au plus récent. */
  events: CoopEvent[];
  openings: number;
  closings: number;
  manualMoves: number;
  entries: number;
  exits: number;
  firstOpening: string | null;
  lastClosing: string | null;
  intervals: OpenInterval[];
  /** Durée totale d'ouverture en minutes. */
  openMinutes: number;
}

/**
 * Résumé d'une journée. Une ouverture sans fermeture ce jour-là dure jusqu'à minuit, ou
 * jusqu'à maintenant pour aujourd'hui.
 */
export function summarizeDay(events: CoopEvent[], key: string, now: Date): DaySummary {
  const dayStart = startOfDay(key).getTime();
  const dayEnd = dayStart + DAY_MS;
  const ofDay = events
    .filter((event) => dayKey(new Date(event.occurred_at)) === key)
    .sort((a, b) => a.occurred_at.localeCompare(b.occurred_at));

  const intervals: OpenInterval[] = [];
  let openedAt: number | null = null;
  let firstOpening: string | null = null;
  let lastClosing: string | null = null;
  let openings = 0;
  let closings = 0;
  let manualMoves = 0;
  let entries = 0;
  let exits = 0;

  for (const event of ofDay) {
    const at = new Date(event.occurred_at).getTime();
    switch (event.event_type) {
      case "DOOR_OPEN":
        openings += 1;
        firstOpening ??= event.occurred_at;
        openedAt ??= at;
        if (event.trigger_source === "MANUAL_APP") manualMoves += 1;
        break;
      case "DOOR_CLOSE":
        closings += 1;
        lastClosing = event.occurred_at;
        if (event.trigger_source === "MANUAL_APP") manualMoves += 1;
        if (openedAt !== null) {
          intervals.push({ start: openedAt - dayStart, end: at - dayStart });
          openedAt = null;
        }
        break;
      case "HEN_ENTRY":
        entries += 1;
        break;
      case "HEN_EXIT":
        exits += 1;
        break;
      case "OBSTACLE":
        break;
    }
  }
  if (openedAt !== null) {
    const end = Math.min(dayEnd, Math.max(openedAt, now.getTime()));
    intervals.push({ start: openedAt - dayStart, end: end - dayStart });
  }

  const openMs = intervals.reduce((total, interval) => total + interval.end - interval.start, 0);
  return {
    events: ofDay,
    openings,
    closings,
    manualMoves,
    entries,
    exits,
    firstOpening,
    lastClosing,
    intervals,
    openMinutes: Math.round(openMs / 60_000),
  };
}

export { DAY_MS };
