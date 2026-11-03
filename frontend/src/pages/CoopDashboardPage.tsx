import { useCallback, useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";

import { api, ApiError, type CoopAlert, type CoopEvent } from "../api/client";
import { useAuth } from "../auth/useAuth";
import { AppHeader } from "../components/AppHeader";
import { SystemStatusCard } from "../components/SystemStatusCard";
import { AlertsCard } from "../dashboard/AlertsCard";
import { DoorCard } from "../dashboard/DoorCard";
import { DoorHistoryCard } from "../dashboard/DoorHistoryCard";
import { HenCountCard } from "../dashboard/HenCountCard";
import { recentPredator } from "../dashboard/labels";
import { useCoopStatus } from "../status/useCoopStatus";
import { useNow } from "../status/useNow";

/** Ajoute un élément reçu en direct en tête de liste, sans doublon. */
function prepend<T extends { id: number }>(list: T[] | null, item: T): T[] | null {
  if (list === null) {
    return null;
  }
  return [item, ...list.filter((existing) => existing.id !== item.id)];
}

/** Tableau de bord d'un poulailler : porte, poules, historique et alertes (issue #26). */
export function CoopDashboardPage() {
  const { coopId = "" } = useParams();
  const { token, logout } = useAuth();
  const now = useNow();
  const [events, setEvents] = useState<CoopEvent[] | null>(null);
  const [alerts, setAlerts] = useState<CoopAlert[] | null>(null);
  const [loadError, setLoadError] = useState<string | null>(null);

  const { status, error, live } = useCoopStatus(coopId, token, {
    onEvent: (event) => {
      setEvents((list) => prepend(list, event));
    },
    onAlert: (alert) => {
      setAlerts((list) => prepend(list, alert));
    },
  });

  useEffect(() => {
    if (!token) {
      return;
    }
    const controller = new AbortController();
    void (async () => {
      try {
        const [loadedEvents, loadedAlerts] = await Promise.all([
          api.listEvents(token, coopId),
          api.listAlerts(token, coopId),
        ]);
        if (!controller.signal.aborted) {
          // Le flux a pu ajouter des éléments pendant le chargement : on les garde devant.
          setEvents((live) => mergeById(live, loadedEvents));
          setAlerts((live) => mergeById(live, loadedAlerts));
        }
      } catch (err) {
        if (controller.signal.aborted) {
          return;
        }
        if (err instanceof ApiError && err.status === 401) {
          logout();
        } else {
          setLoadError(err instanceof Error ? err.message : "Erreur inconnue");
        }
      }
    })();
    return () => {
      controller.abort();
    };
  }, [coopId, token, logout]);

  const sendCommand = useCallback(
    async (action: "OPEN" | "CLOSE" | "CALIBRATE", insideCount?: number) => {
      if (!token) return;
      await api.sendCommand(token, coopId, action, insideCount);
    },
    [token, coopId],
  );

  const acknowledge = useCallback(
    async (alertId: number) => {
      if (!token) return;
      const updated = await api.acknowledgeAlert(token, coopId, alertId);
      setAlerts(
        (list) => list?.map((alert) => (alert.id === updated.id ? updated : alert)) ?? null,
      );
    },
    [token, coopId],
  );

  const notFound = error !== null && !status;

  return (
    <div className="min-h-screen bg-stone-100">
      <AppHeader />
      <main className="mx-auto flex max-w-5xl flex-col gap-4 p-4">
        <div className="flex flex-wrap items-end justify-between gap-2">
          <div>
            <Link to="/" className="text-sm text-amber-800 underline underline-offset-2">
              ← Mes poulaillers
            </Link>
            <h1 className="mt-1 text-2xl font-semibold text-stone-900">
              {status?.name ?? "Poulailler"}
            </h1>
          </div>
        </div>

        {notFound && <p className="text-red-700">{error}</p>}
        {!status && !notFound && <p className="text-stone-500">Chargement du poulailler…</p>}

        {status && (
          <>
            <div className="grid grid-cols-[minmax(0,1fr)] gap-4 md:grid-cols-[repeat(2,minmax(0,1fr))]">
              <DoorCard
                status={status}
                predator={recentPredator(alerts ?? [], now)}
                onCommand={(action) => sendCommand(action)}
              />
              <HenCountCard
                status={status}
                onCalibrate={(count) => sendCommand("CALIBRATE", count)}
              />
            </div>
            <SystemStatusCard status={status} now={now} live={live} />
          </>
        )}

        {loadError && <p className="text-red-700">{loadError}</p>}
        {status && (
          <div className="grid grid-cols-[minmax(0,1fr)] items-start gap-4 lg:grid-cols-[minmax(0,3fr)_minmax(0,2fr)]">
            {events ? (
              <DoorHistoryCard events={events} now={now} />
            ) : (
              !loadError && <p className="text-stone-500">Chargement de l'historique…</p>
            )}
            {alerts && token && (
              <AlertsCard
                alerts={alerts}
                imageUrl={(alertId) => api.alertImageUrl(token, coopId, alertId)}
                onAcknowledge={acknowledge}
              />
            )}
          </div>
        )}
      </main>
    </div>
  );
}

function mergeById<T extends { id: number }>(live: T[] | null, loaded: T[]): T[] {
  const fresh = (live ?? []).filter((item) => !loaded.some((other) => other.id === item.id));
  return [...fresh, ...loaded];
}
