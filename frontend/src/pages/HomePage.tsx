import { useEffect, useState } from "react";

import { api, ApiError, type Coop } from "../api/client";
import { useAuth } from "../auth/useAuth";

/** Page d'accueil après connexion : la liste des poulaillers de l'éleveur. */
export function HomePage() {
  const { user, token, logout } = useAuth();
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
    <div className="min-h-screen">
      <header className="flex items-center justify-between bg-amber-800 px-4 py-3 text-white">
        <span className="text-lg font-bold">SmartNuggets</span>
        <div className="flex items-center gap-3 text-sm">
          <span className="hidden sm:inline">{user?.email}</span>
          <button
            type="button"
            onClick={logout}
            className="rounded-lg bg-white/15 px-3 py-1.5 hover:bg-white/25"
          >
            Déconnexion
          </button>
        </div>
      </header>

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
              <p className="font-medium text-stone-900">{coop.name}</p>
              <p className="text-sm text-stone-500">
                {coop.total_hens} poules · identifiant {coop.id}
              </p>
              {/* Le tableau de bord du poulailler (issue #26) vient se brancher ici. */}
            </li>
          ))}
        </ul>
      </main>
    </div>
  );
}
