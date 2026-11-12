import { describe, expect, it } from "vitest";

import {
  DEFAULT_FILTERS,
  filtersFromParams,
  filtersToParams,
  type HistoryFilters,
  periodRange,
  rangeError,
} from "./period";

// Les tests tournent à l'heure de Bruxelles (vite.config.ts) : mardi 10/11/2026, 11:40.
const NOW = new Date(2026, 10, 10, 11, 40);

function filters(overrides: Partial<HistoryFilters>): HistoryFilters {
  return { ...DEFAULT_FILTERS, ...overrides };
}

function iso(range: { since: Date | null; until: Date | null }) {
  return [range.since?.toISOString() ?? null, range.until?.toISOString() ?? null];
}

describe("périodes de l'historique, en heure locale", () => {
  it("aujourd'hui et hier vont de minuit à minuit (heure de Bruxelles = UTC+1 en hiver)", () => {
    expect(iso(periodRange(filters({ period: "aujourdhui" }), NOW))).toEqual([
      "2026-11-09T23:00:00.000Z",
      "2026-11-10T23:00:00.000Z",
    ]);
    expect(iso(periodRange(filters({ period: "hier" }), NOW))).toEqual([
      "2026-11-08T23:00:00.000Z",
      "2026-11-09T23:00:00.000Z",
    ]);
  });

  it("7 et 30 derniers jours comprennent aujourd'hui", () => {
    expect(iso(periodRange(filters({ period: "7j" }), NOW))).toEqual([
      "2026-11-03T23:00:00.000Z",
      "2026-11-10T23:00:00.000Z",
    ]);
    expect(iso(periodRange(filters({ period: "30j" }), NOW))).toEqual([
      "2026-10-11T22:00:00.000Z", // le 12/10 était encore à l'heure d'été (UTC+2)
      "2026-11-10T23:00:00.000Z",
    ]);
  });

  it("le jour du passage à l'heure d'hiver dure 25 heures", () => {
    const range = periodRange(filters({ period: "hier" }), new Date(2026, 9, 26, 9, 0));
    expect(iso(range)).toEqual(["2026-10-24T22:00:00.000Z", "2026-10-25T23:00:00.000Z"]);
    const hours = ((range.until?.getTime() ?? 0) - (range.since?.getTime() ?? 0)) / 3_600_000;
    expect(hours).toBe(25);
  });

  it("tout l'historique n'a pas de limite", () => {
    expect(iso(periodRange(filters({ period: "tout" }), NOW))).toEqual([null, null]);
  });

  it("dates au choix : le jour de fin est inclus", () => {
    const custom = filters({ period: "perso", from: "2026-11-01", to: "2026-11-03" });
    expect(iso(periodRange(custom, NOW))).toEqual([
      "2026-10-31T23:00:00.000Z",
      "2026-11-03T23:00:00.000Z",
    ]);
    expect(iso(periodRange(filters({ period: "perso", from: "2026-11-01" }), NOW))).toEqual([
      "2026-10-31T23:00:00.000Z",
      null,
    ]);
  });

  it("refuse une date de fin avant la date de début", () => {
    expect(rangeError(filters({ period: "perso", from: "2026-11-05", to: "2026-11-01" }))).toMatch(
      /date de fin/,
    );
    expect(rangeError(filters({ period: "perso", from: "2026-11-05", to: "2026-11-05" }))).toBe(
      null,
    );
    expect(rangeError(filters({ period: "7j", from: "2026-11-05", to: "2026-11-01" }))).toBe(null);
  });
});

describe("filtres dans l'URL", () => {
  it("lit les catégories, la période et les dates", () => {
    const params = new URLSearchParams(
      "categorie=alerts&categorie=entries&periode=perso&du=2026-11-01&au=2026-11-09",
    );
    expect(filtersFromParams(params)).toEqual({
      categories: ["entries", "alerts"], // toujours dans le même ordre
      period: "perso",
      from: "2026-11-01",
      to: "2026-11-09",
    });
  });

  it("ignore les valeurs inconnues ou mal formées", () => {
    const params = new URLSearchParams("categorie=poules&periode=demain&du=hier&au=2026-13");
    expect(filtersFromParams(params)).toEqual({ ...DEFAULT_FILTERS, from: null, to: null });
  });

  it("écrit une URL courte : les valeurs par défaut sont omises", () => {
    expect(filtersToParams(DEFAULT_FILTERS).toString()).toBe("");
    expect(
      filtersToParams(filters({ categories: ["alerts", "entries"], period: "hier" })).toString(),
    ).toBe("categorie=entries&categorie=alerts&periode=hier");
    // Les dates ne sont gardées que pour la période « perso ».
    expect(filtersToParams(filters({ period: "30j", from: "2026-11-01" })).toString()).toBe(
      "periode=30j",
    );
  });

  it("aller-retour : écrire puis relire donne les mêmes filtres", () => {
    const original = filters({
      categories: ["exits", "door"],
      period: "perso",
      from: "2026-10-20",
      to: "2026-10-31",
    });
    expect(filtersFromParams(filtersToParams(original))).toEqual(original);
  });
});
