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
