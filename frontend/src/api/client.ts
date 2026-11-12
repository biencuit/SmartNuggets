/** Accès à l'API SmartNuggets (FastAPI). En développement, Vite relaie /api vers le port 8000. */

export const API_BASE = "/api/v1";

export class ApiError extends Error {
  readonly status: number;

  constructor(status: number, message: string) {
    super(message);
    this.name = "ApiError";
    this.status = status;
  }
}

export interface User {
  id: string;
  email: string;
  created_at: string;
}

export interface Token {
  access_token: string;
  token_type: string;
}

export interface Coop {
  id: string;
  name: string;
  total_hens: number;
}

/** Ajout d'un poulailler : il faut aussi le code d'appairage du Raspberry Pi. */
export interface CoopCreate extends Coop {
  claim_code: string;
}

export type DoorState = "OPEN" | "CLOSED" | "OPENING" | "CLOSING" | "ERROR";

export interface CoopStatus {
  coop_id: string;
  name: string;
  door_state: DoorState;
  inside_count: number;
  total_hens: number;
  outside_count: number;
  /** Niveau de batterie en %, null si inconnu. */
  battery: number | null;
  auto_close_time: string | null;
  /** Dernier message reçu du Raspberry Pi (ISO 8601, UTC). */
  last_seen_at: string | null;
  online: boolean;
  camera_ok: boolean | null;
}

export type EventType = "HEN_ENTRY" | "HEN_EXIT" | "DOOR_OPEN" | "DOOR_CLOSE" | "OBSTACLE";

export type TriggerSource = "AI_AUTO" | "MANUAL_APP" | "SCHEDULE" | "FAILSAFE";

/** Passage d'une poule ou mouvement de la porte (`GET /events`, flux `event`). */
export interface CoopEvent {
  id: number;
  event_type: EventType;
  trigger_source: TriggerSource | null;
  inside_count_after: number | null;
  ai_confidence: number | null;
  /** ISO 8601, UTC. */
  occurred_at: string;
}

export type AlertType =
  "PREDATOR_DETECTED" | "MISSING_HEN" | "DOOR_BLOCKED" | "LOW_BATTERY" | "DEVICE_OFFLINE";

export type Severity = "WARNING" | "CRITICAL";

/** Alerte du poulailler (`GET /alerts`, flux `alert`). */
export interface CoopAlert {
  id: number;
  alert_type: AlertType;
  severity: Severity;
  ai_confidence: number | null;
  image_url: string | null;
  acknowledged: boolean;
  /** ISO 8601, UTC. */
  created_at: string;
}

/** Filtres de la page Historique (#27). */
export type HistoryCategory = "entries" | "exits" | "door" | "alerts";

/** Une ligne de l'historique complet : un événement OU une alerte (`GET /history`). */
export interface HistoryItem {
  kind: "event" | "alert";
  /** Identifiant dans sa table d'origine : un événement et une alerte peuvent avoir le même. */
  id: number;
  type: EventType | AlertType;
  /** ISO 8601, UTC. */
  occurred_at: string;
  /** Événements seulement. */
  trigger_source: TriggerSource | null;
  inside_count_after: number | null;
  /** Alertes seulement. */
  severity: Severity | null;
  image_url: string | null;
  acknowledged: boolean | null;
}

export interface HistoryPage {
  /** Nombre de résultats pour ces filtres, toutes pages confondues. */
  total: number;
  items: HistoryItem[];
}

export interface HistoryQuery {
  /** Vide : tout. */
  categories: HistoryCategory[];
  /** Début (inclus) et fin (exclue), ISO 8601 ; null : pas de limite. */
  since: string | null;
  until: string | null;
  limit: number;
  offset: number;
}

/** Passages d'une journée ; heures locales « HH:MM:SS ». */
export interface HabitDay {
  /** AAAA-MM-JJ */
  day: string;
  exits: number;
  entries: number;
  first_exit: string | null;
  last_entry: string | null;
}

export interface HabitHour {
  hour: number;
  exits: number;
  entries: number;
}

/** Habitudes des poules (`GET /habits`). */
export interface Habits {
  timezone: string;
  /** Du plus ancien au plus récent, jours vides compris. */
  days: HabitDay[];
  /** 24 éléments, de 0 h à 23 h. */
  hours: HabitHour[];
  average_first_exit: string | null;
  average_last_entry: string | null;
  /** Moyenne sur les jours avec au moins un passage (`active_days`). */
  exits_per_day: number;
  active_days: number;
  total_exits: number;
  total_entries: number;
}

/** Paramètres de `GET /history`, toujours dans le même ordre (catégories répétées). */
export function historyQueryString(query: HistoryQuery): string {
  const params = new URLSearchParams();
  for (const category of query.categories) {
    params.append("category", category);
  }
  if (query.since) {
    params.set("since", query.since);
  }
  if (query.until) {
    params.set("until", query.until);
  }
  params.set("limit", String(query.limit));
  params.set("offset", String(query.offset));
  return params.toString();
}

export type CommandAction = "OPEN" | "CLOSE" | "CALIBRATE";

