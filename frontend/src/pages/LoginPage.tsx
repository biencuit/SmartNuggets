import { useEffect, useState, type FormEvent } from "react";
import { Link, Navigate, useLocation, useNavigate } from "react-router-dom";

import { ApiError } from "../api/client";
import { clearNotice, readNotice } from "../auth/notice";
import { useAuth } from "../auth/useAuth";
import { AuthLayout } from "../components/AuthLayout";
import { FormError, FormField, SubmitButton } from "../components/FormField";

export function LoginPage() {
  const { user, login } = useAuth();
  const navigate = useNavigate();
  const location = useLocation();
  const from = (location.state as { from?: string } | null)?.from ?? "/";
  // Message laissé par une autre page (compte supprimé), affiché une seule fois.
  const [notice] = useState(readNotice);
  useEffect(clearNotice, []);

  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  if (user) {
    return <Navigate to={from} replace />;
  }

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setError(null);
    setBusy(true);
    try {
      await login(email.trim(), password);
      navigate(from, { replace: true });
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Connexion impossible.");
      setBusy(false);
    }
  }

  return (
    <AuthLayout title="Connexion">
      <form
        onSubmit={(event) => {
          void handleSubmit(event);
        }}
      >
        {notice && (
          <p
            role="status"
            className="mb-4 rounded-lg bg-emerald-50 px-3 py-2 text-sm text-emerald-800"
          >
            {notice}
          </p>
        )}
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
          label="Mot de passe"
          type="password"
          autoComplete="current-password"
          required
          value={password}
          onChange={(event) => {
            setPassword(event.target.value);
          }}
        />
        <SubmitButton busy={busy}>Se connecter</SubmitButton>
      </form>
      <p className="mt-6 text-center text-sm text-stone-600">
        Pas encore de compte ?{" "}
        <Link to="/inscription" className="font-medium text-amber-800 underline">
          Créer un compte
        </Link>
      </p>
    </AuthLayout>
  );
}
