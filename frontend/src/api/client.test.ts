import { describe, expect, it, vi } from "vitest";

import { mockFetch } from "../test/fetchMock";
import { api, ApiError, apiFetch } from "./client";

describe("apiFetch", () => {
  it("envoie le jeton dans l'en-tête Authorization", async () => {
    const calls = mockFetch({ "GET /api/v1/coops": () => ({ body: [] }) });

    await api.listCoops("abc");

    expect(calls[0]?.headers.Authorization).toBe("Bearer abc");
  });

  it("envoie la connexion en formulaire OAuth2", async () => {
    const calls = mockFetch({
      "POST /api/v1/auth/login": () => ({ body: { access_token: "t", token_type: "bearer" } }),
    });

    const token = await api.login("marc@example.com", "secret");

    expect(token.access_token).toBe("t");
    expect(calls[0]?.body).toBe("username=marc%40example.com&password=secret");
  });

  it("transforme le détail d'erreur de l'API en message", async () => {
    mockFetch({
      "POST /api/v1/auth/login": () => ({ status: 401, body: { detail: "Email inconnu" } }),
    });

    await expect(api.login("x@y.z", "pw")).rejects.toEqual(new ApiError(401, "Email inconnu"));
  });

  it("donne un message lisible pour une erreur de validation ou serveur", async () => {
    mockFetch({
      "POST /api/v1/auth/register": () => ({ status: 422, body: { detail: [{ msg: "bad" }] } }),
      "GET /api/v1/auth/me": () => ({ status: 502 }),
    });

    await expect(api.register("x", "y")).rejects.toThrow(/vérifiez le formulaire/);
    await expect(api.me("t")).rejects.toThrow(/serveur rencontre un problème/);
  });

  it("signale un serveur injoignable", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(() => Promise.reject(new TypeError("Failed to fetch"))),
    );

    await expect(apiFetch("/health")).rejects.toMatchObject({ status: 0 });
  });
});

describe("historique et habitudes (#27)", () => {
  it("répète la catégorie et encode les dates de la période", async () => {
    const url =
      "/api/v1/coops/coop_01/history?category=entries&category=alerts" +
      "&since=2026-11-08T23%3A00%3A00.000Z&until=2026-11-09T23%3A00%3A00.000Z&limit=50&offset=100";
    const calls = mockFetch({ [`GET ${url}`]: () => ({ body: { total: 0, items: [] } }) });

    const page = await api.listHistory("abc", "coop_01", {
      categories: ["entries", "alerts"],
      since: "2026-11-08T23:00:00.000Z",
      until: "2026-11-09T23:00:00.000Z",
      limit: 50,
      offset: 100,
    });

    expect(page).toEqual({ total: 0, items: [] });
    expect(calls[0]?.headers.Authorization).toBe("Bearer abc");
  });

  it("sans filtre ni période, n'envoie que la pagination", async () => {
    const calls = mockFetch({
      "GET /api/v1/coops/coop_01/history?limit=50&offset=0": () => ({
        body: { total: 0, items: [] },
      }),
    });

    await api.listHistory("abc", "coop_01", {
      categories: [],
      since: null,
      until: null,
      limit: 50,
      offset: 0,
    });

    expect(calls).toHaveLength(1);
  });

  it("envoie le nombre de jours et le fuseau des habitudes", async () => {
    const calls = mockFetch({
      "GET /api/v1/coops/coop_01/habits?days=30&tz=America%2FNew_York": () => ({ body: {} }),
    });

    await api.getHabits("abc", "coop_01", 30, "America/New_York");

    expect(calls[0]?.url).toBe("/api/v1/coops/coop_01/habits?days=30&tz=America%2FNew_York");
  });
});
