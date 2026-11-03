import { act, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it } from "vitest";

import type { CoopAlert, CoopEvent } from "../api/client";
import { TOKEN_KEY } from "../auth/context";
import { FakeEventSource } from "../test/FakeEventSource";
import { mockFetch, USER } from "../test/fetchMock";
import { renderApp } from "../test/renderApp";
import { makeStatus } from "../test/statusFixture";

const BASE = "/api/v1/coops/coop_01";

function makeEvent(overrides: Partial<CoopEvent> = {}): CoopEvent {
  return {
    id: 1,
    event_type: "DOOR_OPEN",
    trigger_source: "AI_AUTO",
    inside_count_after: 8,
    ai_confidence: 0.93,
    occurred_at: new Date(Date.now() - 60 * 60_000).toISOString(),
    ...overrides,
  };
}

function makeAlert(overrides: Partial<CoopAlert> = {}): CoopAlert {
  return {
    id: 7,
    alert_type: "DOOR_BLOCKED",
    severity: "WARNING",
    ai_confidence: null,
    image_url: null,
    acknowledged: false,
    created_at: new Date(Date.now() - 2 * 60 * 60_000).toISOString(),
    ...overrides,
  };
}

function setup(
  options: {
    status?: Parameters<typeof makeStatus>[0];
    events?: CoopEvent[];
    alerts?: CoopAlert[];
    commandStatus?: number;
    /** Le poulailler a disparu côté serveur : toutes ses routes répondent 404. */
    gone?: boolean;
  } = {},
) {
  localStorage.setItem(TOKEN_KEY, "jeton");
  const gone = { status: 404, body: { detail: "Poulailler 'coop_01' introuvable" } };
  const calls = mockFetch({
    "GET /api/v1/auth/me": () => ({ body: USER }),
    "GET /api/v1/coops": () => ({ body: [{ id: "coop_01", name: "Chez Marc", total_hens: 10 }] }),
    [`GET ${BASE}/status`]: () => (options.gone ? gone : { body: makeStatus(options.status) }),
    [`GET ${BASE}/events?limit=200`]: () =>
      options.gone ? gone : { body: options.events ?? [makeEvent()] },
    [`GET ${BASE}/alerts?limit=50`]: () =>
      options.gone ? gone : { body: options.alerts ?? [makeAlert()] },
    [`POST ${BASE}/command`]: () =>
      options.commandStatus
        ? { status: options.commandStatus, body: { detail: "Le poulailler est injoignable" } }
        : { status: 202, body: { command_id: "c1", coop_id: "coop_01", action: "OPEN" } },
    [`POST ${BASE}/alerts/7/ack`]: () => ({ body: makeAlert({ acknowledged: true }) }),
  });
  renderApp("/");
  return calls;
}

