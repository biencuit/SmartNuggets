import { useEffect, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";

import { api, ApiError, type Coop } from "../api/client";
import { useAuth } from "../auth/useAuth";
import { AppHeader } from "../components/AppHeader";
import { AddCoopForm } from "../dashboard/AddCoopForm";
import { CoopDashboard } from "../dashboard/CoopDashboard";

function coopPath(coopId: string): string {
  return `/poulaillers/${encodeURIComponent(coopId)}`;
}

/**
 * Accueil après connexion : le tableau de bord du poulailler (issue #26). Le poulailler affiché
 * vient de l'URL (/poulaillers/:coopId), sinon c'est le premier du compte. Sans poulailler, on
 * propose d'en ajouter un.
 */
export function HomePage() {
  const { coopId } = useParams();
  const navigate = useNavigate();
  const { token, logout } = useAuth();
  const [coops, setCoops] = useState<Coop[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [adding, setAdding] = useState(false);

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

  function handleCreated(coop: Coop) {
    setCoops((list) => [...(list ?? []), coop]);
    setAdding(false);
    navigate(coopPath(coop.id));
  }

  // Un poulailler absent de la liste n'est pas à cet éleveur : on n'interroge pas l'API.
  const selected = coops?.find((coop) => coop.id === coopId) ?? (coopId ? undefined : coops?.[0]);

  return (
    <div className="min-h-screen bg-stone-100">
      <AppHeader />

      <main className="mx-auto flex max-w-5xl flex-col gap-4 p-4">
        {error && <p className="text-red-700">{error}</p>}
        {coops === null && !error && <p className="text-stone-500">Chargement…</p>}

        {coops?.length === 0 && (
          <>
            <h1 className="text-2xl font-semibold text-stone-900">Bienvenue</h1>
            <p className="text-stone-600">
              Aucun poulailler n'est encore associé à votre compte. Ajoutez le vôtre pour voir son
              tableau de bord.
            </p>
            <div className="max-w-md">
              <AddCoopForm onCreated={handleCreated} />
            </div>
          </>
        )}

        {coops && coops.length > 0 && (
          <>
            <nav aria-label="Mes poulaillers" className="flex flex-wrap items-center gap-2">
              {coops.length > 1 && (
                <div className="flex flex-wrap rounded-lg bg-white ring-1 ring-stone-300">
                  {coops.map((coop) => (
                    <button
                      key={coop.id}
                      type="button"
                      aria-pressed={coop.id === selected?.id}
                      onClick={() => {
                        navigate(coopPath(coop.id));
                      }}
                      className="px-3 py-1.5 text-sm font-medium text-stone-700 first:rounded-l-lg last:rounded-r-lg aria-pressed:bg-amber-100 aria-pressed:text-amber-900"
                    >
                      {coop.name}
                    </button>
                  ))}
                </div>
              )}
              <button
                type="button"
                aria-expanded={adding}
                onClick={() => {
                  setAdding((open) => !open);
                }}
                className="rounded-lg px-3 py-1.5 text-sm font-medium text-amber-800 ring-1 ring-amber-300 hover:bg-amber-50"
              >
                + Ajouter un poulailler
              </button>
            </nav>

            {adding && (
              <div className="max-w-md">
                <AddCoopForm
                  onCreated={handleCreated}
                  onCancel={() => {
                    setAdding(false);
                  }}
                />
              </div>
            )}

            {selected ? (
              <CoopDashboard key={selected.id} coopId={selected.id} name={selected.name} />
            ) : (
              <p className="text-stone-700">
                Le poulailler « {coopId} » n'est pas associé à votre compte. Choisissez l'un des
                vôtres ci-dessus.
              </p>
            )}
          </>
        )}
      </main>
    </div>
  );
}
