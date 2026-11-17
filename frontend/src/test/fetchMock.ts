import { vi } from "vitest";

export interface Call {
  url: string;
  method: string;
  headers: Record<string, string>;
  body: string | null;
}

type Handler = (call: Call) => { status?: number; body?: unknown };

/** Remplace fetch : chaque route "METHODE /chemin" renvoie la réponse décrite. */
export function mockFetch(routes: Record<string, Handler>) {
  const calls: Call[] = [];
  const fetchMock = vi.fn((input: string, init?: RequestInit) => {
    const headers = (init?.headers ?? {}) as Record<string, string>;
    const body = init?.body;
    const call: Call = {
      url: input,
      method: init?.method ?? "GET",
      headers,
      body: body === undefined || body === null ? null : String(body as string | URLSearchParams),
    };
    calls.push(call);
    const handler = routes[`${call.method} ${input}`];
    if (!handler) {
      return Promise.resolve(
        new Response(JSON.stringify({ detail: "Not Found" }), { status: 404 }),
      );
    }
    const { status = 200, body: responseBody } = handler(call);
    return Promise.resolve(
      new Response(responseBody === undefined ? null : JSON.stringify(responseBody), { status }),
    );
  });
  vi.stubGlobal("fetch", fetchMock);
  return calls;
}

export const USER = { id: "u1", email: "marc@example.com", created_at: "2026-11-03T08:00:00Z" };
