import { screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";

import { TOKEN_KEY } from "../auth/context";
import { mockFetch, USER } from "../test/fetchMock";
import { renderApp } from "../test/renderApp";

const EXPORT = { exported_at: "2026-11-12T15:00:00Z", account: USER, coops: [] };
const DEFAULT_NOTIFICATION_PREFS = {
  push_enabled: false,
  telegram_chat_id: null,
  notify_critical_only: false,
};

function setup(deleteResponse: { status: number; body?: unknown } = { status: 204 }) {
  localStorage.setItem(TOKEN_KEY, "jeton");
  return mockFetch({
    "GET /api/v1/auth/me": () => ({ body: USER }),
    "GET /api/v1/coops": () => ({ body: [] }),
    "GET /api/v1/auth/me/export": () => ({ body: EXPORT }),
    "GET /api/v1/auth/me/notifications": () => ({ body: DEFAULT_NOTIFICATION_PREFS }),
    "PATCH /api/v1/auth/me/notifications": (call) => ({ body: JSON.parse(call.body ?? "{}") }),
    "DELETE /api/v1/auth/me": () => deleteResponse,
  });
}

describe("ProfilePage", () => {
  afterEach(() => {
    vi.restoreAllMocks();
  });

  it("s'ouvre depuis le bandeau et fait télécharger mes données", async () => {
    const calls = setup();
    const blobs: Blob[] = [];
    const names: string[] = [];
    URL.createObjectURL = vi.fn((blob: Blob) => {
      blobs.push(blob);
      return "blob:mes-donnees";
    });
    URL.revokeObjectURL = vi.fn();
    vi.spyOn(HTMLAnchorElement.prototype, "click").mockImplementation(function (
      this: HTMLAnchorElement,
    ) {
      names.push(this.download);
    });
    renderApp("/");

    await userEvent.click(await screen.findByRole("link", { name: "Mon compte" }));
    expect(await screen.findByRole("heading", { name: "Mon compte" })).toBeInTheDocument();
    expect(screen.getByText(/3 novembre 2026/)).toBeInTheDocument();

    await userEvent.click(screen.getByRole("button", { name: "Télécharger mes données" }));

    const exportCall = calls.find((call) => call.url === "/api/v1/auth/me/export");
    expect(exportCall?.headers.Authorization).toBe("Bearer jeton");
    expect(names).toEqual(["smartnuggets-mes-donnees.json"]);
    const blob = blobs.at(0);
    expect(blob).toBeDefined();
    expect(JSON.parse((await blob?.text()) ?? "null")).toEqual(EXPORT);
  });

  it("supprime le compte après confirmation, puis revient à la connexion", async () => {
    const calls = setup();
    renderApp("/compte");

    const button = await screen.findByRole("button", { name: "Supprimer mon compte" });
    await userEvent.type(screen.getByLabelText("Mot de passe"), "poulailler42");
    expect(button).toBeDisabled(); // tant que la case n'est pas cochée
    await userEvent.click(screen.getByRole("checkbox", { name: /comprends/ }));
    await userEvent.click(button);

    expect(
      await screen.findByText("Votre compte et toutes ses données ont été supprimés."),
    ).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "Connexion" })).toBeInTheDocument();
    const deleteCall = calls.find((call) => call.method === "DELETE");
    expect(deleteCall?.url).toBe("/api/v1/auth/me");
    expect(JSON.parse(deleteCall?.body ?? "{}")).toEqual({ password: "poulailler42" });
    expect(localStorage.getItem(TOKEN_KEY)).toBeNull();
  });

  it("active les notifications Telegram et enregistre l'identifiant de chat", async () => {
    const calls = setup();
    renderApp("/compte");

    await userEvent.click(await screen.findByRole("checkbox", { name: /notifications Telegram/ }));
    await userEvent.type(screen.getByLabelText("Identifiant de chat Telegram"), "123456789");
    await userEvent.click(screen.getByRole("button", { name: "Enregistrer" }));

    expect(await screen.findByText("Préférences enregistrées.")).toBeInTheDocument();
    const patchCall = calls.find((call) => call.method === "PATCH");
    expect(patchCall?.url).toBe("/api/v1/auth/me/notifications");
    expect(JSON.parse(patchCall?.body ?? "{}")).toEqual({
      push_enabled: true,
      telegram_chat_id: "123456789",
      notify_critical_only: false,
    });
  });

  it("garde le compte si le mot de passe est faux", async () => {
    setup({ status: 401, body: { detail: "Mot de passe incorrect" } });
    renderApp("/compte");

    await userEvent.type(await screen.findByLabelText("Mot de passe"), "pas-le-bon");
    await userEvent.click(screen.getByRole("checkbox", { name: /comprends/ }));
    await userEvent.click(screen.getByRole("button", { name: "Supprimer mon compte" }));

    expect(await screen.findByRole("alert")).toHaveTextContent("Mot de passe incorrect");
    expect(screen.getByRole("heading", { name: "Mon compte" })).toBeInTheDocument();
    expect(localStorage.getItem(TOKEN_KEY)).toBe("jeton");
  });
});
