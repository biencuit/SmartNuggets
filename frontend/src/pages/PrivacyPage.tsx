import type { ReactNode } from "react";
import { Link } from "react-router-dom";

/** Où tournent l'API et la base. À changer si le serveur est déplacé (page 13 du wiki). */
const HOSTING = "un serveur OVH, dans le datacenter de Singapour (hors de l'Union européenne)";
/** Durées de conservation appliquées par la purge quotidienne de l'API (`app/services/retention.py`). */
const PHOTO_RETENTION = "30 jours";
const DATA_RETENTION = "1 an";
const CONTACT = "[contact à définir par l'équipe]";

function Section({ title, children }: { title: string; children: ReactNode }) {
  return (
    <section className="flex flex-col gap-2">
      <h2 className="text-lg font-semibold text-stone-900">{title}</h2>
      {children}
    </section>
  );
}

/** Information des utilisateurs (RGPD, art. 13 ; issue #64). Page publique. */
export function PrivacyPage() {
  return (
    <div className="min-h-screen bg-stone-100">
      <header className="bg-amber-800 px-4 py-3 text-white">
        <Link to="/" className="text-lg font-bold">
          SmartNuggets
        </Link>
      </header>

      <main className="mx-auto flex max-w-2xl flex-col gap-6 p-4 pb-12 text-stone-700">
        <h1 className="text-2xl font-semibold text-stone-900">
          Vie privée et données personnelles
        </h1>
        <p>
          SmartNuggets est un projet étudiant de l'EPHEC (groupe G3). Cette page explique quelles
          données l'application garde, pourquoi, combien de temps, et comment les récupérer ou les
          faire effacer.
        </p>

        <Section title="Ce que nous gardons">
          <ul className="list-disc space-y-1 pl-5">
            <li>
              Votre <strong>compte</strong> : adresse email et mot de passe. Le mot de passe est
              haché (Argon2), jamais gardé en clair.
            </li>
            <li>
              Vos <strong>poulaillers</strong> : nom, nombre de poules, heure de fermeture, état de
              la porte et du boîtier (connexion, caméra).
            </li>
            <li>
              Les <strong>passages</strong> des poules et les mouvements de la porte, avec leur
              heure.
            </li>
            <li>
              Les <strong>alertes</strong>, et la <strong>photo</strong> prise quand un prédateur
              est vu. La caméra filme la porte du poulailler ; les images restent dans le boîtier,
              seule la photo d'une alerte est envoyée au serveur.
            </li>
          </ul>
        </Section>

        <Section title="Pourquoi">
          <p>
            Uniquement pour faire fonctionner le service que vous utilisez : suivre la porte,
            compter les poules et vous prévenir. Rien n'est vendu ni utilisé pour de la publicité.
          </p>
        </Section>

        <Section title="Combien de temps">
          <ul className="list-disc space-y-1 pl-5">
            <li>Photos des alertes : {PHOTO_RETENTION}.</li>
            <li>Passages, mouvements de porte et alertes : {DATA_RETENTION}.</li>
            <li>Compte et poulaillers : jusqu'à ce que vous supprimiez votre compte.</li>
          </ul>
          <p className="text-sm text-stone-600">
            Une purge automatique efface chaque jour ce qui a dépassé ces durées.
          </p>
        </Section>

        <Section title="Où">
          <p>Les données sont hébergées sur {HOSTING}.</p>
        </Section>

        <Section title="Vos droits">
          <ul className="list-disc space-y-1 pl-5">
            <li>
              <strong>Récupérer vos données</strong> : « Télécharger mes données » dans{" "}
              <Link to="/compte" className="font-medium text-amber-800 underline">
                Mon compte
              </Link>{" "}
              (fichier JSON).
            </li>
            <li>
              <strong>Tout effacer</strong> : « Supprimer mon compte », au même endroit. Le compte,
              les poulaillers, les passages, les alertes et les photos sont supprimés tout de suite.
            </li>
            <li>
              <strong>Corriger ou poser une question</strong> : {CONTACT}.
            </li>
            <li>
              Vous pouvez aussi vous adresser à l'
              <a
                href="https://www.autoriteprotectiondonnees.be"
                className="font-medium text-amber-800 underline"
              >
                Autorité de protection des données
              </a>
              .
            </li>
          </ul>
        </Section>
      </main>
    </div>
  );
}
