/** Règles du formulaire d'inscription (les mêmes que celles de l'API). */

export const MIN_PASSWORD_LENGTH = 8;

export function validateRegistration(password: string, confirmation: string): string | null {
  if (password.length < MIN_PASSWORD_LENGTH) {
    return `Le mot de passe doit contenir au moins ${String(MIN_PASSWORD_LENGTH)} caractères.`;
  }
  if (password !== confirmation) {
    return "Les deux mots de passe ne correspondent pas.";
  }
  return null;
}
