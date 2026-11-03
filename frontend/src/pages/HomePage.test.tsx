import { act, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { TOKEN_KEY } from "../auth/context";
import { FakeEventSource } from "../test/FakeEventSource";
import { mockFetch, USER } from "../test/fetchMock";
import { renderApp } from "../test/renderApp";
import { makeStatus } from "../test/statusFixture";

describe("HomePage - état du système en temps réel", () => {
  it("affiche l'état puis le met à jour à chaque message du flux", async () => {
    localStorage.setItem(TOKEN_KEY, "jeton secret");
    mockFetch({
      "GET /api/v1/auth/me": () => ({ body: USER }),
      "GET /api/v1/coops": () => ({ body: [{ id: "coop_01", name: "Chez Marc", total_hens: 10 }] }),
      "GET /api/v1/coops/coop_01/status": () => ({ body: makeStatus({ battery: 87 }) }),
    });
    renderApp("/");

    expect(await screen.findByText("87 %")).toBeInTheDocument();
    const source = FakeEventSource.instances[0];
    expect(source?.url).toBe("/api/v1/coops/coop_01/stream?token=jeton%20secret");

    act(() => {
      source?.emit("open");
      source?.emit("status", makeStatus({ battery: 15, online: false }));
    });

    expect(screen.getByText("15 %")).toBeInTheDocument();
    expect(screen.getByText("Hors ligne")).toBeInTheDocument();
    expect(screen.getByRole("alert")).toHaveTextContent("Le poulailler ne répond plus");
    expect(screen.getByText("● en direct")).toBeInTheDocument();
  });

  it("ferme le flux à la déconnexion", async () => {
    localStorage.setItem(TOKEN_KEY, "jeton");
    mockFetch({
      "GET /api/v1/auth/me": () => ({ body: USER }),
      "GET /api/v1/coops": () => ({ body: [{ id: "coop_01", name: "Chez Marc", total_hens: 10 }] }),
      "GET /api/v1/coops/coop_01/status": () => ({ body: makeStatus() }),
    });
    renderApp("/");
    await screen.findByText("87 %");

    act(() => {
      screen.getByRole("button", { name: "Déconnexion" }).click();
    });

    expect(FakeEventSource.instances.every((source) => source.closed)).toBe(true);
  });
});
