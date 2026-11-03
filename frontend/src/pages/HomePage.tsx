import { useEffect, useState } from "react";
import { Link } from "react-router-dom";

import { api, ApiError, type Coop } from "../api/client";
import { useAuth } from "../auth/useAuth";
import { AppHeader } from "../components/AppHeader";
import { CoopStatusPanel } from "../components/CoopStatusPanel";

/** Page d'accueil après connexion : la liste des poulaillers de l'éleveur. */
export function HomePage() {
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
        if (!controller.signal.aborted) {
          setCoops(result);
        }
      } catch (err) {
        if (controller.signal.aborted) {
          return;
        }
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

  return (
    <div className="min-h-screen bg-stone-100">
      <AppHeader />

      <main className="mx-auto max-w-3xl p-4">
        <h1 className="mb-4 text-xl font-semibold text-stone-900">Mes poulaillers</h1>
        {error && <p className="text-red-700">{error}</p>}
        {coops === null && !error && <p className="text-stone-500">Chargement…</p>}
        {coops?.length === 0 && (
          <p className="text-stone-600">Aucun poulailler n'est encore associé à votre compte.</p>
        )}
        <ul className="space-y-3">
          {coops?.map((coop) => (
            <li key={coop.id} className="rounded-2xl bg-white p-4 shadow-sm ring-1 ring-stone-200">
              <div className="flex flex-wrap items-start justify-between gap-2">
                <div>
                  <p className="font-medium text-stone-900">{coop.name}</p>
                  <p className="text-sm text-stone-500">
                    {coop.total_hens} poules · identifiant {coop.id}
                  </p>
                </div>
                <Link
                  to={`/poulaillers/${encodeURIComponent(coop.id)}`}
                  className="rounded-lg bg-amber-700 px-4 py-2 text-sm font-medium text-white hover:bg-amber-800"
                >
                  Ouvrir le tableau de bord
                </Link>
              </div>
              <CoopStatusPanel coopId={coop.id} />
            </li>
          ))}
        </ul>
      </main>
    </div>
  );
}
