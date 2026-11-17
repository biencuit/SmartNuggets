import { act, renderHook } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { FakeEventSource } from "../test/FakeEventSource";
import { mockFetch } from "../test/fetchMock";
import { makeStatus } from "../test/statusFixture";
import { STREAM_RETRY_MS, STREAM_SILENCE_MS, useCoopStatus } from "./useCoopStatus";

function renderStatus() {
  mockFetch({
    "GET /api/v1/coops/coop_01/status": () => ({
      body: makeStatus({ inside_count: 6, outside_count: 4 }),
    }),
  });
  return renderHook(() => useCoopStatus("coop_01", "jeton"));
}

/** Avance l'horloge (minuteries simulées) et laisse React traiter les mises à jour. */
async function wait(ms: number) {
  await act(async () => {
    await vi.advanceTimersByTimeAsync(ms);
  });
}

describe("useCoopStatus - flux temps réel qui se rouvre tout seul", () => {
  beforeEach(() => {
    vi.useFakeTimers();
  });

  afterEach(() => {
    vi.useRealTimers();
  });

  it("rouvre le flux que le navigateur a abandonné (502 pendant un déploiement)", async () => {
    const { result } = renderStatus();
    await wait(0);
    const first = FakeEventSource.instances[0];
    act(() => {
      first?.emit("open");
    });
    expect(result.current.live).toBe(true);

    act(() => {
      first?.fail();
    });
    expect(result.current.live).toBe(false);
    await wait(STREAM_RETRY_MS - 1);
    expect(FakeEventSource.instances).toHaveLength(1);
    await wait(1);
    expect(FakeEventSource.instances).toHaveLength(2);

    // Nouvel échec : on attend deux fois plus longtemps avant de réessayer.
    act(() => {
      FakeEventSource.instances[1]?.fail();
    });
    await wait(STREAM_RETRY_MS);
    expect(FakeEventSource.instances).toHaveLength(2);
    await wait(STREAM_RETRY_MS);
    expect(FakeEventSource.instances).toHaveLength(3);

    // L'API est revenue : elle renvoie l'état actuel dès la connexion.
    const third = FakeEventSource.instances[2];
    expect(third?.url).toBe(first?.url);
    act(() => {
      third?.emit("open");
      third?.emit("status", makeStatus({ inside_count: 9, outside_count: 1 }));
    });
    expect(result.current.live).toBe(true);
    expect(result.current.status?.inside_count).toBe(9);
    expect(result.current.status?.outside_count).toBe(1);
  });

  it("garde le flux tant que le serveur donne des nouvelles, le rouvre s'il se tait", async () => {
    renderStatus();
    await wait(0);
    const first = FakeEventSource.instances[0];
    act(() => {
      first?.emit("open");
    });

    // Le serveur envoie un ping toutes les 15 s : le flux est vivant.
    for (let i = 0; i < 4; i += 1) {
      await wait(15_000);
      act(() => {
        first?.emit("ping", {});
      });
    }
    expect(FakeEventSource.instances).toHaveLength(1);

    // Connexion morte sans erreur (proxy, réseau mobile) : plus rien n'arrive.
    await wait(STREAM_SILENCE_MS);
    expect(first?.closed).toBe(true);
    expect(FakeEventSource.instances).toHaveLength(2);
  });

  it("ne rouvre plus rien une fois la page quittée", async () => {
    const { unmount } = renderStatus();
    await wait(0);
    const first = FakeEventSource.instances[0];

    unmount();
    act(() => {
      first?.fail();
    });
    await wait(STREAM_SILENCE_MS + STREAM_RETRY_MS);

    expect(first?.closed).toBe(true);
    expect(FakeEventSource.instances).toHaveLength(1);
  });
});
