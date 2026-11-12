import { Link } from "react-router-dom";

import { useAuth } from "../auth/useAuth";

/** Bandeau commun des pages connectées : nom de l'application, « Mon compte », déconnexion. */
export function AppHeader() {
  const { user, logout } = useAuth();
  return (
    <header className="flex items-center justify-between bg-amber-800 px-4 py-3 text-white">
      <Link to="/" className="text-lg font-bold">
        SmartNuggets
      </Link>
      <div className="flex items-center gap-3 text-sm">
        <span className="hidden sm:inline">{user?.email}</span>
        <Link to="/compte" className="rounded-lg px-2 py-1.5 hover:bg-white/15">
          Mon compte
        </Link>
        <button
          type="button"
          onClick={logout}
          className="rounded-lg bg-white/15 px-3 py-1.5 hover:bg-white/25"
        >
          Déconnexion
        </button>
      </div>
    </header>
  );
}
