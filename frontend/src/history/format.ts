/** Petites fonctions d'affichage de la page Historique (#27), testées seules. */

import type { HabitHour } from "../api/client";

/** « 1 poule », « 2 poules », « 0 poule ». */
export function plural(count: number, singular: string, pluralForm: string): string {
  return `${String(count)} ${count > 1 ? pluralForm : singular}`;
}

/** « 07:15:00 » → « 07:15 » ; null → tiret. */
export function clock(value: string | null): string {
  return value ? value.slice(0, 5) : "—";
}

/** Fuseau du navigateur, pour que « hier » et « 7 h » soient ceux de l'éleveur. */
export function browserTimeZone(): string {
  return Intl.DateTimeFormat().resolvedOptions().timeZone || "Europe/Brussels";
}

/** Graduations « rondes » de l'axe vertical (pas de 1, 2 ou 5 × 10^n, 4 intervalles environ). */
export function niceScale(max: number): { top: number; step: number } {
  if (max <= 0) {
    return { top: 4, step: 1 };
  }
  const rough = max / 4;
  const power = 10 ** Math.floor(Math.log10(rough));
  const step = [1, 2, 5, 10].map((m) => m * power).find((s) => s >= rough) ?? 10 * power;
  return { top: Math.ceil(max / step) * step, step: Math.max(step, 1) };
}

function busiest(hours: HabitHour[], key: "exits" | "entries"): HabitHour | undefined {
  return hours.reduce<HabitHour | undefined>(
    (best, hour) => (hour[key] > 0 && (!best || hour[key] > best[key]) ? hour : best),
    undefined,
  );
}

/** Résumé du graphique par heure, lu par les lecteurs d'écran à la place des barres. */
export function chartSummary(hours: HabitHour[]): string {
  const exit = busiest(hours, "exits");
  const entry = busiest(hours, "entries");
  if (!exit && !entry) {
    return "Aucun passage sur la période.";
  }
  const parts: string[] = [];
  if (exit) {
    parts.push(
      `Sorties surtout entre ${String(exit.hour)} h et ${String(exit.hour + 1)} h (${plural(exit.exits, "sortie", "sorties")}).`,
    );
  }
  if (entry) {
    parts.push(
      `Retours surtout entre ${String(entry.hour)} h et ${String(entry.hour + 1)} h (${plural(entry.entries, "entrée", "entrées")}).`,
    );
  }
  return parts.join(" ");
}
