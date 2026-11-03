import { screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it } from "vitest";

import { mockFetch, USER } from "../test/fetchMock";
import { renderApp } from "../test/renderApp";
import { validateRegistration } from "../auth/validation";

async function fillForm(email: string, password: string, confirmation: string) {
  await userEvent.type(screen.getByLabelText("Adresse email"), email);
  await userEvent.type(screen.getByLabelText(/^Mot de passe/), password);
  await userEvent.type(screen.getByLabelText("Confirmer le mot de passe"), confirmation);
  await userEvent.click(screen.getByRole("button", { name: "Créer mon compte" }));
}

describe("validateRegistration", () => {
  it("vérifie la longueur et la confirmation", () => {
    expect(validateRegistration("court", "court")).toMatch(/au moins 8/);
    expect(validateRegistration("poulailler42", "poulailler43")).toMatch(/ne correspondent pas/);
    expect(validateRegistration("poulailler42", "poulailler42")).toBeNull();
  });
});

describe("RegisterPage", () => {
  it("refuse deux mots de passe différents sans appeler l'API", async () => {
    const calls = mockFetch({});
    renderApp("/inscription");

    await fillForm("marc@example.com", "poulailler42", "poulailler43");

    expect(screen.getByRole("alert")).toHaveTextContent("ne correspondent pas");
    expect(calls).toHaveLength(0);
  });

  it("crée le compte puis connecte directement l'éleveur", async () => {
    const calls = mockFetch({
      "POST /api/v1/auth/register": () => ({ status: 201, body: USER }),
      "POST /api/v1/auth/login": () => ({ body: { access_token: "jeton", token_type: "bearer" } }),
      "GET /api/v1/auth/me": () => ({ body: USER }),
      "GET /api/v1/coops": () => ({ body: [] }),
    });
    renderApp("/inscription");

    await fillForm("marc@example.com", "poulailler42", "poulailler42");

    expect(await screen.findByRole("heading", { name: "Mes poulaillers" })).toBeInTheDocument();
    expect(calls[0]?.body).toBe(
      JSON.stringify({ email: "marc@example.com", password: "poulailler42" }),
    );
  });

  it("affiche l'erreur si l'email est déjà utilisé", async () => {
    mockFetch({
      "POST /api/v1/auth/register": () => ({
        status: 409,
        body: { detail: "Un compte existe déjà avec cette adresse email" },
      }),
    });
    renderApp("/inscription");

    await fillForm("marc@example.com", "poulailler42", "poulailler42");

    expect(await screen.findByRole("alert")).toHaveTextContent("Un compte existe déjà");
  });
});
