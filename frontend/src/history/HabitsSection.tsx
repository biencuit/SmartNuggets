import { useEffect, useState } from "react";

import { api, ApiError, type Habits } from "../api/client";
import { useAuth } from "../auth/useAuth";
import { dayLabel } from "../dashboard/history";
import { browserTimeZone, clock, plural } from "./format";
import { HourChart } from "./HourChart";

const PERIOD_DAYS = [7, 30] as const;
type PeriodDays = (typeof PERIOD_DAYS)[number];

/** Réponse (ou erreur) liée à la période demandée : une réponse d'avant ne s'affiche pas. */
type Loaded = { days: PeriodDays; habits: Habits } | { days: PeriodDays; error: string };

function Tile({ label, value, hint }: { label: string; value: string; hint?: string }) {
  return (
    <div className="rounded-xl bg-stone-50 p-3 ring-1 ring-stone-200">
      <dt className="text-sm text-stone-600">{label}</dt>
      <dd className="mt-1 text-2xl font-semibold text-stone-900">{value}</dd>
      {hint && <dd className="text-xs text-stone-500">{hint}</dd>}
    </div>
  );
}

/**
 * Habitudes des poules (#27) : heures moyennes de première sortie et de dernier retour,
 * passages par heure et détail jour par jour, sur 7 ou 30 jours.
 */
export function HabitsSection({ coopId }: { coopId: string }) {
  const { token, logout } = useAuth();
  const [days, setDays] = useState<PeriodDays>(7);
  const [loaded, setLoaded] = useState<Loaded | null>(null);

  useEffect(() => {
    if (!token) {
      return;
    }
    const controller = new AbortController();
    void (async () => {
      try {
        const habits = await api.getHabits(token, coopId, days, browserTimeZone());
        if (!controller.signal.aborted) setLoaded({ days, habits });
      } catch (err) {
        if (controller.signal.aborted) return;
        if (err instanceof ApiError && err.status === 401) {
          logout();
        } else {
          setLoaded({ days, error: err instanceof Error ? err.message : "Erreur inconnue" });
        }
      }
    })();
    return () => {
      controller.abort();
    };
  }, [token, coopId, days, logout]);

  const current = loaded?.days === days ? loaded : null;
  const habits = current && "habits" in current ? current.habits : null;
  const error = current && "error" in current ? current.error : null;
  const now = new Date();

  return (
    <section
      aria-labelledby="habitudes-titre"
      className="flex flex-col gap-4 rounded-2xl bg-white p-5 shadow-sm ring-1 ring-stone-200"
    >
      <div className="flex flex-wrap items-center justify-between gap-3">
        <h2 id="habitudes-titre" className="text-lg font-semibold text-stone-900">
          Habitudes des poules
        </h2>
        <div
          role="group"
          aria-label="Période des habitudes"
          className="flex rounded-lg ring-1 ring-stone-300"
        >
          {PERIOD_DAYS.map((value) => (
            <button
              key={value}
              type="button"
              aria-pressed={days === value}
              onClick={() => {
                setDays(value);
              }}
              className="px-3 py-1.5 text-sm font-medium text-stone-700 first:rounded-l-lg last:rounded-r-lg aria-pressed:bg-amber-100 aria-pressed:text-amber-900"
            >
              {value} jours
            </button>
          ))}
        </div>
      </div>

      {error && (
        <p role="alert" className="text-sm text-red-700">
          {error}
        </p>
      )}
      {!habits && !error && <p className="text-sm text-stone-500">Calcul des habitudes…</p>}

      {habits && habits.active_days === 0 && (
        <p className="text-sm text-stone-600">
          Aucun passage de poule sur les {days} derniers jours.
        </p>
      )}

      {habits && habits.active_days > 0 && (
        <>
          <dl className="grid grid-cols-[minmax(0,1fr)] gap-3 sm:grid-cols-[repeat(3,minmax(0,1fr))]">
            <Tile
              label="Première sortie (moyenne)"
              value={clock(habits.average_first_exit)}
              hint="le matin, porte ouverte"
            />
            <Tile
              label="Dernier retour (moyenne)"
              value={clock(habits.average_last_entry)}
              hint="avant la fermeture du soir"
            />
            <Tile
              label="Sorties par jour"
              value={habits.exits_per_day.toLocaleString("fr-BE", { maximumFractionDigits: 1 })}
              hint={`sur ${plural(habits.active_days, "jour", "jours")} avec des passages`}
            />
          </dl>

          <HourChart hours={habits.hours} />

          <div className="max-h-80 overflow-auto">
            <table className="w-full min-w-[30rem] text-left text-sm tabular-nums">
              <caption className="pb-2 text-left text-sm font-medium text-stone-800">
                Jour par jour
              </caption>
              <thead>
                <tr className="text-stone-500">
                  <th scope="col" className="py-1.5 pr-3 font-medium whitespace-nowrap">
                    Jour
                  </th>
                  <th scope="col" className="py-1.5 pr-3 font-medium whitespace-nowrap">
                    Sorties
                  </th>
                  <th scope="col" className="py-1.5 pr-3 font-medium whitespace-nowrap">
                    Entrées
                  </th>
                  <th scope="col" className="py-1.5 pr-3 font-medium whitespace-nowrap">
                    1<sup>re</sup> sortie
                  </th>
                  <th scope="col" className="py-1.5 pr-3 font-medium whitespace-nowrap">
                    Dernier retour
                  </th>
                </tr>
              </thead>
              <tbody>
                {[...habits.days].reverse().map((day) => (
                  <tr key={day.day} className="border-t border-stone-100 text-stone-800">
                    <th scope="row" className="py-1.5 pr-3 font-normal whitespace-nowrap">
                      {dayLabel(day.day, now)}
                    </th>
                    <td className="py-1.5 pr-3">{day.exits}</td>
                    <td className="py-1.5 pr-3">{day.entries}</td>
                    <td className="py-1.5 pr-3">{clock(day.first_exit)}</td>
                    <td className="py-1.5 pr-3">{clock(day.last_entry)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </>
      )}
    </section>
  );
}
