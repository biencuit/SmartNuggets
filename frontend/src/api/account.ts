import { apiFetch } from "./client";

/** Toutes les données du compte (RGPD, art. 20) : compte, poulaillers, passages, alertes. */
export function exportMyData(token: string): Promise<unknown> {
  return apiFetch<unknown>("/auth/me/export", { token });
}

/** Supprime le compte et tout ce qui lui appartient (RGPD, art. 17). Mot de passe redemandé. */
export async function deleteMyAccount(token: string, password: string): Promise<void> {
  await apiFetch<null>("/auth/me", { method: "DELETE", token, json: { password } });
}
