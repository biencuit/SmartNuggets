import type { ReactNode } from "react";
import { Navigate, useLocation } from "react-router-dom";

import { useAuth } from "../auth/useAuth";

/** Affiche la page seulement si l'éleveur est connecté ; sinon renvoie vers la connexion. */
export function ProtectedRoute({ children }: { children: ReactNode }) {
  const { user, checking, error } = useAuth();
  const location = useLocation();

  if (checking) {
    return <p className="p-8 text-center text-stone-500">Chargement…</p>;
  }
  if (!user && error) {
    return (
      <div className="p-8 text-center">
        <p className="text-red-700">{error}</p>
        <button
          type="button"
          className="mt-4 rounded-lg bg-amber-700 px-4 py-2 text-white"
          onClick={() => {
            window.location.reload();
          }}
        >
          Réessayer
        </button>
      </div>
    );
  }
  if (!user) {
    return <Navigate to="/connexion" replace state={{ from: location.pathname }} />;
  }
  return children;
}
