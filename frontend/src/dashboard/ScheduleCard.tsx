import { useEffect, useState } from "react";

import { api, ApiError, type DaySchedule } from "../api/client";
import { useAuth } from "../auth/useAuth";

const LOCK_MAX_S = 3600;

const WEEKDAY_LABELS = ["Lundi", "Mardi", "Mercredi", "Jeudi", "Vendredi", "Samedi", "Dimanche"];

/** "HH:MM:SS" (API) <-> "HH:MM" (<input type="time">). */
function toInput(time: string): string {
  return time.slice(0, 5);
}

function toApi(time: string): string {
  return `${time}:00`;
}

function sameDays(a: DaySchedule[], b: DaySchedule[]): boolean {
  return a.every((day) => {
    const other = b.find((candidate) => candidate.weekday === day.weekday);
    if (!other) {
      return false;
    }
    return other.open_from === day.open_from && other.close_at === day.close_at;
  });
}

/**
 * Planning hebdomadaire de la porte (#70) : un horaire d'ouverture et de fermeture par jour,
 * transmis au Raspberry Pi dès l'enregistrement (message MQTT retenu, reçu même hors ligne).
 */
export function ScheduleCard({ coopId }: { coopId: string }) {
  const { token, logout } = useAuth();
  const [saved, setSaved] = useState<DaySchedule[] | null>(null);
  const [days, setDays] = useState<DaySchedule[] | null>(null);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);
  const [saveError, setSaveError] = useState<string | null>(null);
  const [savedNotice, setSavedNotice] = useState(false);
  // Verrouillage après un prédateur, en secondes (texte du champ, vérifié à l'enregistrement).
  const [savedLock, setSavedLock] = useState<number | null>(null);
  const [lock, setLock] = useState("");

  useEffect(() => {
    if (!token) {
      return;
    }
    const controller = new AbortController();
    void (async () => {
      try {
        const schedule = await api.getSchedule(token, coopId);
        if (controller.signal.aborted) {
          return;
        }
        setSaved(schedule.days);
        setDays(schedule.days);
        setSavedLock(schedule.predator_lock_s);
        setLock(String(schedule.predator_lock_s));
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
  }, [token, coopId, logout]);

  function change(weekday: number, field: "open_from" | "close_at", value: string) {
    setDays(
      (current) =>
        current?.map((day) =>
          day.weekday === weekday ? { ...day, [field]: toApi(value) } : day,
        ) ?? null,
    );
  }

  const lockSeconds = /^\d+$/.test(lock.trim()) ? Number(lock.trim()) : NaN;
  const lockValid = Number.isInteger(lockSeconds) && lockSeconds >= 0 && lockSeconds <= LOCK_MAX_S;

  async function save() {
    if (!token || !days) {
      return;
    }
    if (!lockValid) {
      setSaveError(
        `Le verrouillage doit être un nombre de secondes entre 0 et ${String(LOCK_MAX_S)}.`,
      );
      return;
    }
    setSaveError(null);
    setSavedNotice(false);
    setSaving(true);
    try {
      const updated = await api.updateSchedule(token, coopId, days, lockSeconds);
      setSaved(updated.days);
      setDays(updated.days);
      setSavedLock(updated.predator_lock_s);
      setLock(String(updated.predator_lock_s));
      setSavedNotice(true);
    } catch (err) {
      if (err instanceof ApiError && err.status === 401) {
        logout();
        return;
      }
      setSaveError(err instanceof Error ? err.message : "L'enregistrement a échoué.");
    } finally {
      setSaving(false);
    }
  }

  const dirty =
    (days && saved ? !sameDays(days, saved) : false) ||
    (savedLock !== null && lock.trim() !== String(savedLock));

  return (
    <section
      aria-labelledby="planning-titre"
      className="flex flex-col gap-3 rounded-2xl bg-white p-5 shadow-sm ring-1 ring-stone-200"
    >
      <h2 id="planning-titre" className="text-lg font-semibold text-stone-900">
        Planning de la porte
      </h2>
      <p className="text-sm text-stone-600">
        Horaires d'ouverture et de fermeture pour chaque jour de la semaine.
      </p>

      {loadError && <p className="text-sm text-red-700">{loadError}</p>}

      {days && (
        <div className="flex flex-col gap-2">
          {days.map((day) => (
            <div key={day.weekday} className="flex items-center gap-3">
              <span className="w-24 shrink-0 text-sm font-medium text-stone-700">
                {WEEKDAY_LABELS[day.weekday]}
              </span>
              <label className="flex items-center gap-1 text-sm text-stone-600">
                de
                <input
                  type="time"
                  value={toInput(day.open_from)}
                  onChange={(event) => {
                    change(day.weekday, "open_from", event.target.value);
                  }}
                  className="rounded-lg border border-stone-300 px-2 py-1 text-stone-900 focus:border-amber-600 focus:ring-2 focus:ring-amber-200 focus:outline-none"
                />
              </label>
              <label className="flex items-center gap-1 text-sm text-stone-600">
                à
                <input
                  type="time"
                  value={toInput(day.close_at)}
                  onChange={(event) => {
                    change(day.weekday, "close_at", event.target.value);
                  }}
                  className="rounded-lg border border-stone-300 px-2 py-1 text-stone-900 focus:border-amber-600 focus:ring-2 focus:ring-amber-200 focus:outline-none"
                />
              </label>
            </div>
          ))}
        </div>
      )}

      {days && (
        <label className="flex flex-wrap items-center gap-2 text-sm text-stone-700">
          Verrouillage après un prédateur
          <input
            type="number"
            inputMode="numeric"
            min={0}
            max={LOCK_MAX_S}
            value={lock}
            onChange={(event) => {
              setLock(event.target.value);
            }}
            className="w-24 rounded-lg border border-stone-300 px-2 py-1 text-stone-900 focus:border-amber-600 focus:ring-2 focus:ring-amber-200 focus:outline-none"
          />
          secondes
        </label>
      )}
      {days && (
        <p className="text-xs text-stone-500">
          Pendant ce temps, la porte ne s'ouvre pas seule (0 : pas de verrouillage). Le bouton «
          Ouvrir quand même » reste toujours possible.
        </p>
      )}

      {saveError && (
        <p role="alert" className="text-sm text-red-700">
          {saveError}
        </p>
      )}
      {savedNotice && !dirty && (
        <p className="text-sm text-green-700">Planning enregistré et transmis au poulailler.</p>
      )}
      <button
        type="button"
        disabled={!dirty || saving}
        onClick={() => void save()}
        className="self-start rounded-lg bg-amber-700 px-4 py-2 font-medium text-white hover:bg-amber-800 disabled:cursor-not-allowed disabled:opacity-40"
      >
        {saving ? "Enregistrement…" : "Enregistrer"}
      </button>
    </section>
  );
}