describe("CoopDashboard - tableau de bord du poulailler, sur l'accueil", () => {
  it("affiche la porte, les poules, l'historique du jour et les alertes", async () => {
    setup({ status: { door_state: "CLOSED", inside_count: 8, outside_count: 2 } });

    expect(await screen.findByText("Fermée")).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "Chez Marc" })).toBeInTheDocument();
    const hens = screen.getByRole("region", { name: "Poules" });
    expect(within(hens).getByText("8")).toBeInTheDocument();
    expect(within(hens).getByText("2")).toBeInTheDocument();

    const history = await screen.findByRole("region", { name: "Historique de la porte" });
    expect(within(history).getByRole("button", { name: "Aujourd'hui" })).toHaveAttribute(
      "aria-pressed",
      "true",
    );
    expect(within(history).getByText("Porte ouverte")).toBeInTheDocument();
    expect(within(history).getByText("Caméra")).toBeInTheDocument();

    expect(screen.getByText("Porte bloquée")).toBeInTheDocument();
  });

  it("envoie la commande d'ouverture puis attend la réponse du poulailler", async () => {
    const calls = setup({ status: { door_state: "CLOSED" } });
    const user = userEvent.setup();

    await user.click(await screen.findByRole("button", { name: "Ouvrir la porte" }));

    const command = calls.find((call) => call.url === `${BASE}/command`);
    expect(command?.method).toBe("POST");
    expect(JSON.parse(command?.body ?? "{}")).toEqual({ action: "OPEN" });
    expect(command?.headers.Authorization).toBe("Bearer jeton");
    expect(screen.getByRole("status")).toHaveTextContent("En attente de la réponse");

    act(() => {
      FakeEventSource.instances[0]?.emit("status", makeStatus({ door_state: "OPEN" }));
    });
    expect(screen.getByText("Ouverte")).toBeInTheDocument();
    expect(screen.queryByText(/En attente de la réponse/)).not.toBeInTheDocument();
  });

  it("affiche l'erreur de l'API si la commande échoue", async () => {
    setup({ status: { door_state: "CLOSED" }, commandStatus: 503 });
    const user = userEvent.setup();

    await user.click(await screen.findByRole("button", { name: "Ouvrir la porte" }));

    expect(await screen.findByText("Le poulailler est injoignable")).toBeInTheDocument();
  });

  it("désactive les commandes quand le poulailler est hors ligne", async () => {
    setup({ status: { door_state: "CLOSED", online: false } });

    expect(await screen.findByRole("button", { name: "Ouvrir la porte" })).toBeDisabled();
    expect(screen.getByText(/les commandes sont indisponibles/)).toBeInTheDocument();
  });

  it("demande confirmation avant d'ouvrir après une alerte prédateur", async () => {
    const calls = setup({
      status: { door_state: "CLOSED" },
      alerts: [
        makeAlert({
          alert_type: "PREDATOR_DETECTED",
          severity: "CRITICAL",
          created_at: new Date(Date.now() - 5 * 60_000).toISOString(),
        }),
      ],
    });
    const user = userEvent.setup();

    await screen.findByText(/Évitez d'ouvrir la porte/);
    await user.click(screen.getByRole("button", { name: "Ouvrir la porte" }));
    expect(calls.some((call) => call.url === `${BASE}/command`)).toBe(false);

    await user.click(screen.getByRole("button", { name: "Ouvrir quand même" }));
    expect(calls.some((call) => call.url === `${BASE}/command`)).toBe(true);
  });

  it("corrige le compteur de poules (CALIBRATE)", async () => {
    const calls = setup({ status: { total_hens: 10, inside_count: 8 } });
    const user = userEvent.setup();

    await user.click(
      await screen.findByRole("button", { name: "Le compte est faux ? Le corriger" }),
    );
    const input = screen.getByLabelText("Nombre réel de poules dans le poulailler");
    await user.clear(input);
    await user.type(input, "10");
    await user.click(screen.getByRole("button", { name: "Corriger le compteur" }));

    const command = calls.find((call) => call.url === `${BASE}/command`);
    expect(JSON.parse(command?.body ?? "{}")).toEqual({ action: "CALIBRATE", inside_count: 10 });
    expect(screen.getByText("Correction envoyée au poulailler.")).toBeInTheDocument();
  });

  it("marque une alerte comme lue", async () => {
    const calls = setup();
    const user = userEvent.setup();

    await user.click(await screen.findByRole("button", { name: "Marquer comme lue" }));

    expect(calls.some((call) => call.url === `${BASE}/alerts/7/ack`)).toBe(true);
    expect(await screen.findByText("Aucune alerte à traiter.")).toBeInTheDocument();
  });

  it("ajoute en direct les passages et les alertes reçus par le flux", async () => {
    setup({ events: [], alerts: [] });
    await screen.findByText("Aucun mouvement enregistré ce jour-là.");

    act(() => {
      const source = FakeEventSource.instances[0];
      source?.emit(
        "event",
        makeEvent({ id: 42, event_type: "HEN_EXIT", occurred_at: new Date().toISOString() }),
      );
      source?.emit("alert", makeAlert({ id: 43, alert_type: "LOW_BATTERY" }));
    });

    expect(screen.getByText("Une poule est sortie")).toBeInTheDocument();
    expect(screen.getByText("Batterie faible")).toBeInTheDocument();
    expect(FakeEventSource.instances).toHaveLength(1);
  });

  it("affiche le dernier événement et le tient à jour", async () => {
    setup({
      events: [makeEvent({ occurred_at: new Date(Date.now() - 60 * 60_000).toISOString() })],
    });

    expect(await screen.findByText(/^Porte ouverte, le .+ \(Caméra\)$/)).toBeInTheDocument();

    act(() => {
      const source = FakeEventSource.instances[0];
      source?.emit(
        "event",
        makeEvent({
          id: 2,
          event_type: "HEN_ENTRY",
          trigger_source: null,
          occurred_at: new Date().toISOString(),
        }),
      );
      // Passage plus ancien, arrivé en retard (file d'attente du Pi après une coupure).
      source?.emit(
        "event",
        makeEvent({
          id: 3,
          event_type: "HEN_EXIT",
          occurred_at: new Date(Date.now() - 3 * 60 * 60_000).toISOString(),
        }),
      );
    });

    expect(screen.getByText(/^Une poule est rentrée, le .+\d$/)).toBeInTheDocument();
    expect(screen.queryByText(/^Porte ouverte, le /)).not.toBeInTheDocument();
  });

  it("n'affiche qu'une seule fois l'erreur d'un poulailler introuvable", async () => {
    setup({ gone: true });

    expect(await screen.findByText("Poulailler 'coop_01' introuvable")).toBeInTheDocument();
    // L'historique et les alertes échouent aussi : leur erreur ne doit pas se répéter.
    await act(async () => {
      await new Promise((resolve) => setTimeout(resolve, 0));
    });
    expect(screen.getAllByText(/introuvable/)).toHaveLength(1);
    expect(screen.queryByText("Chargement du poulailler…")).not.toBeInTheDocument();
  });
});
