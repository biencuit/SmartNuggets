import { describe, expect, it } from "vitest";

import type { CoopEvent, EventType, TriggerSource } from "../api/client";
import { availableDays, dayKey, dayLabel, summarizeDay } from "./history";

// Heures locales : les tests ne dépendent pas du fuseau de la machine.
const at = (day: number, hour: number, minute = 0) =>
  new Date(2026, 10, day, hour, minute).toISOString();

let nextId = 1;
function event(
  type: EventType,
  occurredAt: string,
  trigger: TriggerSource | null = "AI_AUTO",
): CoopEvent {
  return {
    id: nextId++,
    event_type: type,
    trigger_source: trigger,
    inside_count_after: null,
    ai_confidence: null,
    occurred_at: occurredAt,
  };
}

describe("summarizeDay", () => {
  it("compte les mouvements et calcule les périodes d'ouverture", () => {
    const events = [
      event("DOOR_OPEN", at(3, 7, 0)),
      event("HEN_EXIT", at(3, 7, 1)),
      event("DOOR_CLOSE", at(3, 7, 2)),
      event("DOOR_OPEN", at(3, 19, 0), "MANUAL_APP"),
      event("HEN_ENTRY", at(3, 19, 5)),
      event("DOOR_CLOSE", at(3, 19, 30)),
      event("DOOR_OPEN", at(2, 8, 0)), // la veille : ignoré
    ];

    const summary = summarizeDay(events, "2026-11-03", new Date(2026, 10, 3, 22, 0));

    expect(summary.openings).toBe(2);
    expect(summary.closings).toBe(2);
    expect(summary.manualMoves).toBe(1);
    expect(summary.entries).toBe(1);
    expect(summary.exits).toBe(1);
    expect(summary.firstOpening).toBe(at(3, 7, 0));
    expect(summary.lastClosing).toBe(at(3, 19, 30));
    expect(summary.openMinutes).toBe(32);
    expect(summary.intervals).toEqual([
      { start: 7 * 3_600_000, end: (7 * 60 + 2) * 60_000 },
      { start: 19 * 3_600_000, end: (19 * 60 + 30) * 60_000 },
    ]);
    expect(summary.events.map((e) => e.occurred_at)).toEqual(
      [...summary.events.map((e) => e.occurred_at)].sort(),
    );
  });

  it("prolonge une porte encore ouverte jusqu'à maintenant", () => {
    const summary = summarizeDay(
      [event("DOOR_OPEN", at(3, 9, 0))],
      "2026-11-03",
      new Date(2026, 10, 3, 9, 45),
    );
    expect(summary.openMinutes).toBe(45);
    expect(summary.lastClosing).toBeNull();
  });
});

describe("jours de l'historique", () => {
  const now = new Date(2026, 10, 3, 12, 0);

  it("liste les jours du plus récent au plus ancien, avec aujourd'hui", () => {
    const days = availableDays([event("DOOR_OPEN", at(1, 8)), event("DOOR_OPEN", at(2, 8))], now);
    expect(days).toEqual(["2026-11-03", "2026-11-02", "2026-11-01"]);
  });

  it("nomme aujourd'hui et hier", () => {
    expect(dayKey(now)).toBe("2026-11-03");
    expect(dayLabel("2026-11-03", now)).toBe("Aujourd'hui");
    expect(dayLabel("2026-11-02", now)).toBe("Hier");
  });
});
