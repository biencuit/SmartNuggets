import { type FormEvent, useEffect, useState } from "react";
import { Link } from "react-router-dom";

import {
  deleteMyAccount,
  exportMyData,
  getNotificationPrefs,
  updateNotificationPrefs,
} from "../api/account";
import { ApiError } from "../api/client";
import { rememberNotice } from "../auth/notice";
import { useAuth } from "../auth/useAuth";
import { AppHeader } from "../components/AppHeader";
import { FormError, FormField } from "../components/FormField";

const EXPORT_FILE = "smartnuggets-mes-donnees.json";
const CARD = "flex flex-col gap-3 rounded-2xl bg-white p-5 shadow-sm ring-1";

function formatDay(iso: string): string {
  return new Date(iso).toLocaleDateString("fr-BE", {
    day: "numeric",
    month: "long",
    year: "numeric",
  });
}

/** Fait télécharger `data` au navigateur, en JSON lisible. */
function saveJson(data: unknown, fileName: string) {
  const blob = new Blob([JSON.stringify(data, null, 2)], { type: "application/json" });
  const url = URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = url;
  link.download = fileName;
  document.body.append(link);
  link.click();
  link.remove();
  URL.revokeObjectURL(url);
}

/** « Mon compte » : récupérer ses données et supprimer son compte (RGPD, issue #64). */
export function ProfilePage() {
  const { user, token, logout } = useAuth();

  const [exporting, setExporting] = useState(false);
  const [exportError, setExportError] = useState<string | null>(null);
  const [password, setPassword] = useState("");
  const [understood, setUnderstood] = useState(false);
  const [deleting, setDeleting] = useState(false);
  const [deleteError, setDeleteError] = useState<string | null>(null);

  const [pushEnabled, setPushEnabled] = useState(false);
  const [telegramChatId, setTelegramChatId] = useState("");
  const [criticalOnly, setCriticalOnly] = useState(false);
  const [notifSaving, setNotifSaving] = useState(false);
  const [notifSaved, setNotifSaved] = useState(false);
  const [notifError, setNotifError] = useState<string | null>(null);

  useEffect(() => {
    if (!token) {
      return;
    }
    const controller = new AbortController();
    void (async () => {
      try {
        const prefs = await getNotificationPrefs(token);
        if (controller.signal.aborted) {
          return;
        }
        setPushEnabled(prefs.push_enabled);
        setTelegramChatId(prefs.telegram_chat_id ?? "");
        setCriticalOnly(prefs.notify_critical_only);
      } catch (err) {
        if (controller.signal.aborted) {
          return;
        }
        if (err instanceof ApiError && err.status === 401) {
          logout();
        }
      }
    })();
    return () => {
      controller.abort();
    };
  }, [token, logout]);

  async function saveNotifications(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!token) {
      return;
    }
    setNotifError(null);
    setNotifSaved(false);
    setNotifSaving(true);
    try {
      await updateNotificationPrefs(token, {
        push_enabled: pushEnabled,
        telegram_chat_id: telegramChatId.trim() === "" ? null : telegramChatId.trim(),
        notify_critical_only: criticalOnly,
      });
      setNotifSaved(true);
    } catch (err) {
      if (err instanceof ApiError && err.status === 401) {
        logout();
        return;
      }
      setNotifError(err instanceof ApiError ? err.message : "L'enregistrement a échoué.");
    } finally {
      setNotifSaving(false);
    }
  }

  async function download() {
    if (!token) {
      return;
    }
    setExportError(null);
    setExporting(true);
    try {
      saveJson(await exportMyData(token), EXPORT_FILE);
    } catch (err) {
      setExportError(err instanceof ApiError ? err.message : "Le téléchargement a échoué.");
    } finally {
      setExporting(false);
    }
  }

  async function remove(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!token) {
      return;
    }
    setDeleteError(null);
    setDeleting(true);
    try {
      await deleteMyAccount(token, password);
    } catch (err) {
      setDeleteError(err instanceof ApiError ? err.message : "La suppression a échoué.");
      setDeleting(false);
      return;
    }
    rememberNotice("Votre compte et toutes ses données ont été supprimés.");
    logout(); // la route protégée renvoie alors vers la connexion
  }

  return (
    <div className="min-h-screen bg-stone-100">
      <AppHeader />

      <main className="mx-auto flex max-w-2xl flex-col gap-4 p-4">
        <h1 className="text-2xl font-semibold text-stone-900">Mon compte</h1>

        <section aria-labelledby="compte-titre" className={`${CARD} ring-stone-200`}>
          <h2 id="compte-titre" className="text-lg font-semibold text-stone-900">
            Mes informations
          </h2>
          <p className="text-stone-700">
            <span className="font-medium">Adresse email :</span> {user?.email}
          </p>
          {user && (
            <p className="text-stone-700">
              <span className="font-medium">Inscrit le</span> {formatDay(user.created_at)}
            </p>
          )}
          <p className="text-sm text-stone-600">
            Ce que SmartNuggets garde sur vous, et combien de temps :{" "}
            <Link to="/vie-privee" className="font-medium text-amber-800 underline">
              Vie privée
            </Link>
            .
          </p>
        </section>

        <section aria-labelledby="notifications-titre" className={`${CARD} ring-stone-200`}>
          <h2 id="notifications-titre" className="text-lg font-semibold text-stone-900">
            Notifications
          </h2>
          <p className="text-sm text-stone-600">
            Recevez une alerte (prédateur, batterie faible, poulailler hors ligne...) sur Telegram,
            même sans avoir l'application ouverte.
          </p>
          <form
            onSubmit={(event) => {
              void saveNotifications(event);
            }}
          >
            <label className="mb-4 flex items-start gap-2 text-sm text-stone-700">
              <input
                type="checkbox"
                checked={pushEnabled}
                onChange={(event) => {
                  setPushEnabled(event.target.checked);
                }}
                className="mt-0.5"
              />
              Activer les notifications Telegram
            </label>
            <FormField
              id="telegram-chat-id"
              label="Identifiant de chat Telegram"
              placeholder="ex. 123456789"
              value={telegramChatId}
              onChange={(event) => {
                setTelegramChatId(event.target.value);
              }}
            />
            <p className="-mt-3 mb-4 text-xs text-stone-500">
              Pour l'obtenir : démarrez une conversation avec <code>@userinfobot</code> sur
              Telegram, il répond avec votre identifiant.
            </p>
            <label className="mb-4 flex items-start gap-2 text-sm text-stone-700">
              <input
                type="checkbox"
                checked={criticalOnly}
                onChange={(event) => {
                  setCriticalOnly(event.target.checked);
                }}
                className="mt-0.5"
              />
              Ne me notifier que pour les alertes critiques (prédateur, porte bloquée)
            </label>
            <FormError message={notifError} />
            {notifSaved && <p className="mb-4 text-sm text-green-700">Préférences enregistrées.</p>}
            <button
              type="submit"
              disabled={notifSaving}
              className="self-start rounded-lg bg-amber-700 px-4 py-2 font-medium text-white hover:bg-amber-800 disabled:opacity-60"
            >
              {notifSaving ? "Enregistrement…" : "Enregistrer"}
            </button>
          </form>
        </section>

        <section aria-labelledby="export-titre" className={`${CARD} ring-stone-200`}>
          <h2 id="export-titre" className="text-lg font-semibold text-stone-900">
            Récupérer mes données
          </h2>
          <p className="text-sm text-stone-600">
            Un fichier JSON avec votre compte, vos poulaillers, leurs passages et leurs alertes.
          </p>
          <FormError message={exportError} />
          <button
            type="button"
            disabled={exporting}
            onClick={() => void download()}
            className="self-start rounded-lg bg-amber-700 px-4 py-2 font-medium text-white hover:bg-amber-800 disabled:opacity-60"
          >
            {exporting ? "Préparation…" : "Télécharger mes données"}
          </button>
        </section>

        <section aria-labelledby="suppression-titre" className={`${CARD} ring-red-200`}>
          <h2 id="suppression-titre" className="text-lg font-semibold text-red-800">
            Supprimer mon compte
          </h2>
          <p className="text-sm text-stone-600">
            Votre compte, vos poulaillers, leurs passages, leurs alertes et leurs photos seront
            effacés définitivement. Le boîtier pourra être ajouté à un autre compte.
          </p>
          <form
            onSubmit={(event) => {
              void remove(event);
            }}
          >
            <FormError message={deleteError} />
            <FormField
              id="delete-password"
              label="Mot de passe"
              type="password"
              autoComplete="current-password"
              required
              value={password}
              onChange={(event) => {
                setPassword(event.target.value);
              }}
            />
            <label className="mb-4 flex items-start gap-2 text-sm text-stone-700">
              <input
                type="checkbox"
                checked={understood}
                onChange={(event) => {
                  setUnderstood(event.target.checked);
                }}
                className="mt-0.5"
              />
              Je comprends que tout sera effacé et ne pourra pas être récupéré.
            </label>
            <button
              type="submit"
              disabled={!understood || deleting}
              className="rounded-lg bg-red-700 px-4 py-2 font-medium text-white hover:bg-red-800 disabled:opacity-50"
            >
              {deleting ? "Suppression…" : "Supprimer mon compte"}
            </button>
          </form>
        </section>
      </main>
    </div>
  );
}
