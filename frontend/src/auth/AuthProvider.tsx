import { useCallback, useEffect, useMemo, useState, type ReactNode } from "react";

import { api, ApiError, type User } from "../api/client";
import { AuthContext, TOKEN_KEY, type AuthContextValue } from "./context";

/**
 * Garde le jeton de l'éleveur dans le navigateur (localStorage) et l'utilisateur connecté.
 * Au chargement, le jeton enregistré est vérifié auprès de l'API (GET /auth/me).
 */
export function AuthProvider({ children }: { children: ReactNode }) {
  const [token, setToken] = useState<string | null>(() => localStorage.getItem(TOKEN_KEY));
  const [user, setUser] = useState<User | null>(null);
  const [checking, setChecking] = useState<boolean>(() => localStorage.getItem(TOKEN_KEY) !== null);
  const [error, setError] = useState<string | null>(null);

  const logout = useCallback(() => {
    localStorage.removeItem(TOKEN_KEY);
    setToken(null);
    setUser(null);
  }, []);

  useEffect(() => {
    const stored = localStorage.getItem(TOKEN_KEY);
    if (stored === null) {
      return;
    }
    const controller = new AbortController();
    void (async () => {
      try {
        const me = await api.me(stored);
        if (!controller.signal.aborted) {
          setUser(me);
        }
      } catch (err) {
        if (controller.signal.aborted) {
          return;
        }
        if (err instanceof ApiError && err.status === 401) {
          localStorage.removeItem(TOKEN_KEY);
          setToken(null);
        } else {
          setError(err instanceof Error ? err.message : "Erreur inconnue");
        }
      } finally {
        if (!controller.signal.aborted) {
          setChecking(false);
        }
      }
    })();
    return () => {
      controller.abort();
    };
  }, []);

  const login = useCallback(async (email: string, password: string) => {
    const { access_token } = await api.login(email, password);
    const me = await api.me(access_token);
    localStorage.setItem(TOKEN_KEY, access_token);
    setToken(access_token);
    setUser(me);
    setError(null);
  }, []);

  const register = useCallback(
    async (email: string, password: string) => {
      await api.register(email, password);
      await login(email, password);
    },
    [login],
  );

  const value = useMemo<AuthContextValue>(
    () => ({ user, token, checking, error, login, register, logout }),
    [user, token, checking, error, login, register, logout],
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}
