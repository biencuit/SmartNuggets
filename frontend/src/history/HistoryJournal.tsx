import { useEffect, useMemo, useState } from "react";
import { useSearchParams } from "react-router-dom";

import {
  api,
  ApiError,
  type AlertType,
  type EventType,
  type HistoryCategory,
  type HistoryItem,
  type HistoryQuery,
} from "../api/client";
import { useAuth } from "../auth/useAuth";
import { dayKey, dayLabel, startOfDay } from "../dashboard/history";
import { ALERT_TITLES, EVENT_LABELS, formatTime, TRIGGER_LABELS } from "../dashboard/labels";
import { plural } from "./format";
import {
  CATEGORIES,
  CATEGORY_LABELS,
  filtersFromParams,
  filtersToParams,
  type HistoryFilters,
  type Period,
  PERIOD_LABELS,
  PERIODS,
  periodRange,
  rangeError,
} from "./period";

const PAGE_SIZE = 50;

interface Loaded {
  query: HistoryQuery;
  items: HistoryItem[];
  total: number;
}

/** Couleur de la pastille de chaque ligne (l'identité est aussi donnée par le texte). */
function dotClass(item: HistoryItem): string {
  if (item.kind === "alert") return "bg-red-600";
  if (item.type === "HEN_ENTRY") return "bg-emerald-700";
  if (item.type === "HEN_EXIT") return "bg-amber-600";
  return "bg-stone-400";
}

function itemTitle(item: HistoryItem): string {
  return item.kind === "alert"
    ? ALERT_TITLES[item.type as AlertType]
    : EVENT_LABELS[item.type as EventType];
}

function groupByDay(items: HistoryItem[]): [string, HistoryItem[]][] {
  const groups = new Map<string, HistoryItem[]>();
  for (const item of items) {
    const key = dayKey(new Date(item.occurred_at));
    groups.set(key, [...(groups.get(key) ?? []), item]);
  }
  return [...groups.entries()];
}

function groupTitle(key: string, now: Date): string {
  const label = dayLabel(key, now);
  const date = startOfDay(key).toLocaleDateString("fr-BE", {
    weekday: "long",
    day: "numeric",
    month: "long",
  });
  return label === "Aujourd'hui" || label === "Hier" ? `${label} · ${date}` : date;
}

/**
 * Journal complet (#27) : passages, porte et alertes dans une seule liste, filtrable par type
 * et par période, avec « Charger plus ». Les filtres sont dans l'URL.
 */
