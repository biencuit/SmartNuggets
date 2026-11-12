import { useEffect, useRef, useState } from "react";

import { api, type CoopAlert, type CoopEvent, type CoopStatus } from "../api/client";

interface CoopStatusState {
  status: CoopStatus | null;
  error: string | null;
  /** Vrai quand le flux temps réel (SSE) est connecté. */
  live: boolean;
}

/** Réactions facultatives aux autres messages du flux (passages, porte, alertes). */
export interface StreamHandlers {
  onEvent?: (event: CoopEvent) => void;
  onAlert?: (alert: CoopAlert) => void;
}

/** Le serveur envoie un `ping` toutes les 15 s : 40 s sans rien, la connexion est morte. */
export const STREAM_SILENCE_MS = 40_000;
/** Premier délai avant de rouvrir un flux abandonné ; il double à chaque échec, jusqu'à 1 min. */
export const STREAM_RETRY_MS = 5_000;
const STREAM_RETRY_MAX_MS = 60_000;

/**
 * État d'un poulailler : chargé une fois (GET /status), puis tenu à jour en temps réel par
 * le flux SSE (/stream), qui renvoie l'état complet à chaque (re)connexion.
 * Un seul flux par poulailler : le tableau de bord y écoute aussi les événements et alertes.
 */
export function useCoopStatus(
  coopId: string,
  token: string | null,
  handlers: StreamHandlers = {},
): CoopStatusState {
  const [status, setStatus] = useState<CoopStatus | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [live, setLive] = useState(false);
  // Les gestionnaires changent à chaque rendu : on garde le dernier sans rouvrir le flux.
  const handlersRef = useRef(handlers);
  useEffect(() => {
    handlersRef.current = handlers;
  });

  useEffect(() => {
    if (!token) {
      return;
    }
    const controller = new AbortController();
    void (async () => {
      try {
        const initial = await api.getStatus(token, coopId);
        if (!controller.signal.aborted) {
          // Le flux a pu envoyer un état plus récent entre-temps : on le garde.
          setStatus((current) => current ?? initial);
        }
      } catch (err) {
        if (!controller.signal.aborted) {
          setError(err instanceof Error ? err.message : "Erreur inconnue");
        }
      }
    })();

    // EventSource se reconnecte tout seul après une coupure réseau. Mais il abandonne si le
    // serveur répond par une erreur (502 de nginx pendant un déploiement), et il ne voit pas
    // une connexion restée ouverte qui ne reçoit plus rien. Dans ces deux cas, on rouvre
    // nous-mêmes le flux : le serveur renvoie alors l'état actuel dès la connexion.
    const url = api.streamUrl(token, coopId);
    let source: EventSource | null = null;
    let watchdog: ReturnType<typeof setTimeout> | undefined;
    let retry: ReturnType<typeof setTimeout> | undefined;
    let retryDelay = STREAM_RETRY_MS;
    let stopped = false;

    function reopen(delay: number) {
      if (stopped) {
        return;
      }
      source?.close();
      setLive(false);
      clearTimeout(watchdog);
      clearTimeout(retry);
      if (delay > 0) {
        retry = setTimeout(connect, delay);
      } else {
        connect();
      }
    }

    function alive() {
      clearTimeout(watchdog);
      watchdog = setTimeout(() => {
        reopen(0);
      }, STREAM_SILENCE_MS);
    }

    function connect() {
      const stream = new EventSource(url);
      source = stream;
      alive();
      stream.addEventListener("open", () => {
        retryDelay = STREAM_RETRY_MS;
        setLive(true);
        alive();
      });
      stream.addEventListener("error", () => {
        setLive(false);
        if (stream.readyState === EventSource.CLOSED) {
          reopen(retryDelay);
          retryDelay = Math.min(retryDelay * 2, STREAM_RETRY_MAX_MS);
        }
      });
      stream.addEventListener("ping", alive);
      stream.addEventListener("status", (event) => {
        alive();
        const { data } = event as MessageEvent<string>;
        setStatus(JSON.parse(data) as CoopStatus);
        setError(null);
      });
      stream.addEventListener("event", (event) => {
        alive();
        const { data } = event as MessageEvent<string>;
        handlersRef.current.onEvent?.(JSON.parse(data) as CoopEvent);
      });
      stream.addEventListener("alert", (event) => {
        alive();
        const { data } = event as MessageEvent<string>;
        handlersRef.current.onAlert?.(JSON.parse(data) as CoopAlert);
      });
    }

    connect();

    return () => {
      stopped = true;
      controller.abort();
      clearTimeout(watchdog);
      clearTimeout(retry);
      source?.close();
    };
  }, [coopId, token]);

  return { status, error, live };
}
