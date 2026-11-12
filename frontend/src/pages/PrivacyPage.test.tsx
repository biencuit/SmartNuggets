import { screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it } from "vitest";

import { mockFetch } from "../test/fetchMock";
import { renderApp } from "../test/renderApp";

describe("PrivacyPage", () => {
  it("s'ouvre sans compte depuis la page de connexion", async () => {
    mockFetch({});
    renderApp("/connexion");

    await userEvent.click(screen.getByRole("link", { name: "Vie privée et données personnelles" }));

    expect(
      screen.getByRole("heading", { name: "Vie privée et données personnelles" }),
    ).toBeInTheDocument();
    expect(screen.getByText(/datacenter de Singapour/)).toBeInTheDocument();
    expect(screen.getByText("Photos des alertes : 30 jours.")).toBeInTheDocument();
    expect(
      screen.getByText("Passages, mouvements de porte et alertes : 1 an."),
    ).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Mon compte" })).toHaveAttribute("href", "/compte");
  });

  it("est annoncée à l'inscription", () => {
    mockFetch({});
    renderApp("/inscription");

    expect(
      screen.getByRole("link", { name: "ce que nous gardons et combien de temps" }),
    ).toHaveAttribute("href", "/vie-privee");
  });
});
