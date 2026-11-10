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
  /** MISSING_HEN : nombre de poules encore dehors à la fermeture du soir. */
  missing_count?: number | null;
  acknowledged: boolean;
  /** ISO 8601, UTC. */
  created_at: string;
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
  /** Réglages du poulailler : pour l'instant le nombre total de poules (US-COMPT-3). */
  updateCoop: (token: string, coopId: string, changes: { total_hens: number }) =>
    apiFetch<Coop>(`/coops/${encodeURIComponent(coopId)}`, {
      method: "PATCH",
      token,
      json: changes,
    }),
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
