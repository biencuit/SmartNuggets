import { useState, type FormEvent } from "react";

import type { CoopStatus } from "../api/client";

function Hens({ count, outside }: { count: number; outside?: boolean }) {
  return (
    <div aria-hidden="true" className="mt-2 flex min-h-5 flex-wrap gap-1">
      {Array.from({ length: count }, (_, index) => (
        <span
          key={index}
          className={`h-5 w-4 rounded-[50%_50%_46%_46%/58%_58%_42%_42%] ${
            outside ? "border-2 border-dashed border-amber-600" : "bg-amber-500"
          }`}
        />
      ))}
    </div>
  );
}

export function HenCountCard({
  status,
  onCalibrate,
}: {
  status: CoopStatus;
  onCalibrate: (insideCount: number) => Promise<void>;
}) {
  const [editing, setEditing] = useState(false);
  const [value, setValue] = useState(String(status.inside_count));
  const [message, setMessage] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [sending, setSending] = useState(false);

  async function submit(event: FormEvent) {
    event.preventDefault();
    const count = Number(value);
    if (!Number.isInteger(count) || count < 0 || count > status.total_hens) {
      setError(`Entrez un nombre entre 0 et ${String(status.total_hens)}.`);
      return;
    }
    setSending(true);
    setError(null);
    try {
      await onCalibrate(count);
      setEditing(false);
      setMessage("Correction envoyée au poulailler.");
    } catch (err) {
      setError(err instanceof Error ? err.message : "La correction n'a pas pu être envoyée.");
    } finally {
      setSending(false);
    }
  }

  return (
    <section
      aria-labelledby="poules-titre"
      className="flex flex-col gap-4 rounded-2xl bg-white p-5 shadow-sm ring-1 ring-stone-200"
    >
      <div className="flex items-baseline justify-between gap-2">
        <h2 id="poules-titre" className="text-lg font-semibold text-stone-900">
          Poules
        </h2>
        <span className="text-sm text-stone-500">{status.total_hens} au total</span>
      </div>

      <dl className="grid grid-cols-2 gap-3">
        <div className="rounded-xl bg-stone-50 p-3">
          <dt className="text-xs tracking-wide text-stone-500 uppercase">Dans le poulailler</dt>
          <dd className="text-4xl font-bold text-stone-900 tabular-nums">{status.inside_count}</dd>
          <Hens count={status.inside_count} />
        </div>
        <div className="rounded-xl bg-stone-50 p-3">
          <dt className="text-xs tracking-wide text-stone-500 uppercase">Dehors</dt>
          <dd className="text-4xl font-bold text-stone-900 tabular-nums">{status.outside_count}</dd>
          <Hens count={status.outside_count} outside />
        </div>
      </dl>

      {editing ? (
        <form onSubmit={(event) => void submit(event)} className="flex flex-wrap items-end gap-2">
          <label className="flex flex-col gap-1 text-sm text-stone-700">
            Nombre réel de poules dans le poulailler
            <input
              id="calibrate-count"
              type="number"
              inputMode="numeric"
              min={0}
              max={status.total_hens}
              value={value}
              onChange={(event) => {
                setValue(event.target.value);
              }}
              className="w-28 rounded-lg border border-stone-300 px-3 py-2"
            />
          </label>
          <button
            type="submit"
            disabled={sending || !status.online}
            className="rounded-lg bg-amber-700 px-4 py-2 font-medium text-white hover:bg-amber-800 disabled:opacity-40"
          >
            Corriger le compteur
          </button>
          <button
            type="button"
            onClick={() => {
              setEditing(false);
              setError(null);
            }}
            className="rounded-lg px-4 py-2 font-medium text-stone-700 ring-1 ring-stone-300 hover:bg-stone-50"
          >
            Annuler
          </button>
        </form>
      ) : (
        <button
          type="button"
          onClick={() => {
            setValue(String(status.inside_count));
            setMessage(null);
            setEditing(true);
          }}
          className="w-max text-sm font-medium text-amber-800 underline underline-offset-2 hover:text-amber-900"
        >
          Le compte est faux ? Le corriger
        </button>
      )}
      {message && (
        <p role="status" className="text-sm text-stone-600">
          {message}
        </p>
      )}
      {error && (
        <p role="alert" className="text-sm text-red-700">
          {error}
        </p>
      )}
    </section>
  );
}
