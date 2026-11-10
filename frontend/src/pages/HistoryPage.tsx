import { useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";

import { api, ApiError, type Coop } from "../api/client";
import { useAuth } from "../auth/useAuth";
import { AppHeader } from "../components/AppHeader";
import { HabitsSection } from "../history/HabitsSection";
import { HistoryJournal } from "../history/HistoryJournal";

/**
 * Page Historique d'un poulailler (#27, US perso de Théo) : habitudes des poules en haut,
 * journal complet et filtrable en dessous.
 */
export function HistoryPage() {
  const { coopId = "" } = useParams();
  const { token, logout } = useAuth();
  const [coops, setCoops] = useState<Coop[] | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!token) {
      return;
    }
    const controller = new AbortController();
    void (async () => {
      try {
        const result = await api.listCoops(token);
        if (!controller.signal.aborted) setCoops(result);
      } catch (err) {
        if (controller.signal.aborted) return;
        if (err instanceof ApiError && err.status === 401) {
          logout();
        } else {
          setError(err instanceof Error ? err.message : "Erreur inconnue");
        }
      }
    })();
    return () => {
      controller.abort();
    };
  }, [token, logout]);

  // Un poulailler absent de la liste n'est pas à cet éleveur : on n'interroge pas l'API.
  const coop = coops?.find((item) => item.id === coopId);

  return (
    <div className="min-h-screen bg-stone-100">
      <AppHeader />

      <main className="mx-auto flex max-w-5xl flex-col gap-4 p-4">
        <Link
          to={`/poulaillers/${encodeURIComponent(coopId)}`}
          className="self-start text-sm font-medium text-amber-800 underline underline-offset-2"
        >
          ← Tableau de bord
        </Link>

        {error && <p className="text-red-700">{error}</p>}
        {coops === null && !error && <p className="text-stone-500">Chargement…</p>}
        {coops && !coop && (
          <p className="text-stone-700">
            Le poulailler « {coopId} » n'est pas associé à votre compte.
          </p>
        )}

        {coop && (
          <>
            <div>
              <h1 className="text-2xl font-semibold text-stone-900">Historique</h1>
              <p className="text-stone-600">{coop.name}</p>
            </div>
            <HabitsSection coopId={coop.id} />
            <HistoryJournal coopId={coop.id} />
          </>
        )}
      </main>
    </div>
  );
}
