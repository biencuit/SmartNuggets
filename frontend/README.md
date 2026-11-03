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
├── components/            # ProtectedRoute, mise en page, champs de formulaire
├── pages/                 # Connexion, Inscription, Accueil
└── test/                  # configuration des tests et faux fetch
```

Une page réservée aux utilisateurs connectés s'entoure de `<ProtectedRoute>`. Le jeton
s'obtient avec `useAuth().token` et se passe aux fonctions de `api/client.ts`.
