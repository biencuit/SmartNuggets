import { useState, type ReactNode } from "react";

import type { CoopEvent } from "../api/client";
import { availableDays, DAY_MS, dayKey, dayLabel, summarizeDay } from "./history";
import { EVENT_LABELS, formatTime, TRIGGER_LABELS } from "./labels";

const pct = (ms: number) => `${String((ms / DAY_MS) * 100)}%`;

function formatDuration(minutes: number): string {
  if (minutes < 60) return `${String(minutes)} min`;
  const rest = minutes % 60;
  return `${String(Math.floor(minutes / 60))} h ${rest ? String(rest).padStart(2, "0") : ""}`.trim();
}

function Stat({ label, children }: { label: string; children: ReactNode }) {
  return (
    <div>
      <dt className="text-stone-500">{label}</dt>
      <dd className="text-lg font-semibold text-stone-900 tabular-nums">{children}</dd>
    </div>
  );
}

/** Ouvertures et fermetures de la porte jour par jour, avec les passages des poules. */
export function DoorHistoryCard({ events, now }: { events: CoopEvent[]; now: Date }) {
  const days = availableDays(events, now);
  const [selected, setSelected] = useState(() => dayKey(now));
  const day = days.includes(selected) ? selected : (days[0] ?? dayKey(now));
  const summary = summarizeDay(events, day, now);

  return (
    <section
      aria-labelledby="historique-titre"
      className="flex min-w-0 flex-col gap-4 rounded-2xl bg-white p-5 shadow-sm ring-1 ring-stone-200"
    >
      <h2 id="historique-titre" className="text-lg font-semibold text-stone-900">
        Historique de la porte
      </h2>

      <div role="group" aria-label="Choisir un jour" className="flex gap-2 overflow-x-auto pb-1">
        {days.map((key) => (
          <button
            key={key}
            type="button"
            aria-pressed={key === day}
            onClick={() => {
              setSelected(key);
            }}
            className="shrink-0 rounded-full px-3 py-1 text-sm font-medium text-stone-700 ring-1 ring-stone-300 aria-pressed:bg-stone-800 aria-pressed:text-white aria-pressed:ring-stone-800"
          >
            {dayLabel(key, now)}
          </button>
        ))}
      </div>

      <div>
        <div
          role="img"
          aria-label={`Porte ouverte ${String(summary.openMinutes)} minutes ce jour-là`}
          className="relative h-10 overflow-hidden rounded-lg bg-stone-100 ring-1 ring-stone-200"
        >
          {summary.intervals.map((interval) => (
            <div
              key={interval.start}
              className="absolute inset-y-2 min-w-[3px] rounded-sm bg-amber-500"
              style={{ left: pct(interval.start), width: pct(interval.end - interval.start) }}
            />
          ))}
        </div>
        <div className="mt-1 flex justify-between text-xs text-stone-500 tabular-nums">
          <span>0 h</span>
          <span>6 h</span>
          <span>12 h</span>
          <span>18 h</span>
          <span>24 h</span>
        </div>
      </div>

      <dl className="grid grid-cols-2 gap-x-4 gap-y-3 text-sm sm:grid-cols-3">
        <Stat label="Ouvertures">
          {summary.openings}
          {summary.manualMoves > 0 && (
            <span className="ml-1 text-xs font-normal text-stone-500">
              dont {summary.manualMoves} à la main
            </span>
          )}
        </Stat>
        <Stat label="Première ouverture">
          {summary.firstOpening ? formatTime(summary.firstOpening) : "—"}
        </Stat>
        <Stat label="Dernière fermeture">
          {summary.lastClosing ? formatTime(summary.lastClosing) : "—"}
        </Stat>
        <Stat label="Temps ouvert">{formatDuration(summary.openMinutes)}</Stat>
        <Stat label="Sorties de poules">{summary.exits}</Stat>
        <Stat label="Entrées de poules">{summary.entries}</Stat>
      </dl>

      {summary.events.length === 0 ? (
        <p className="text-sm text-stone-500">Aucun mouvement enregistré ce jour-là.</p>
      ) : (
        <div className="max-h-80 overflow-auto rounded-lg ring-1 ring-stone-200">
          <table className="w-full text-left text-sm">
            <thead className="sticky top-0 bg-stone-50 text-xs tracking-wide text-stone-500 uppercase">
              <tr>
                <th className="px-3 py-2">Heure</th>
                <th className="px-3 py-2">Événement</th>
                <th className="px-3 py-2">Déclencheur</th>
                <th className="px-3 py-2">Poules dedans</th>
              </tr>
            </thead>
            <tbody>
              {[...summary.events].reverse().map((event) => (
                <tr key={event.id} className="border-t border-stone-100">
                  <td className="px-3 py-2 tabular-nums">{formatTime(event.occurred_at)}</td>
                  <td className="px-3 py-2">{EVENT_LABELS[event.event_type]}</td>
                  <td className="px-3 py-2 text-stone-600">
                    {event.trigger_source ? TRIGGER_LABELS[event.trigger_source] : "—"}
                  </td>
                  <td className="px-3 py-2 tabular-nums">{event.inside_count_after ?? "—"}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </section>
  );
}
