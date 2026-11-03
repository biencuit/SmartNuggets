import type { CoopStatus } from "../api/client";

export function makeStatus(overrides: Partial<CoopStatus> = {}): CoopStatus {
  return {
    coop_id: "coop_01",
    name: "Chez Marc",
    door_state: "OPEN",
    inside_count: 8,
    total_hens: 10,
    outside_count: 2,
    battery: 87,
    auto_close_time: "21:30:00",
    last_seen_at: "2026-11-03T08:00:00Z",
    online: true,
    camera_ok: true,
    ...overrides,
  };
}
