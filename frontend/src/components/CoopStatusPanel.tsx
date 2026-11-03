import { useAuth } from "../auth/useAuth";
import { useCoopStatus } from "../status/useCoopStatus";
import { useNow } from "../status/useNow";
import { SystemStatusCard } from "./SystemStatusCard";

export function CoopStatusPanel({ coopId }: { coopId: string }) {
  const { token } = useAuth();
  const { status, error, live } = useCoopStatus(coopId, token);
  const now = useNow();

  if (error && !status) {
    return <p className="mt-3 text-sm text-red-700">{error}</p>;
  }
  if (!status) {
    return <p className="mt-3 text-sm text-stone-500">Chargement de l'état…</p>;
  }
  return <SystemStatusCard status={status} now={now} live={live} />;
}
