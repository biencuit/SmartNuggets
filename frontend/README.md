# Frontend SmartNuggets

Application web de l'éleveur : React 18, TypeScript, Vite, Tailwind CSS.

## Lancer en développement

Node.js 20 ou plus récent. L'API doit tourner sur le port 8000 (voir `backend/README.md`) :
Vite relaie automatiquement les appels `/api` vers elle.

```bash
cd frontend
npm install
npm run dev          # http://localhost:5173
```

Avec les données de démo du backend (`python -m app.seed`), on se connecte avec
`demo@smartnuggets.be` / `poulailler`.

## Scripts

| Commande                          | Rôle                                                       |
| --------------------------------- | ---------------------------------------------------------- |
| `npm run dev`                     | serveur de développement                                   |
| `npm run build`                   | vérification TypeScript + build de production dans `dist/` |
| `npm run lint`                    | ESLint (règles strictes typescript-eslint, `any` interdit) |
| `npm run format` / `format:check` | Prettier (100 colonnes)                                    |
| `npm test`                        | tests Vitest + Testing Library                             |

## Organisation

```
src/
├── api/client.ts          # appels à l'API, messages d'erreur en français
├── auth/                  # jeton de connexion (localStorage), useAuth()
├── components/            # ProtectedRoute, en-tête, mise en page, champs de formulaire
├── dashboard/             # cartes du tableau de bord : porte, poules, historique, alertes
├── pages/                 # Connexion, Inscription, Accueil, Tableau de bord
├── status/                # état du poulailler en temps réel (SSE)
└── test/                  # configuration des tests et faux fetch
```

## Pages

| Route                  | Page                                              |
| ---------------------- | ------------------------------------------------- |
| `/connexion`           | connexion                                         |
| `/inscription`         | création de compte                                |
| `/`                    | mes poulaillers, avec l'état du système de chacun |
| `/poulaillers/:coopId` | tableau de bord d'un poulailler (issue #26)       |

Le tableau de bord regroupe :

- **Porte** : état, ouverture et fermeture manuelles (`POST /command`). Les boutons sont
  désactivés quand le poulailler est hors ligne ; après une alerte prédateur non lue de moins de
  30 minutes, l'ouverture demande une confirmation.
- **Poules** : dedans, dehors, et correction du compteur (`CALIBRATE`).
- **Historique de la porte** : jour par jour, frise des périodes d'ouverture sur 24 h, nombre
  d'ouvertures, première ouverture, dernière fermeture, passages des poules. Les 200 derniers
  événements sont chargés.
- **Alertes** : non lues ou toutes, marquer comme lue, photo de l'alerte.

Tout se met à jour en direct par **un seul** flux SSE par poulailler : `useCoopStatus` reçoit
les messages `status`, et transmet `event` et `alert` au tableau de bord.

Une page réservée aux utilisateurs connectés s'entoure de `<ProtectedRoute>`. Le jeton
s'obtient avec `useAuth().token` et se passe aux fonctions de `api/client.ts`.
