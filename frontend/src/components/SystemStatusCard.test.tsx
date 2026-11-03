import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { makeStatus } from "../test/statusFixture";
import { SystemStatusCard } from "./SystemStatusCard";

const NOW = new Date("2026-11-03T08:05:00Z");

describe("SystemStatusCard", () => {
  it("affiche un poulailler en bonne santé", () => {
    render(<SystemStatusCard status={makeStatus()} now={NOW} live />);

    expect(screen.getByText("Connecté")).toBeInTheDocument();
    expect(screen.getByText("87 %")).toBeInTheDocument();
    expect(screen.getByText("OK")).toBeInTheDocument();
    expect(screen.getByText("Dernière communication : il y a 5 min")).toBeInTheDocument();
    expect(screen.getByText("● en direct")).toBeInTheDocument();
    expect(screen.queryByRole("alert")).not.toBeInTheDocument();
  });

  it("prévient quand le poulailler ne répond plus", () => {
    render(<SystemStatusCard status={makeStatus({ online: false })} now={NOW} live={false} />);

    expect(screen.getByText("Hors ligne")).toBeInTheDocument();
    expect(screen.getByRole("alert")).toHaveTextContent(
      "Le poulailler ne répond plus (dernière communication : il y a 5 min)",
    );
    expect(screen.queryByText("● en direct")).not.toBeInTheDocument();
  });

  it("signale une batterie faible et une caméra en panne", () => {
    render(
      <SystemStatusCard status={makeStatus({ battery: 12, camera_ok: false })} now={NOW} live />,
    );

    expect(screen.getByText("12 %")).toBeInTheDocument();
    expect(screen.getByText("À recharger")).toBeInTheDocument();
    expect(screen.getByText("En panne")).toBeInTheDocument();
  });

  it("gère les valeurs encore inconnues", () => {
    render(
      <SystemStatusCard
        status={makeStatus({ battery: null, camera_ok: null, last_seen_at: null, online: false })}
        now={NOW}
        live={false}
      />,
    );

    expect(screen.getAllByText("Inconnue")).toHaveLength(2);
    expect(screen.getByText("Dernière communication : jamais")).toBeInTheDocument();
  });
});
