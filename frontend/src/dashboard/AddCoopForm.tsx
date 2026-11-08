import { useState, type FormEvent } from "react";

import { api, ApiError, type Coop } from "../api/client";
import { useAuth } from "../auth/useAuth";
import { FormError, FormField, SubmitButton } from "../components/FormField";

/** Même règle que l'API (CoopCreate.id) : c'est aussi le nom du compte MQTT du Raspberry Pi. */
const COOP_ID = /^[A-Za-z0-9_-]{1,64}$/;
/** Code d'appairage : 12 caractères, les tirets et les espaces sont ignorés. */
const CLAIM_CODE_LENGTH = 12;
const MAX_HENS = 1000;

/** Déclare un poulailler sur le compte de l'éleveur (`POST /coops`). */
export function AddCoopForm({
  onCreated,
  onCancel,
}: {
  onCreated: (coop: Coop) => void;
  /** Absent quand le compte n'a encore aucun poulailler : le formulaire est alors obligatoire. */
  onCancel?: () => void;
}) {
  const { token, logout } = useAuth();
  const [id, setId] = useState("");
  const [code, setCode] = useState("");
  const [name, setName] = useState("");
  const [hens, setHens] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const coopId = id.trim();
    const claimCode = code.trim();
    const totalHens = Number(hens);
    if (!COOP_ID.test(coopId)) {
      setError(
        "L'identifiant ne peut contenir que des lettres sans accent, des chiffres, _ et - (64 caractères au maximum).",
      );
      return;
    }
    if (claimCode.replace(/[\s-]/g, "").length !== CLAIM_CODE_LENGTH) {
      setError(
        `Le code d'appairage fait ${String(CLAIM_CODE_LENGTH)} caractères, par exemple K7QM-3XRA-PZ8D.`,
      );
      return;
    }
    if (!Number.isInteger(totalHens) || totalHens < 0 || totalHens > MAX_HENS) {
      setError(`Le nombre de poules doit être un nombre entier entre 0 et ${String(MAX_HENS)}.`);
      return;
    }
    if (!token) {
      return;
    }
    setError(null);
    setBusy(true);
    try {
      const coop = await api.createCoop(token, {
        id: coopId,
        claim_code: claimCode,
        name: name.trim(),
        total_hens: totalHens,
      });
      onCreated(coop);
    } catch (err) {
      if (err instanceof ApiError && err.status === 401) {
        logout();
        return;
      }
      setError(err instanceof Error ? err.message : "Le poulailler n'a pas pu être ajouté.");
      setBusy(false);
    }
  }

  return (
    <section
      aria-labelledby="ajout-titre"
      className="rounded-2xl bg-white p-5 shadow-sm ring-1 ring-stone-200"
    >
      <h2 id="ajout-titre" className="mb-1 text-lg font-semibold text-stone-900">
        Ajouter un poulailler
      </h2>
      <p className="mb-4 text-sm text-stone-600">
        L'identifiant (par exemple <code>coop_01</code>) et le code d'appairage sont sur l'étiquette
        du boîtier de votre poulailler. Le code ne marche qu'une fois.
      </p>
      <form
        onSubmit={(event) => {
          void handleSubmit(event);
        }}
      >
        <FormError message={error} />
        <FormField
          id="coop-id"
          label="Identifiant du poulailler"
          required
          maxLength={64}
          autoComplete="off"
          spellCheck={false}
          value={id}
          onChange={(event) => {
            setId(event.target.value);
          }}
        />
        <FormField
          id="coop-code"
          label="Code d'appairage"
          required
          maxLength={20}
          autoComplete="off"
          spellCheck={false}
          placeholder="XXXX-XXXX-XXXX"
          value={code}
          onChange={(event) => {
            setCode(event.target.value);
          }}
        />
        <FormField
          id="coop-name"
          label="Nom"
          required
          maxLength={100}
          value={name}
          onChange={(event) => {
            setName(event.target.value);
          }}
        />
        <FormField
          id="coop-hens"
          label="Nombre de poules"
          type="number"
          inputMode="numeric"
          required
          min={0}
          max={MAX_HENS}
          value={hens}
          onChange={(event) => {
            setHens(event.target.value);
          }}
        />
        <div className="flex flex-col gap-2">
          <SubmitButton busy={busy}>Ajouter le poulailler</SubmitButton>
          {onCancel && (
            <button
              type="button"
              onClick={onCancel}
              className="rounded-lg px-4 py-2 font-medium text-stone-700 ring-1 ring-stone-300 hover:bg-stone-50"
            >
              Annuler
            </button>
          )}
        </div>
      </form>
    </section>
  );
}
