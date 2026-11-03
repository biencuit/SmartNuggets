import { describe, expect, it } from "vitest";

import { batteryTone, cameraState, formatLastSeen } from "./format";

const NOW = new Date("2026-11-03T12:00:00Z");

describe("formatLastSeen", () => {
  it.each([
    [null, "jamais"],
    ["2026-11-03T11:59:30Z", "à l'instant"],
    ["2026-11-03T11:57:00Z", "il y a 3 min"],
    ["2026-11-03T09:00:00Z", "il y a 3 h"],
  ])("%s -> %s", (lastSeen, expected) => {
    expect(formatLastSeen(lastSeen, NOW)).toBe(expected);
  });

  it("donne la date au-delà d'un jour", () => {
    expect(formatLastSeen("2026-11-01T08:00:00Z", NOW)).toMatch(/^le 01\/11 à \d{2}:\d{2}$/);
  });
});

describe("batteryTone", () => {
  it.each([
    [null, "unknown"],
    [10, "danger"],
    [19, "danger"],
    [20, "warning"],
    [39, "warning"],
    [40, "ok"],
  ] as const)("%s %% -> %s", (battery, tone) => {
    expect(batteryTone(battery)).toBe(tone);
  });
});

describe("cameraState", () => {
  it("distingue OK, en panne et inconnue", () => {
    expect(cameraState(true).label).toBe("OK");
    expect(cameraState(false)).toEqual({ label: "En panne", tone: "danger" });
    expect(cameraState(null).label).toBe("Inconnue");
  });
});
