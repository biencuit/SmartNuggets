import { act, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it } from "vitest";

import type { Coop, CoopCreate } from "../api/client";
import { TOKEN_KEY } from "../auth/context";
import { FakeEventSource } from "../test/FakeEventSource";
import { mockFetch, USER } from "../test/fetchMock";
import { renderApp } from "../test/renderApp";
import { makeStatus } from "../test/statusFixture";

const MARC: Coop = { id: "coop_01", name: "Chez Marc", total_hens: 10 };
const JARDIN: Coop = { id: "coop_02", name: "Au fond du jardin", total_hens: 4 };

/**
 * Éleveur connecté qui possède `coops` (la liste grandit quand il en ajoute un). Chaque
 * poulailler connu répond avec son état, sans historique ni alerte.
 */
function setup(coops: Coop[], options: { path?: string; createStatus?: number } = {}) {
  localStorage.setItem(TOKEN_KEY, "jeton secret");
  const routes: Parameters<typeof mockFetch>[0] = {
    "GET /api/v1/auth/me": () => ({ body: USER }),
    "GET /api/v1/coops": () => ({ body: coops }),
    "POST /api/v1/coops": (call) => {
      if (options.createStatus) {
        return {
          status: options.createStatus,
          body: { detail: "Identifiant ou code d'appairage incorrect" },
        };
      }
      const sent = JSON.parse(call.body ?? "{}") as CoopCreate;
      const created: Coop = { id: sent.id, name: sent.name, total_hens: sent.total_hens };
      coops.push(created);
      return { status: 201, body: created };
    },
  };
  for (const coop of [MARC, JARDIN]) {
    const base = `/api/v1/coops/${coop.id}`;
    routes[`GET ${base}/status`] = () => ({
      body: makeStatus({ coop_id: coop.id, name: coop.name }),
    });
    routes[`GET ${base}/events?limit=200`] = () => ({ body: [] });
    routes[`GET ${base}/alerts?limit=50`] = () => ({ body: [] });
  }
  const calls = mockFetch(routes);
  renderApp(options.path ?? "/");
  return calls;
}

const CODE = "K7QM-3XRA-PZ8D";

async function fillCoopForm(id: string, name: string, hens: string, code = CODE) {
  const user = userEvent.setup();
  await user.type(await screen.findByLabelText("Identifiant du poulailler"), id);
  await user.type(screen.getByLabelText("Code d'appairage"), code);
  await user.type(screen.getByLabelText("Nom"), name);
  await user.type(screen.getByLabelText("Nombre de poules"), hens);
  await user.click(screen.getByRole("button", { name: "Ajouter le poulailler" }));
}

describe("HomePage - l'accueil est le tableau de bord", () => {
  it("affiche l'état puis le met à jour à chaque message du flux", async () => {
    setup([MARC]);

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
    setup([MARC]);
    await screen.findByText("87 %");

    act(() => {
      screen.getByRole("button", { name: "Déconnexion" }).click();
    });

    expect(FakeEventSource.instances.every((source) => source.closed)).toBe(true);
  });

  it("propose d'ajouter un poulailler au compte qui n'en a pas, puis affiche son tableau de bord", async () => {
    const calls = setup([]);

    expect(await screen.findByText(/Aucun poulailler n'est encore associé/)).toBeInTheDocument();
    await fillCoopForm("coop_01", "Chez Marc", "10");

    const created = calls.find((call) => call.method === "POST" && call.url === "/api/v1/coops");
    expect(JSON.parse(created?.body ?? "{}")).toEqual({
      id: "coop_01",
      claim_code: CODE,
      name: "Chez Marc",
      total_hens: 10,
    });
    expect(created?.headers.Authorization).toBe("Bearer jeton secret");
    expect(await screen.findByText("87 %")).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "Chez Marc" })).toBeInTheDocument();
    expect(FakeEventSource.instances.at(-1)?.url).toContain("/coops/coop_01/stream");
  });

  it("affiche le refus de l'API quand l'identifiant ou le code est faux", async () => {
    setup([], { createStatus: 403 });

    await fillCoopForm("coop_01", "Chez Marc", "10");

    expect(await screen.findByRole("alert")).toHaveTextContent(
      "Identifiant ou code d'appairage incorrect",
    );
    expect(FakeEventSource.instances).toHaveLength(0);
  });

  it("refuse un code d'appairage trop court sans appeler l'API", async () => {
    const calls = setup([]);

    await fillCoopForm("coop_01", "Chez Marc", "10", "K7QM-3XRA");

    expect(await screen.findByRole("alert")).toHaveTextContent(/fait 12 caractères/);
    expect(calls.some((call) => call.method === "POST")).toBe(false);
  });

  it("refuse un identifiant invalide sans appeler l'API", async () => {
    const calls = setup([]);

    await fillCoopForm("poulailler n°1", "Chez Marc", "10");

    expect(await screen.findByRole("alert")).toHaveTextContent(/ne peut contenir que des lettres/);
    expect(calls.some((call) => call.method === "POST")).toBe(false);
  });

  it("passe d'un poulailler à l'autre", async () => {
    setup([MARC, JARDIN]);
    const user = userEvent.setup();

    await screen.findByText("87 %");
    expect(screen.getByRole("button", { name: "Chez Marc" })).toHaveAttribute(
      "aria-pressed",
      "true",
    );

    await user.click(screen.getByRole("button", { name: "Au fond du jardin" }));

    expect(await screen.findByRole("heading", { name: "Au fond du jardin" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Au fond du jardin" })).toHaveAttribute(
      "aria-pressed",
      "true",
    );
    expect(FakeEventSource.instances.at(-1)?.url).toContain("/coops/coop_02/stream");
    expect(FakeEventSource.instances[0]?.closed).toBe(true);
  });

  it("signale un poulailler qui n'est pas au compte, sans interroger l'API", async () => {
    const calls = setup([MARC], { path: "/poulaillers/coop_99" });

    expect(
      await screen.findByText(/« coop_99 » n'est pas associé à votre compte/),
    ).toBeInTheDocument();
    expect(calls.some((call) => call.url.includes("coop_99"))).toBe(false);
    expect(FakeEventSource.instances).toHaveLength(0);
  });
});