export function HistoryJournal({ coopId }: { coopId: string }) {
  const { token, logout } = useAuth();
  const [searchParams, setSearchParams] = useSearchParams();
  const filters = useMemo(() => filtersFromParams(searchParams), [searchParams]);
  const invalid = rangeError(filters);

  // Requête de la première page : gardée telle quelle pour les pages suivantes, même si
  // l'heure avance entre-temps (sinon les pages ne se suivraient plus).
  const query = useMemo<HistoryQuery | null>(() => {
    if (invalid) return null;
    const range = periodRange(filters, new Date());
    return {
      categories: filters.categories,
      since: range.since?.toISOString() ?? null,
      until: range.until?.toISOString() ?? null,
      limit: PAGE_SIZE,
      offset: 0,
    };
  }, [filters, invalid]);

  // Résultats et erreur sont rangés avec la requête qui les a produits : quand les filtres
  // changent, une réponse arrivée en retard pour les anciens filtres ne s'affiche pas.
  const [loaded, setLoaded] = useState<Loaded | null>(null);
  const [failure, setFailure] = useState<{ query: HistoryQuery; message: string } | null>(null);
  const [loadingMore, setLoadingMore] = useState(false);
  const [openImage, setOpenImage] = useState<number | null>(null);

  const current = loaded && loaded.query === query ? loaded : null;
  const error = failure && failure.query === query ? failure.message : null;
  const items = current?.items ?? null;
  const total = current?.total ?? 0;

  useEffect(() => {
    if (!token || !query) {
      return;
    }
    const controller = new AbortController();
    void (async () => {
      try {
        const page = await api.listHistory(token, coopId, query);
        if (!controller.signal.aborted) setLoaded({ query, ...page });
      } catch (err) {
        if (controller.signal.aborted) return;
        if (err instanceof ApiError && err.status === 401) {
          logout();
        } else {
          setFailure({ query, message: err instanceof Error ? err.message : "Erreur inconnue" });
        }
      }
    })();
    return () => {
      controller.abort();
    };
  }, [token, coopId, query, logout]);

  async function loadMore() {
    if (!token || !query || !current) return;
    setLoadingMore(true);
    setFailure(null);
    try {
      const page = await api.listHistory(token, coopId, {
        ...query,
        offset: current.items.length,
      });
      setLoaded({ query, total: page.total, items: [...current.items, ...page.items] });
    } catch (err) {
      if (err instanceof ApiError && err.status === 401) {
        logout();
      } else {
        setFailure({ query, message: err instanceof Error ? err.message : "Erreur inconnue" });
      }
    } finally {
      setLoadingMore(false);
    }
  }

  function update(changes: Partial<HistoryFilters>) {
    setSearchParams(filtersToParams({ ...filters, ...changes }));
  }

  function toggleCategory(category: HistoryCategory) {
    const chosen = filters.categories.includes(category)
      ? filters.categories.filter((c) => c !== category)
      : [...filters.categories, category];
    // Les quatre cochées = tout : on revient au filtre vide.
    update({ categories: chosen.length === CATEGORIES.length ? [] : chosen });
  }

  const now = new Date();
  const remaining = items ? total - items.length : 0;

  return (
    <section
      aria-labelledby="journal-titre"
      className="flex flex-col gap-4 rounded-2xl bg-white p-5 shadow-sm ring-1 ring-stone-200"
    >
      <h2 id="journal-titre" className="text-lg font-semibold text-stone-900">
        Journal
      </h2>

      <div className="flex flex-col gap-3">
        <div role="group" aria-label="Filtrer par type" className="flex flex-wrap gap-2">
          <button
            type="button"
            aria-pressed={filters.categories.length === 0}
            onClick={() => {
              update({ categories: [] });
            }}
            className="rounded-full px-3 py-1 text-sm font-medium text-stone-700 ring-1 ring-stone-300 aria-pressed:bg-amber-100 aria-pressed:text-amber-900 aria-pressed:ring-amber-300"
          >
            Tout
          </button>
          {CATEGORIES.map((category) => (
            <button
              key={category}
              type="button"
              aria-pressed={filters.categories.includes(category)}
              onClick={() => {
                toggleCategory(category);
              }}
              className="rounded-full px-3 py-1 text-sm font-medium text-stone-700 ring-1 ring-stone-300 aria-pressed:bg-amber-100 aria-pressed:text-amber-900 aria-pressed:ring-amber-300"
            >
              {CATEGORY_LABELS[category]}
            </button>
          ))}
        </div>

        <div className="flex flex-wrap items-end gap-3">
          <label className="flex flex-col gap-1 text-sm text-stone-700">
            Période
            <select
              value={filters.period}
              onChange={(event) => {
                update({ period: event.target.value as Period });
              }}
              className="rounded-lg bg-white px-3 py-1.5 ring-1 ring-stone-300"
            >
              {PERIODS.map((period) => (
                <option key={period} value={period}>
                  {PERIOD_LABELS[period]}
                </option>
              ))}
            </select>
          </label>
          {filters.period === "perso" && (
            <>
              <label className="flex flex-col gap-1 text-sm text-stone-700">
                Du
                <input
                  type="date"
                  value={filters.from ?? ""}
                  onChange={(event) => {
                    update({ from: event.target.value || null });
                  }}
                  className="rounded-lg px-3 py-1.5 ring-1 ring-stone-300"
                />
              </label>
              <label className="flex flex-col gap-1 text-sm text-stone-700">
                Au
                <input
                  type="date"
                  value={filters.to ?? ""}
                  onChange={(event) => {
                    update({ to: event.target.value || null });
                  }}
                  className="rounded-lg px-3 py-1.5 ring-1 ring-stone-300"
                />
              </label>
            </>
          )}
        </div>
      </div>

      {invalid && (
        <p role="alert" className="text-sm text-red-700">
          {invalid}
        </p>
      )}
      {error && (
        <p role="alert" className="text-sm text-red-700">
          {error}
        </p>
      )}
      {!items && !error && !invalid && <p className="text-sm text-stone-500">Chargement…</p>}

      {items && !invalid && (
        <>
          <p aria-live="polite" className="text-sm text-stone-600">
            {plural(total, "résultat", "résultats")}
          </p>
          {items.length === 0 ? (
            <p className="text-sm text-stone-500">
              Rien à afficher pour ces filtres. Essayez une autre période ou un autre type.
            </p>
          ) : (
            <div className="flex flex-col gap-4">
              {groupByDay(items).map(([key, dayItems]) => (
                <div key={key}>
                  <h3 className="mb-1 text-sm font-semibold text-stone-800 first-letter:uppercase">
                    {groupTitle(key, now)}
                  </h3>
                  <ul className="divide-y divide-stone-100">
                    {dayItems.map((item) => (
                      <li key={`${item.kind}-${String(item.id)}`} className="flex gap-3 py-2">
                        <span className="w-12 shrink-0 text-sm text-stone-500 tabular-nums">
                          {formatTime(item.occurred_at)}
                        </span>
                        <span
                          aria-hidden="true"
                          className={`mt-1.5 size-2.5 shrink-0 rounded-full ${dotClass(item)}`}
                        />
                        <div className="min-w-0 flex-1">
                          <p className="text-sm font-medium text-stone-900">
                            {itemTitle(item)}
                            {item.kind === "alert" && (
                              <span
                                className={`ml-2 text-xs font-semibold uppercase ${
                                  item.severity === "CRITICAL" ? "text-red-700" : "text-amber-800"
                                }`}
                              >
                                {item.severity === "CRITICAL" ? "Critique" : "Attention"}
                              </span>
                            )}
                          </p>
                          <p className="text-xs text-stone-500">
                            {item.kind === "event"
                              ? [
                                  item.trigger_source && TRIGGER_LABELS[item.trigger_source],
                                  item.inside_count_after !== null &&
                                    `${plural(item.inside_count_after, "poule", "poules")} dedans`,
                                ]
                                  .filter(Boolean)
                                  .join(" · ")
                              : item.acknowledged
                                ? "Lue"
                                : "Non lue"}
                          </p>
                          {item.kind === "alert" && item.image_url && token && (
                            <div className="mt-1">
                              <button
                                type="button"
                                onClick={() => {
                                  setOpenImage(openImage === item.id ? null : item.id);
                                }}
                                className="text-sm font-medium text-amber-800 underline underline-offset-2"
                              >
                                {openImage === item.id ? "Masquer la photo" : "Voir la photo"}
                              </button>
                              {openImage === item.id && (
                                <img
                                  src={api.alertImageUrl(token, coopId, item.id)}
                                  alt={`Photo prise lors de l'alerte « ${itemTitle(item)} »`}
                                  className="mt-2 max-h-72 rounded-lg object-contain"
                                />
                              )}
                            </div>
                          )}
                        </div>
                      </li>
                    ))}
                  </ul>
                </div>
              ))}
            </div>
          )}
          {remaining > 0 && (
            <button
              type="button"
              disabled={loadingMore}
              onClick={() => void loadMore()}
              className="self-start rounded-lg px-4 py-2 text-sm font-medium text-amber-800 ring-1 ring-amber-300 hover:bg-amber-50 disabled:opacity-60"
            >
              {loadingMore
                ? "Chargement…"
                : `Charger plus (${plural(remaining, "restant", "restants")})`}
            </button>
          )}
        </>
      )}
    </section>
  );
}
