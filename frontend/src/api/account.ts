import { apiFetch, type NotificationPrefs } from "./client";

/** Toutes les données du compte (RGPD, art. 20) : compte, poulaillers, passages, alertes. */
export function exportMyData(token: string): Promise<unknown> {
  return apiFetch<unknown>("/auth/me/export", { token });
}

/** Supprime le compte et tout ce qui lui appartient (RGPD, art. 17). Mot de passe redemandé. */
export async function deleteMyAccount(token: string, password: string): Promise<void> {
  await apiFetch<null>("/auth/me", { method: "DELETE", token, json: { password } });
}

/** Préférences de notification actuelles (#68). */
export function getNotificationPrefs(token: string): Promise<NotificationPrefs> {
  return apiFetch<NotificationPrefs>("/auth/me/notifications", { token });
}

/** Active/règle les notifications Telegram. */
export function updateNotificationPrefs(
  token: string,
  prefs: NotificationPrefs,
): Promise<NotificationPrefs> {
  return apiFetch<NotificationPrefs>("/auth/me/notifications", {
    method: "PATCH",
    token,
    json: prefs,
  });
}
