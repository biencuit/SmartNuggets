import { fireEvent, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import type { Habits, HistoryItem, HistoryPage } from "../api/client";
import { TOKEN_KEY } from "../auth/context";
import { type Call, mockFetch, USER } from "../test/fetchMock";
import { renderApp } from "../test/renderApp";
import { makeStatus } from "../test/statusFixture";

// Les tests tournent à l'heure de Bruxelles (vite.config.ts). « Maintenant » est figé au
// mardi 10/11/2026 à 11:40 : les bornes des périodes sont donc connues à l'avance.
const NOW = new Date("2026-11-10T10:40:00Z");
const BASE = "/api/v1/coops/coop_01";
const PAGE = "/poulaillers/coop_01/historique";
// 7 derniers jours (filtre par défaut) : du 04/11 à 00:00 au 11/11 à 00:00, heure de Bruxelles.
const LAST_7_DAYS = "since=2026-11-03T23%3A00%3A00.000Z&until=2026-11-10T23%3A00%3A00.000Z";
const YESTERDAY = "since=2026-11-08T23%3A00%3A00.000Z&until=2026-11-09T23%3A00%3A00.000Z";
const HABITS_7 = `GET ${BASE}/habits?days=7&tz=Europe%2FBrussels`;

function historyUrl(params: string): string {
  return `GET ${BASE}/history?${params}`;
}

function makeItem(overrides: Partial<HistoryItem> = {}): HistoryItem {
  return {
    kind: "event",
    id: 1,
    type: "HEN_ENTRY",
    occurred_at: "2026-11-09T17:42:00Z",
    trigger_source: "AI_AUTO",
    inside_count_after: 9,
    severity: null,
    image_url: null,
    acknowledged: null,
    ...overrides,
  };
}

const FOX = makeItem({
  kind: "alert",
  id: 9,
  type: "PREDATOR_DETECTED",
  occurred_at: "2026-11-07T13:12:00Z",
  trigger_source: null,
  inside_count_after: null,
  severity: "CRITICAL",
  image_url: `${BASE}/alerts/9/image`,
  acknowledged: false,
});

function makeHabits(overrides: Partial<Habits> = {}): Habits {
  const hours = Array.from({ length: 24 }, (_, hour) => ({
    hour,
    exits: hour === 7 ? 12 : hour === 11 ? 3 : 0,
    entries: hour === 18 ? 10 : hour === 11 ? 3 : 0,
  }));
  return {
    timezone: "Europe/Brussels",
    days: [
      { day: "2026-11-08", exits: 9, entries: 9, first_exit: "07:05:00", last_entry: "18:55:00" },
      { day: "2026-11-09", exits: 6, entries: 4, first_exit: "07:19:00", last_entry: "18:39:00" },
      { day: "2026-11-10", exits: 0, entries: 0, first_exit: null, last_entry: null },
    ],
    hours,
    average_first_exit: "07:12:00",
    average_last_entry: "18:47:00",
    exits_per_day: 7.5,
    active_days: 2,
    total_exits: 15,
    total_entries: 13,
    ...overrides,
  };
}

function page(items: HistoryItem[], total = items.length): { body: HistoryPage } {
  return { body: { total, items } };
}

function setup(routes: Record<string, (call: Call) => { status?: number; body?: unknown }> = {}) {
  localStorage.setItem(TOKEN_KEY, "jeton");
  return mockFetch({
    "GET /api/v1/auth/me": () => ({ body: USER }),
    "GET /api/v1/coops": () => ({ body: [{ id: "coop_01", name: "Chez Marc", total_hens: 10 }] }),
    [HABITS_7]: () => ({ body: makeHabits() }),
    [historyUrl(`${LAST_7_DAYS}&limit=50&offset=0`)]: () => page([makeItem(), FOX]),
    ...routes,
  });
}

/** La section Journal, une fois la page chargée. */
function journal() {
  return screen.findByRole("region", { name: "Journal" });
}

beforeEach(() => {
  // Seule la date est figée : les minuteries restent réelles pour Testing Library.
  vi.useFakeTimers({ toFake: ["Date"] });
  vi.setSystemTime(NOW);
});

afterEach(() => {
  vi.useRealTimers();
});

describe("HistoryPage - historique complet et habitudes des poules (#27)", () => {
  it("affiche les habitudes : moyennes, graphique par heure et tableau par jour", async () => {
    setup();
    renderApp(PAGE);

    expect(await screen.findByRole("heading", { name: "Historique" })).toBeInTheDocument();
    expect(screen.getByText("Chez Marc")).toBeInTheDocument();
    const habits = screen.getByRole("region", { name: "Habitudes des poules" });
    expect(await within(habits).findByText("07:12")).toBeInTheDocument();
    expect(within(habits).getByText("18:47")).toBeInTheDocument();
    expect(within(habits).getByText("7,5")).toBeInTheDocument();
    expect(within(habits).getByText("sur 2 jours avec des passages")).toBeInTheDocument();
    expect(
      within(habits).getByRole("img", {
        name: /Sorties surtout entre 7 h et 8 h \(12 sorties\)\. Retours surtout entre 18 h et 19 h/,
      }),
    ).toBeInTheDocument();

    // Tableau du plus récent au plus ancien ; un jour sans passage affiche des tirets.
    const rows = within(within(habits).getByRole("table", { name: "Jour par jour" })).getAllByRole(
      "row",
    );
    expect(rows[1]).toHaveTextContent("Aujourd'hui00——");
    expect(rows[2]).toHaveTextContent("Hier6407:1918:39");
  });

  it("montre le détail d'une heure au survol du graphique", async () => {
    setup();
    renderApp(PAGE);

    fireEvent.mouseEnter(await screen.findByTestId("heure-7"));

    expect(screen.getByRole("status")).toHaveTextContent("7 h – 8 h · 12 sorties · 0 entrée");
  });

  it("passe des habitudes sur 7 jours à 30 jours", async () => {
    const calls = setup({
      [`GET ${BASE}/habits?days=30&tz=Europe%2FBrussels`]: () => ({
        body: makeHabits({ average_first_exit: "07:31:00" }),
      }),
    });
    renderApp(PAGE);
    const habits = await screen.findByRole("region", { name: "Habitudes des poules" });
    await within(habits).findByText("07:12");

    await userEvent.click(within(habits).getByRole("button", { name: "30 jours" }));

    expect(await within(habits).findByText("07:31")).toBeInTheDocument();
    expect(calls.some((call) => call.url.includes("habits?days=30"))).toBe(true);
  });

  it("dit quand il n'y a aucun passage sur la période", async () => {
    setup({
      [HABITS_7]: () => ({
        body: makeHabits({ active_days: 0, average_first_exit: null, average_last_entry: null }),
      }),
    });
    renderApp(PAGE);

    expect(
      await screen.findByText("Aucun passage de poule sur les 7 derniers jours."),
    ).toBeInTheDocument();
  });

  it("sans filtre : passages, porte et alertes mélangés, groupés par jour", async () => {
    const calls = setup();
    renderApp(PAGE);

    expect(await within(await journal()).findByText("2 résultats")).toBeInTheDocument();
    expect(within(await journal()).getByRole("button", { name: "Tout" })).toHaveAttribute(
      "aria-pressed",
      "true",
    );
    expect(within(await journal()).getByRole("combobox", { name: "Période" })).toHaveValue("7j");
    expect(
      within(await journal()).getByRole("heading", { name: "Hier · lundi 9 novembre" }),
    ).toBeInTheDocument();
    expect(within(await journal()).getByText("Une poule est rentrée")).toBeInTheDocument();
    expect(within(await journal()).getByText("Caméra · 9 poules dedans")).toBeInTheDocument();
    expect(
      within(await journal()).getByRole("heading", { name: "samedi 7 novembre" }),
    ).toBeVisible();
    expect(within(await journal()).getByText("Prédateur détecté")).toBeInTheDocument();
    expect(within(await journal()).getByText("Critique")).toBeInTheDocument();
    expect(calls.find((call) => call.url.includes("/history"))?.headers.Authorization).toBe(
      "Bearer jeton",
    );
  });

  it("scénario 1 : « Entrées » + « Hier » ne demande que les entrées d'hier", async () => {
    const calls = setup({
      [historyUrl(`category=entries&${LAST_7_DAYS}&limit=50&offset=0`)]: () =>
        page([makeItem(), makeItem({ id: 2, occurred_at: "2026-11-06T17:00:00Z" })]),
      [historyUrl(`category=entries&${YESTERDAY}&limit=50&offset=0`)]: () => page([makeItem()]),
    });
    renderApp(PAGE);
    await within(await journal()).findByText("2 résultats");

    await userEvent.click(within(await journal()).getByRole("button", { name: "Entrées" }));
    await userEvent.selectOptions(
      within(await journal()).getByRole("combobox", { name: "Période" }),
      "hier",
    );

    expect(await within(await journal()).findByText("1 résultat")).toBeInTheDocument();
    expect(within(await journal()).getByRole("button", { name: "Entrées" })).toHaveAttribute(
      "aria-pressed",
      "true",
    );
    expect(within(await journal()).getByRole("button", { name: "Tout" })).toHaveAttribute(
      "aria-pressed",
      "false",
    );
    expect(calls.at(-1)?.url).toBe(
      `${BASE}/history?category=entries&${YESTERDAY}&limit=50&offset=0`,
    );
  });

  it("reprend les filtres de l'URL (favori, bouton Retour)", async () => {
    const calls = setup({
      [historyUrl("category=exits&category=alerts&limit=50&offset=0")]: () => page([FOX]),
    });
    renderApp(`${PAGE}?categorie=alerts&categorie=exits&periode=tout`);

    expect(await within(await journal()).findByText("1 résultat")).toBeInTheDocument();
    expect(within(await journal()).getByRole("button", { name: "Sorties" })).toHaveAttribute(
      "aria-pressed",
      "true",
    );
    expect(within(await journal()).getByRole("button", { name: "Alertes" })).toHaveAttribute(
      "aria-pressed",
      "true",
    );
    expect(within(await journal()).getByRole("combobox", { name: "Période" })).toHaveValue("tout");
    expect(calls.some((call) => call.url.includes("since="))).toBe(false);
  });

  it("scénario 3 : affiche le total et charge la page suivante", async () => {
    const first = Array.from({ length: 50 }, (_, i) => makeItem({ id: 200 - i }));
    const second = Array.from({ length: 50 }, (_, i) => makeItem({ id: 150 - i }));
    const calls = setup({
      [historyUrl(`${LAST_7_DAYS}&limit=50&offset=0`)]: () => page(first, 120),
      [historyUrl(`${LAST_7_DAYS}&limit=50&offset=50`)]: () => page(second, 120),
    });
    renderApp(PAGE);

    expect(await within(await journal()).findByText("120 résultats")).toBeInTheDocument();
    expect(within(await journal()).getAllByText("Une poule est rentrée")).toHaveLength(50);

    await userEvent.click(
      within(await journal()).getByRole("button", { name: "Charger plus (70 restants)" }),
    );

    expect(
      await within(await journal()).findByRole("button", { name: "Charger plus (20 restants)" }),
    ).toBeInTheDocument();
    expect(within(await journal()).getAllByText("Une poule est rentrée")).toHaveLength(100);
    expect(calls.at(-1)?.url).toContain("offset=50");
  });

  it("scénario 4 : ouvre la photo d'une alerte depuis l'historique", async () => {
    setup();
    renderApp(PAGE);

    await userEvent.click(
      await within(await journal()).findByRole("button", { name: "Voir la photo" }),
    );

    expect(
      within(await journal()).getByRole("img", {
        name: "Photo prise lors de l'alerte « Prédateur détecté »",
      }),
    ).toHaveAttribute("src", `${BASE}/alerts/9/image?token=jeton`);
    await userEvent.click(
      within(await journal()).getByRole("button", { name: "Masquer la photo" }),
    );
    expect(within(await journal()).queryByRole("img")).not.toBeInTheDocument();
  });

  it("dates au choix : refuse une fin avant le début sans appeler l'API", async () => {
    const calls = setup();
    renderApp(`${PAGE}?periode=perso&du=2026-11-09&au=2026-11-01`);

    expect(await within(await journal()).findByRole("alert")).toHaveTextContent(
      "La date de fin doit être le même jour que la date de début, ou après.",
    );
    expect(within(await journal()).getByLabelText("Du")).toHaveValue("2026-11-09");
    expect(calls.some((call) => call.url.includes("/history"))).toBe(false);
  });

  it("dates au choix valides : du premier jour à minuit au lendemain du dernier", async () => {
    const calls = setup({
      [historyUrl(
        "since=2026-10-31T23%3A00%3A00.000Z&until=2026-11-03T23%3A00%3A00.000Z&limit=50&offset=0",
      )]: () => page([]),
    });
    renderApp(`${PAGE}?periode=perso&du=2026-11-01&au=2026-11-03`);

    expect(
      await within(await journal()).findByText(
        "Rien à afficher pour ces filtres. Essayez une autre période ou un autre type.",
      ),
    ).toBeInTheDocument();
    expect(within(await journal()).getByText("0 résultat")).toBeInTheDocument();
    expect(calls.at(-1)?.url).toContain("until=2026-11-03T23");
  });

  it("affiche l'erreur du serveur", async () => {
    setup({
      [historyUrl(`${LAST_7_DAYS}&limit=50&offset=0`)]: () => ({
        status: 500,
        body: { detail: "Base de données indisponible" },
      }),
    });
    renderApp(PAGE);

    expect(await within(await journal()).findByRole("alert")).toHaveTextContent(
      "Base de données indisponible",
    );
  });

  it("une session expirée renvoie vers la connexion", async () => {
    setup({
      [historyUrl(`${LAST_7_DAYS}&limit=50&offset=0`)]: () => ({
        status: 401,
        body: { detail: "Jeton expiré" },
      }),
    });
    renderApp(PAGE);

    expect(await screen.findByRole("heading", { name: "Connexion" })).toBeInTheDocument();
    expect(localStorage.getItem(TOKEN_KEY)).toBeNull();
  });

  it("le poulailler d'un autre compte n'est pas chargé", async () => {
    const calls = setup();
    renderApp("/poulaillers/coop_99/historique");

    expect(
      await screen.findByText("Le poulailler « coop_99 » n'est pas associé à votre compte."),
    ).toBeInTheDocument();
    expect(calls.some((call) => call.url.includes("coop_99"))).toBe(false);
  });

  it("le tableau de bord mène à l'historique, et l'historique au tableau de bord", async () => {
    setup({
      [`GET ${BASE}/status`]: () => ({ body: makeStatus() }),
      [`GET ${BASE}/events?limit=200`]: () => ({ body: [] }),
      [`GET ${BASE}/alerts?limit=50`]: () => ({ body: [] }),
    });
    renderApp("/");

    await userEvent.click(
      await screen.findByRole("link", { name: "Tout l'historique et les habitudes des poules →" }),
    );
    expect(await screen.findByRole("heading", { name: "Historique" })).toBeInTheDocument();

    await userEvent.click(screen.getByRole("link", { name: "← Tableau de bord" }));
    expect(await screen.findByRole("region", { name: "Poules" })).toBeInTheDocument();
  });
});
