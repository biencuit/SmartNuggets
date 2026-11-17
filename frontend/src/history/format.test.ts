import { describe, expect, it } from "vitest";

import type { HabitHour } from "../api/client";
import { browserTimeZone, chartSummary, clock, niceScale, plural } from "./format";

function hours(values: Record<number, [number, number]>): HabitHour[] {
  return Array.from({ length: 24 }, (_, hour) => ({
    hour,
    exits: values[hour]?.[0] ?? 0,
    entries: values[hour]?.[1] ?? 0,
  }));
}

describe("format de la page Historique", () => {
  it("accorde au pluriel à partir de 2", () => {
    expect(plural(0, "poule", "poules")).toBe("0 poule");
    expect(plural(1, "poule", "poules")).toBe("1 poule");
    expect(plural(2, "poule", "poules")).toBe("2 poules");
  });

  it("affiche les heures à la minute", () => {
    expect(clock("07:15:00")).toBe("07:15");
    expect(clock(null)).toBe("—");
  });

  it("prend le fuseau du navigateur", () => {
    expect(browserTimeZone()).toBe("Europe/Brussels");
  });

  it("choisit des graduations rondes", () => {
    expect(niceScale(0)).toEqual({ top: 4, step: 1 });
    expect(niceScale(3)).toEqual({ top: 3, step: 1 });
    expect(niceScale(37)).toEqual({ top: 40, step: 10 });
    expect(niceScale(18)).toEqual({ top: 20, step: 5 });
    expect(niceScale(120)).toEqual({ top: 150, step: 50 });
  });

  it("résume le graphique pour les lecteurs d'écran", () => {
    expect(chartSummary(hours({ 7: [34, 1], 8: [5, 0], 18: [0, 29], 19: [0, 3] }))).toBe(
      "Sorties surtout entre 7 h et 8 h (34 sorties). Retours surtout entre 18 h et 19 h (29 entrées).",
    );
    expect(chartSummary(hours({ 7: [1, 0] }))).toBe("Sorties surtout entre 7 h et 8 h (1 sortie).");
    expect(chartSummary(hours({}))).toBe("Aucun passage sur la période.");
  });
});
