import { useCallback, useEffect, useState } from "react";

import { api, ApiError, type CoopAlert, type CoopEvent } from "../api/client";
import { useAuth } from "../auth/useAuth";
import { SystemStatusCard } from "../components/SystemStatusCard";
import { useCoopStatus } from "../status/useCoopStatus";
import { useNow } from "../status/useNow";
import { AlertsCard } from "./AlertsCard";
import { DoorCard } from "./DoorCard";
import { DoorHistoryCard } from "./DoorHistoryCard";
import { HenCountCard } from "./HenCountCard";
import { EVENT_LABELS, formatDateTime, recentPredator, TRIGGER_LABELS } from "./labels";

/** Ajoute un élément reçu en direct en tête de liste, sans doublon. */
function prepend<T extends { id: number }>(list: T[] | null, item: T): T[] | null {
  if (list === null) {
    return null;
  }
  return [item, ...list.filter((existing) => existing.id !== item.id)];
}

/** Le plus récent par date (un événement mis en file pendant une coupure arrive en retard). */
function latest(events: CoopEvent[]): CoopEvent | undefined {
  return events.reduce<CoopEvent | undefined>(
    (best, event) =>
      best === undefined || Date.parse(event.occurred_at) > Date.parse(best.occurred_at)
        ? event
        : best,
    undefined,
  );
}

function describeEvent(event: CoopEvent): string {
  const source = event.trigger_source ? ` (${TRIGGER_LABELS[event.trigger_source]})` : "";
  return `${EVENT_LABELS[event.event_type]}, le ${formatDateTime(event.occurred_at)}${source}`;
}

/**
 * Tableau de bord d'un poulailler (issue #26) : porte, poules, état du système, dernier
 * événement, historique et alertes, tenus à jour par le flux temps réel.
 */
export function CoopDashboard({ coopId, name }: { coopId: string; name: string }) {
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

  // L'état n'a pas pu être chargé : une seule erreur, l'historique et les alertes échouent pareil.
  const failed = error !== null && !status;
  const lastEvent = events ? latest(events) : undefined;

  return (
    <div className="flex flex-col gap-4">
      <div>
        <h1 className="text-2xl font-semibold text-stone-900">{status?.name ?? name}</h1>
        {status && events && (
          <p className="mt-1 text-sm text-stone-600">
            <span className="font-medium text-stone-800">Dernier événement :</span>{" "}
            {lastEvent ? describeEvent(lastEvent) : "aucun pour l'instant."}
          </p>
        )}
      </div>

      {failed && <p className="text-red-700">{error}</p>}
      {!status && !failed && <p className="text-stone-500">Chargement du poulailler…</p>}

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

      {loadError && !failed && <p className="text-red-700">{loadError}</p>}
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
    </div>
  );
}

function mergeById<T extends { id: number }>(live: T[] | null, loaded: T[]): T[] {
  const fresh = (live ?? []).filter((item) => !loaded.some((other) => other.id === item.id));
  return [...fresh, ...loaded];
}
