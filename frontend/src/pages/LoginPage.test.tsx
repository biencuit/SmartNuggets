import { screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it } from "vitest";

import { TOKEN_KEY } from "../auth/context";
import { mockFetch, USER } from "../test/fetchMock";
import { renderApp } from "../test/renderApp";

describe("LoginPage", () => {
  it("connecte l'éleveur puis affiche ses poulaillers", async () => {
    mockFetch({
      "POST /api/v1/auth/login": () => ({ body: { access_token: "jeton", token_type: "bearer" } }),
      "GET /api/v1/auth/me": () => ({ body: USER }),
      "GET /api/v1/coops": () => ({ body: [{ id: "coop_01", name: "Chez Marc", total_hens: 10 }] }),
    });
    renderApp("/connexion");

    await userEvent.type(screen.getByLabelText("Adresse email"), "marc@example.com");
    await userEvent.type(screen.getByLabelText("Mot de passe"), "poulailler42");
    await userEvent.click(screen.getByRole("button", { name: "Se connecter" }));

    expect(await screen.findByText("Chez Marc")).toBeInTheDocument();
    expect(localStorage.getItem(TOKEN_KEY)).toBe("jeton");
  });

  it("affiche l'erreur renvoyée par l'API", async () => {
    mockFetch({
      "POST /api/v1/auth/login": () => ({
        status: 401,
        body: { detail: "Email ou mot de passe incorrect" },
      }),
    });
    renderApp("/connexion");

    await userEvent.type(screen.getByLabelText("Adresse email"), "marc@example.com");
    await userEvent.type(screen.getByLabelText("Mot de passe"), "mauvais");
    await userEvent.click(screen.getByRole("button", { name: "Se connecter" }));

    expect(await screen.findByRole("alert")).toHaveTextContent("Email ou mot de passe incorrect");
    expect(localStorage.getItem(TOKEN_KEY)).toBeNull();
  });

  it("renvoie vers la connexion si on n'est pas connecté", async () => {
    mockFetch({});
    renderApp("/");

    expect(await screen.findByRole("heading", { name: "Connexion" })).toBeInTheDocument();
  });

  it("oublie un jeton expiré", async () => {
    localStorage.setItem(TOKEN_KEY, "expire");
    mockFetch({ "GET /api/v1/auth/me": () => ({ status: 401, body: { detail: "expiré" } }) });
    renderApp("/");

    expect(await screen.findByRole("heading", { name: "Connexion" })).toBeInTheDocument();
    expect(localStorage.getItem(TOKEN_KEY)).toBeNull();
  });

  it("garde la session avec un jeton valide et permet de se déconnecter", async () => {
    localStorage.setItem(TOKEN_KEY, "valide");
    mockFetch({
      "GET /api/v1/auth/me": () => ({ body: USER }),
      "GET /api/v1/coops": () => ({ body: [] }),
    });
    renderApp("/");

    expect(await screen.findByText(/Aucun poulailler/)).toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", { name: "Déconnexion" }));
    expect(await screen.findByRole("heading", { name: "Connexion" })).toBeInTheDocument();
    expect(localStorage.getItem(TOKEN_KEY)).toBeNull();
  });
});
