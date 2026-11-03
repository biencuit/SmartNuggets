import { useState } from "react";

import type { CoopAlert } from "../api/client";
import { ALERT_ADVICE, ALERT_TITLES, formatDateTime } from "./labels";

type Filter = "unread" | "all";

const SEVERITY = {
  CRITICAL: { label: "Critique", stripe: "border-l-red-600", text: "text-red-700" },
  WARNING: { label: "Attention", stripe: "border-l-amber-500", text: "text-amber-800" },
} as const;

export function AlertsCard({
  alerts,
  imageUrl,
  onAcknowledge,
}: {
  alerts: CoopAlert[];
  imageUrl: (alertId: number) => string;
  onAcknowledge: (alertId: number) => Promise<void>;
}) {
  const [filter, setFilter] = useState<Filter>("unread");
  const [error, setError] = useState<string | null>(null);
  const [openImage, setOpenImage] = useState<number | null>(null);

  const unread = alerts.filter((alert) => !alert.acknowledged).length;
  const shown = filter === "unread" ? alerts.filter((alert) => !alert.acknowledged) : alerts;

  async function acknowledge(alertId: number) {
    setError(null);
    try {
      await onAcknowledge(alertId);
    } catch (err) {
      setError(err instanceof Error ? err.message : "L'alerte n'a pas pu être marquée comme lue.");
    }
  }

  return (
    <section
      aria-labelledby="alertes-titre"
      className="flex flex-col gap-4 rounded-2xl bg-white p-5 shadow-sm ring-1 ring-stone-200"
    >
      <div className="flex flex-wrap items-center justify-between gap-3">
        <h2 id="alertes-titre" className="text-lg font-semibold text-stone-900">
          Alertes
          {unread > 0 && (
            <span className="ml-2 rounded-full bg-red-600 px-2 py-0.5 text-xs font-bold text-white">
              {unread}
            </span>
          )}
        </h2>
        <div
          role="group"
          aria-label="Filtrer les alertes"
          className="flex rounded-lg ring-1 ring-stone-300"
        >
          {(
            [
              ["unread", "Non lues"],
              ["all", "Toutes"],
            ] as const
          ).map(([value, label]) => (
            <button
              key={value}
              type="button"
              aria-pressed={filter === value}
              onClick={() => {
                setFilter(value);
              }}
              className="px-3 py-1.5 text-sm font-medium text-stone-700 first:rounded-l-lg last:rounded-r-lg aria-pressed:bg-amber-100 aria-pressed:text-amber-900"
            >
              {label}
            </button>
          ))}
        </div>
      </div>

      {error && (
        <p role="alert" className="text-sm text-red-700">
          {error}
        </p>
      )}

      {shown.length === 0 ? (
        <p className="text-sm text-stone-500">
          {filter === "unread" ? "Aucune alerte à traiter." : "Aucune alerte pour l'instant."}
        </p>
      ) : (
        <ul className="flex max-h-[28rem] flex-col gap-2 overflow-y-auto">
          {shown.map((alert) => {
            const severity = SEVERITY[alert.severity];
            return (
              <li
                key={alert.id}
                className={`rounded-lg border border-l-4 border-stone-200 p-3 ${severity.stripe} ${
                  alert.acknowledged ? "opacity-60" : ""
                }`}
              >
                <div className="flex flex-wrap items-start justify-between gap-2">
                  <div className="min-w-0">
                    <p className="font-semibold text-stone-900">{ALERT_TITLES[alert.alert_type]}</p>
                    <p className="text-xs text-stone-500">
                      <span className={`font-semibold uppercase ${severity.text}`}>
                        {severity.label}
                      </span>{" "}
                      · {formatDateTime(alert.created_at)}
                      {alert.ai_confidence !== null &&
                        ` · confiance ${String(Math.round(alert.ai_confidence * 100))} %`}
                    </p>
                  </div>
                  {alert.acknowledged ? (
                    <span className="text-xs text-stone-500">Lue</span>
                  ) : (
                    <button
                      type="button"
                      onClick={() => void acknowledge(alert.id)}
                      className="rounded-lg px-3 py-1 text-sm font-medium text-stone-800 ring-1 ring-stone-300 hover:bg-stone-50"
                    >
                      Marquer comme lue
                    </button>
                  )}
                </div>
                <p className="mt-1 text-sm text-stone-600">{ALERT_ADVICE[alert.alert_type]}</p>
                {alert.image_url && (
                  <div className="mt-2">
                    <button
                      type="button"
                      onClick={() => {
                        setOpenImage(openImage === alert.id ? null : alert.id);
                      }}
                      className="text-sm font-medium text-amber-800 underline underline-offset-2"
                    >
                      {openImage === alert.id ? "Masquer la photo" : "Voir la photo"}
                    </button>
                    {openImage === alert.id && (
                      <img
                        src={imageUrl(alert.id)}
                        alt={`Photo prise lors de l'alerte « ${ALERT_TITLES[alert.alert_type]} »`}
                        className="mt-2 max-h-64 rounded-lg object-contain"
                      />
                    )}
                  </div>
                )}
              </li>
            );
          })}
        </ul>
      )}
    </section>
  );
}
