import { useState } from "react";

import type { CoopAlert, CoopStatus } from "../api/client";
import { DOOR_STATE_LABELS, formatTime } from "./labels";

type DoorAction = "OPEN" | "CLOSE";

const STATE_CLASSES: Record<CoopStatus["door_state"], string> = {
  OPEN: "bg-amber-100 text-amber-900",
  CLOSED: "bg-emerald-100 text-emerald-900",
  OPENING: "bg-sky-100 text-sky-900",
  CLOSING: "bg-sky-100 text-sky-900",
  ERROR: "bg-red-100 text-red-900",
};

/** Dessin simple de la trappe : elle monte quand la porte est ouverte. */
function DoorDrawing({ open }: { open: boolean }) {
  return (
    <div
      aria-hidden="true"
      className="relative h-24 w-20 shrink-0 overflow-hidden rounded-t-[2.5rem] rounded-b-md border-4 border-stone-800 bg-stone-100"
    >
      <div
        className={`absolute inset-0 bg-[repeating-linear-gradient(90deg,#d97706_0_12px,#b45309_12px_14px)] transition-transform duration-700 motion-reduce:transition-none ${
          open ? "-translate-y-[82%]" : ""
        }`}
      />
    </div>
  );
}

export function DoorCard({
  status,
  predator,
  onCommand,
}: {
  status: CoopStatus;
  /** Alerte prédateur récente non lue : l'ouverture demande une confirmation. */
  predator: CoopAlert | undefined;
  onCommand: (action: DoorAction) => Promise<void>;
}) {
  // État de la porte au moment de l'envoi : la commande reste « en attente » tant qu'il ne change pas.
  const [sentFrom, setSentFrom] = useState<CoopStatus["door_state"] | null>(null);
  const [sending, setSending] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [confirming, setConfirming] = useState(false);

  const isOpen = status.door_state === "OPEN" || status.door_state === "OPENING";
  const moving = status.door_state === "OPENING" || status.door_state === "CLOSING";
  // Le poulailler a annoncé un nouvel état : la commande n'est plus en attente (ajustement
  // pendant le rendu, recommandé par React plutôt qu'un useEffect).
  const [seenState, setSeenState] = useState(status.door_state);
  if (seenState !== status.door_state) {
    setSeenState(status.door_state);
    setSentFrom(null);
  }
  const pending = sentFrom !== null;
  const disabled = !status.online || sending || moving;

  async function send(action: DoorAction) {
    setConfirming(false);
    setSending(true);
    setError(null);
    try {
      await onCommand(action);
      setSentFrom(status.door_state);
    } catch (err) {
      setError(err instanceof Error ? err.message : "La commande n'a pas pu être envoyée.");
    } finally {
      setSending(false);
    }
  }

  return (
    <section
      aria-labelledby="porte-titre"
      className="flex flex-col gap-4 rounded-2xl bg-white p-5 shadow-sm ring-1 ring-stone-200"
    >
      <h2 id="porte-titre" className="text-lg font-semibold text-stone-900">
        Porte
      </h2>

      <div className="flex items-center gap-5">
        <DoorDrawing open={isOpen} />
        <div className="flex flex-col gap-2">
          <span
            className={`w-max rounded-full px-3 py-1 text-sm font-semibold ${STATE_CLASSES[status.door_state]}`}
          >
            {DOOR_STATE_LABELS[status.door_state]}
          </span>
          {status.auto_close_time && (
            <p className="text-sm text-stone-600">
              Fermeture automatique à {status.auto_close_time.slice(0, 5)}
            </p>
          )}
        </div>
      </div>

      {predator && (
        <p role="alert" className="rounded-lg bg-red-50 p-3 text-sm text-red-800">
          Prédateur détecté à {formatTime(predator.created_at)}. Évitez d'ouvrir la porte tant que
          l'alerte n'est pas vérifiée.
        </p>
      )}
      {!status.online && (
        <p className="text-sm text-stone-600">
          Le poulailler est hors ligne : les commandes sont indisponibles.
        </p>
      )}

      {confirming ? (
        <div className="flex flex-col gap-3 rounded-lg border border-red-300 bg-red-50 p-3">
          <p className="text-sm text-red-900">
            Un prédateur a été signalé il y a moins de 30 minutes. Ouvrir quand même ?
          </p>
          <div className="flex flex-wrap gap-2">
            <button
              type="button"
              onClick={() => void send("OPEN")}
              className="rounded-lg bg-red-700 px-4 py-2 font-medium text-white hover:bg-red-800"
            >
              Ouvrir quand même
            </button>
            <button
              type="button"
              onClick={() => {
                setConfirming(false);
              }}
              className="rounded-lg px-4 py-2 font-medium text-stone-700 ring-1 ring-stone-300 hover:bg-stone-50"
            >
              Annuler
            </button>
          </div>
        </div>
      ) : (
        <div className="flex flex-wrap gap-2">
          <button
            type="button"
            disabled={disabled || isOpen}
            onClick={() => {
              if (predator) {
                setConfirming(true);
              } else {
                void send("OPEN");
              }
            }}
            className="rounded-lg bg-amber-700 px-4 py-2 font-medium text-white hover:bg-amber-800 disabled:cursor-not-allowed disabled:opacity-40"
          >
            Ouvrir la porte
          </button>
          <button
            type="button"
            disabled={disabled || !isOpen}
            onClick={() => void send("CLOSE")}
            className="rounded-lg px-4 py-2 font-medium text-stone-800 ring-1 ring-stone-300 hover:bg-stone-50 disabled:cursor-not-allowed disabled:opacity-40"
          >
            Fermer la porte
          </button>
        </div>
      )}

      {pending && (
        <p role="status" className="text-sm text-stone-600">
          Commande envoyée. En attente de la réponse du poulailler…
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