export interface CommandAccepted {
  command_id: string;
  coop_id: string;
  action: CommandAction;
  inside_count: number | null;
  issued_at: string;
}

interface RequestOptions {
  method?: string;
  token?: string | null;
  json?: unknown;
  form?: Record<string, string>;
}

function errorMessage(status: number, body: unknown): string {
  if (typeof body === "object" && body !== null && "detail" in body) {
    const { detail } = body;
    if (typeof detail === "string") {
      return detail;
    }
    if (Array.isArray(detail)) {
      return "Certaines informations sont invalides, vérifiez le formulaire.";
    }
  }
  if (status >= 500) {
    return "Le serveur rencontre un problème, réessayez dans quelques instants.";
  }
  return `Erreur inattendue (${String(status)})`;
}

function parseJson(text: string): unknown {
  if (!text) {
    return null;
  }
  try {
    return JSON.parse(text) as unknown;
  } catch {
    return null;
  }
}

export async function apiFetch<T>(path: string, options: RequestOptions = {}): Promise<T> {
  const headers: Record<string, string> = {};
  let body: BodyInit | undefined;
  if (options.token) {
    headers.Authorization = `Bearer ${options.token}`;
  }
  if (options.json !== undefined) {
    headers["Content-Type"] = "application/json";
    body = JSON.stringify(options.json);
  } else if (options.form) {
    body = new URLSearchParams(options.form);
  }

  let response: Response;
  try {
    response = await fetch(`${API_BASE}${path}`, {
      method: options.method ?? "GET",
      headers,
      body,
    });
  } catch {
    throw new ApiError(0, "Impossible de joindre le serveur. Vérifiez votre connexion.");
  }

  const data = parseJson(await response.text());
  if (!response.ok) {
    throw new ApiError(response.status, errorMessage(response.status, data));
  }
  return data as T;
}

export const api = {
  login: (email: string, password: string) =>
    apiFetch<Token>("/auth/login", { method: "POST", form: { username: email, password } }),
  register: (email: string, password: string) =>
    apiFetch<User>("/auth/register", { method: "POST", json: { email, password } }),
  me: (token: string) => apiFetch<User>("/auth/me", { token }),
  listCoops: (token: string) => apiFetch<Coop[]>("/coops", { token }),
  /** L'identifiant est celui du compte MQTT du Raspberry Pi (409 s'il est déjà pris). */
  createCoop: (token: string, coop: CoopCreate) =>
    apiFetch<Coop>("/coops", { method: "POST", token, json: coop }),
  getStatus: (token: string, coopId: string) =>
    apiFetch<CoopStatus>(`/coops/${encodeURIComponent(coopId)}/status`, { token }),
  /** Historique, du plus récent au plus ancien (200 éléments au maximum par appel). */
  listEvents: (token: string, coopId: string, limit = 200) =>
    apiFetch<CoopEvent[]>(`/coops/${encodeURIComponent(coopId)}/events?limit=${String(limit)}`, {
      token,
    }),
  listAlerts: (token: string, coopId: string, limit = 50) =>
    apiFetch<CoopAlert[]>(`/coops/${encodeURIComponent(coopId)}/alerts?limit=${String(limit)}`, {
      token,
    }),
  /** Historique complet (passages, porte, alertes), filtré et paginé. */
  listHistory: (token: string, coopId: string, query: HistoryQuery) =>
    apiFetch<HistoryPage>(
      `/coops/${encodeURIComponent(coopId)}/history?${historyQueryString(query)}`,
      { token },
    ),
  /** Habitudes des `days` derniers jours ; `timeZone` : fuseau IANA du navigateur. */
  getHabits: (token: string, coopId: string, days: number, timeZone: string) =>
    apiFetch<Habits>(
      `/coops/${encodeURIComponent(coopId)}/habits?days=${String(days)}&tz=${encodeURIComponent(timeZone)}`,
      { token },
    ),
  acknowledgeAlert: (token: string, coopId: string, alertId: number) =>
    apiFetch<CoopAlert>(`/coops/${encodeURIComponent(coopId)}/alerts/${String(alertId)}/ack`, {
      method: "POST",
      token,
    }),
  sendCommand: (token: string, coopId: string, action: CommandAction, insideCount?: number) =>
    apiFetch<CommandAccepted>(`/coops/${encodeURIComponent(coopId)}/command`, {
      method: "POST",
      token,
      json: insideCount === undefined ? { action } : { action, inside_count: insideCount },
    }),
  /** `<img>` ne peut pas envoyer d'en-tête : le jeton passe en paramètre. */
  alertImageUrl: (token: string, coopId: string, alertId: number) =>
    `${API_BASE}/coops/${encodeURIComponent(coopId)}/alerts/${String(alertId)}/image?token=${encodeURIComponent(token)}`,
  /** EventSource ne peut pas envoyer d'en-tête : le jeton passe en paramètre. */
  streamUrl: (token: string, coopId: string) =>
    `${API_BASE}/coops/${encodeURIComponent(coopId)}/stream?token=${encodeURIComponent(token)}`,
};
