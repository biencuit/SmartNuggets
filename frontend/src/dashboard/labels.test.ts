import { describe, expect, it } from "vitest";

import { ALERT_ADVICE, alertAdvice } from "./labels";

describe("alertAdvice", () => {
  it("donne le nombre de poules encore dehors", () => {
    expect(alertAdvice({ alert_type: "MISSING_HEN", missing_count: 2 })).toBe(
      "2 poules sont encore dehors à l'heure de fermeture.",
    );
    expect(alertAdvice({ alert_type: "MISSING_HEN", missing_count: 1 })).toBe(
      "1 poule est encore dehors à l'heure de fermeture.",
    );
  });

  it("garde le texte générique si le nombre est inconnu ou pour une autre alerte", () => {
    expect(alertAdvice({ alert_type: "MISSING_HEN", missing_count: null })).toBe(
      ALERT_ADVICE.MISSING_HEN,
    );
    expect(alertAdvice({ alert_type: "MISSING_HEN" })).toBe(ALERT_ADVICE.MISSING_HEN);
    expect(alertAdvice({ alert_type: "DOOR_BLOCKED", missing_count: 3 })).toBe(
      ALERT_ADVICE.DOOR_BLOCKED,
    );
  });
});
