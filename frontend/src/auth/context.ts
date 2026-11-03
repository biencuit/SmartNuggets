import { createContext } from "react";

import type { User } from "../api/client";

export interface AuthContextValue {
  user: User | null;
  token: string | null;
  /** Vrai pendant la vérification du jeton enregistré, au chargement de l'application. */
  checking: boolean;
  /** Erreur réseau pendant cette vérification (le jeton est gardé). */
  error: string | null;
  login: (email: string, password: string) => Promise<void>;
  register: (email: string, password: string) => Promise<void>;
  logout: () => void;
}

export const AuthContext = createContext<AuthContextValue | null>(null);

export const TOKEN_KEY = "smartnuggets.token";
