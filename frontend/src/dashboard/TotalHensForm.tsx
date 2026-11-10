import { useState, type FormEvent } from "react";

/** Nombre maximum accepté par l'API (`CoopUpdate.total_hens`). */
export const MAX_HENS = 1000;

/**
 * Régler le nombre total de poules du poulailler (US-COMPT-3, #18).
 * Ce total sert à calculer combien de poules sont dehors, et à prévenir l'éleveur si la
 * porte se ferme le soir alors qu'il en manque (US-COMPT-4, #19, côté serveur).
 */
export function TotalHensForm({
  total,
  onSave,
}: {
  total: number;
  onSave: (total: number) => Promise<void>;
}) {
  const [editing, setEditing] = useState(false);
  const [value, setValue] = useState(String(total));
  const [message, setMessage] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);

  async function submit(event: FormEvent) {
    event.preventDefault();
    const count = Number(value);
    if (value.trim() === "" || !Number.isInteger(count) || count < 0 || count > MAX_HENS) {
      setError(`Entrez un nombre entier entre 0 et ${String(MAX_HENS)}.`);
      return;
    }
    setSaving(true);
    setError(null);
    try {
      await onSave(count);
      setEditing(false);
      setMessage(`C'est noté : ${String(count)} poules au total.`);
    } catch (err) {
      setError(
        err instanceof Error ? err.message : "Le nombre de poules n'a pas pu être enregistré.",
      );
    } finally {
      setSaving(false);
    }
  }

  if (!editing) {
    return (
      <div className="flex flex-col gap-1">
        <button
          type="button"
          onClick={() => {
            setValue(String(total));
            setMessage(null);
            setEditing(true);
          }}
          className="w-max text-sm font-medium text-amber-800 underline underline-offset-2 hover:text-amber-900"
        >
          Modifier le nombre total de poules
        </button>
        {message && (
          <p role="status" className="text-sm text-stone-600">
            {message}
          </p>
        )}
      </div>
    );
  }

  return (
    <form
      noValidate
      onSubmit={(event) => void submit(event)}
      className="flex flex-wrap items-end gap-2"
    >
      <label className="flex flex-col gap-1 text-sm text-stone-700">
        Nombre total de poules
        <input
          id="total-hens"
          type="number"
          inputMode="numeric"
          min={0}
          max={MAX_HENS}
          value={value}
          onChange={(event) => {
            setValue(event.target.value);
          }}
          className="w-28 rounded-lg border border-stone-300 px-3 py-2"
        />
      </label>
      <button
        type="submit"
        disabled={saving}
        className="rounded-lg bg-amber-700 px-4 py-2 font-medium text-white hover:bg-amber-800 disabled:opacity-40"
      >
        Enregistrer
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
      {error && (
        <p role="alert" className="w-full text-sm text-red-700">
          {error}
        </p>
      )}
    </form>
  );
}
