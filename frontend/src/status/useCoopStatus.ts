import { useEffect, useState } from "react";

import { api, type CoopStatus } from "../api/client";

interface CoopStatusState {
  status: CoopStatus | null;
  error: string | null;
  /** Vrai quand le flux temps réel (SSE) est connecté. */
  live: boolean;
}

/**
 * État d'un poulailler : chargé une fois (GET /status), puis tenu à jour en temps réel par
 * le flux SSE (/stream). EventSource se reconnecte tout seul si la connexion est coupée.
 */
export function useCoopStatus(coopId: string, token: string | null): CoopStatusState {
  const [status, setStatus] = useState<CoopStatus | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [live, setLive] = useState(false);

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

    const source = new EventSource(api.streamUrl(token, coopId));
    source.addEventListener("open", () => {
      setLive(true);
    });
    source.addEventListener("error", () => {
      setLive(false);
    });
    source.addEventListener("status", (event) => {
      const { data } = event as MessageEvent<string>;
      setStatus(JSON.parse(data) as CoopStatus);
      setError(null);
    });

    return () => {
      controller.abort();
      source.close();
    };
  }, [coopId, token]);

  return { status, error, live };
}
