/**
 * Message à montrer une fois sur la page de connexion (par exemple après la suppression du
 * compte). Passer par l'état de navigation ne marche pas : à la déconnexion, la route protégée
 * redirige elle-même vers /connexion. Si le stockage est bloqué, le message est simplement perdu.
 */
const NOTICE_KEY = "smartnuggets.notice";

export function rememberNotice(message: string): void {
  try {
    sessionStorage.setItem(NOTICE_KEY, message);
  } catch {
    // stockage indisponible (navigation privée stricte) : pas de message, rien de grave
  }
}

export function readNotice(): string | null {
  try {
    return sessionStorage.getItem(NOTICE_KEY);
  } catch {
    return null;
  }
}

/** À appeler une fois le message affiché (dans un effet : StrictMode lit l'état deux fois). */
export function clearNotice(): void {
  try {
    sessionStorage.removeItem(NOTICE_KEY);
  } catch {
    // rien à faire
  }
}
