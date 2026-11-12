/**
 * Filtres de la page Historique (#27) : types d'éléments et période.
 *
 * Les filtres vivent dans l'URL (`?categorie=entries&periode=hier`) : on peut recharger la
 * page, la mettre en favori ou revenir en arrière sans perdre sa recherche. Les périodes sont
 * calculées en heure locale (« hier » = de minuit à minuit), puis envoyées à l'API en UTC.
 */

import type { HistoryCategory } from "../api/client";
import { startOfDay } from "../dashboard/history";

export type Period = "aujourdhui" | "hier" | "7j" | "30j" | "tout" | "perso";

export interface HistoryFilters {
  /** Vide : tous les types. */
  categories: HistoryCategory[];
  period: Period;
  /** Période « perso » : jours locaux AAAA-MM-JJ, bornes incluses (null : pas de limite). */
  from: string | null;
  to: string | null;
}

export const CATEGORIES: HistoryCategory[] = ["entries", "exits", "door", "alerts"];

export const CATEGORY_LABELS: Record<HistoryCategory, string> = {
  entries: "Entrées",
  exits: "Sorties",
  door: "Porte",
  alerts: "Alertes",
};

export const PERIODS: Period[] = ["aujourdhui", "hier", "7j", "30j", "tout", "perso"];

export const PERIOD_LABELS: Record<Period, string> = {
  aujourdhui: "Aujourd'hui",
  hier: "Hier",
  "7j": "7 derniers jours",
  "30j": "30 derniers jours",
  tout: "Tout l'historique",
  perso: "Dates au choix",
};

export const DEFAULT_FILTERS: HistoryFilters = {
  categories: [],
  period: "7j",
  from: null,
  to: null,
};

const DATE_KEY = /^\d{4}-\d{2}-\d{2}$/;

function isCategory(value: string): value is HistoryCategory {
  return (CATEGORIES as string[]).includes(value);
}

function isPeriod(value: string | null): value is Period {
  return value !== null && (PERIODS as string[]).includes(value);
}

function dateKeyOrNull(value: string | null): string | null {
  return value !== null && DATE_KEY.test(value) ? value : null;
}

/** Lit les filtres de l'URL ; une valeur inconnue est ignorée (lien ancien ou modifié). */
export function filtersFromParams(params: URLSearchParams): HistoryFilters {
  const chosen = new Set(params.getAll("categorie").filter(isCategory));
  const period = params.get("periode");
  return {
    categories: CATEGORIES.filter((category) => chosen.has(category)),
    period: isPeriod(period) ? period : DEFAULT_FILTERS.period,
    from: dateKeyOrNull(params.get("du")),
    to: dateKeyOrNull(params.get("au")),
  };
}

/** Écrit les filtres dans l'URL ; les valeurs par défaut sont omises (URL courte). */
export function filtersToParams(filters: HistoryFilters): URLSearchParams {
  const params = new URLSearchParams();
  for (const category of CATEGORIES) {
    if (filters.categories.includes(category)) {
      params.append("categorie", category);
    }
  }
  if (filters.period !== DEFAULT_FILTERS.period) {
    params.set("periode", filters.period);
  }
  if (filters.period === "perso") {
    if (filters.from) params.set("du", filters.from);
    if (filters.to) params.set("au", filters.to);
  }
  return params;
}

/** Ajoute des jours au calendrier local : un jour de changement d'heure dure 23 h ou 25 h. */
export function addDays(date: Date, days: number): Date {
  const result = new Date(date);
  result.setDate(result.getDate() + days);
  return result;
}

function midnight(date: Date): Date {
  return new Date(date.getFullYear(), date.getMonth(), date.getDate());
}

export interface Range {
  /** Début inclus et fin exclue ; null : pas de limite. */
  since: Date | null;
  until: Date | null;
}

/** Bornes de la période, en heure locale, à l'instant `now`. */
export function periodRange(filters: HistoryFilters, now: Date): Range {
  const today = midnight(now);
  const tomorrow = addDays(today, 1);
  switch (filters.period) {
    case "aujourdhui":
      return { since: today, until: tomorrow };
    case "hier":
      return { since: addDays(today, -1), until: today };
    case "7j":
      return { since: addDays(today, -6), until: tomorrow };
    case "30j":
      return { since: addDays(today, -29), until: tomorrow };
    case "tout":
      return { since: null, until: null };
    case "perso":
      return {
        since: filters.from ? startOfDay(filters.from) : null,
        // Le jour de fin est inclus : la borne exclue est le lendemain à minuit.
        until: filters.to ? addDays(startOfDay(filters.to), 1) : null,
      };
  }
}

/** Message d'erreur si la période « perso » est incohérente, sinon null. */
export function rangeError(filters: HistoryFilters): string | null {
  if (filters.period === "perso" && filters.from && filters.to && filters.from > filters.to) {
    return "La date de fin doit être le même jour que la date de début, ou après.";
  }
  return null;
}
