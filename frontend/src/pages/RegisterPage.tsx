import { useState, type FormEvent } from "react";
import { Link, Navigate, useNavigate } from "react-router-dom";

import { ApiError } from "../api/client";
import { useAuth } from "../auth/useAuth";
import { AuthLayout } from "../components/AuthLayout";
import { MIN_PASSWORD_LENGTH, validateRegistration } from "../auth/validation";
import { FormError, FormField, SubmitButton } from "../components/FormField";

export function RegisterPage() {
  const { user, register } = useAuth();
  const navigate = useNavigate();

  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [confirmation, setConfirmation] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  if (user) {
    return <Navigate to="/" replace />;
  }

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const problem = validateRegistration(password, confirmation);
    if (problem) {
      setError(problem);
      return;
    }
    setError(null);
    setBusy(true);
    try {
      await register(email.trim(), password);
      navigate("/", { replace: true });
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Inscription impossible.");
      setBusy(false);
    }
  }

  return (
    <AuthLayout title="Créer un compte">
      <form
        onSubmit={(event) => {
          void handleSubmit(event);
        }}
      >
        <FormError message={error} />
        <FormField
          id="email"
          label="Adresse email"
          type="email"
          autoComplete="email"
          required
          value={email}
          onChange={(event) => {
            setEmail(event.target.value);
          }}
        />
        <FormField
          id="password"
          label={`Mot de passe (${String(MIN_PASSWORD_LENGTH)} caractères minimum)`}
          type="password"
          autoComplete="new-password"
          required
          value={password}
          onChange={(event) => {
            setPassword(event.target.value);
          }}
        />
        <FormField
          id="confirmation"
          label="Confirmer le mot de passe"
          type="password"
          autoComplete="new-password"
          required
          value={confirmation}
          onChange={(event) => {
            setConfirmation(event.target.value);
          }}
        />
        <SubmitButton busy={busy}>Créer mon compte</SubmitButton>
      </form>
      <p className="mt-6 text-center text-sm text-stone-600">
        Déjà inscrit ?{" "}
        <Link to="/connexion" className="font-medium text-amber-800 underline">
          Se connecter
        </Link>
      </p>
    </AuthLayout>
  );
}
