import type { CoopStatus } from "../api/client";
import { batteryTone, cameraState, formatLastSeen, LOW_BATTERY, type Tone } from "../status/format";

const TONE_CLASSES: Record<Tone, string> = {
  ok: "bg-emerald-500",
  warning: "bg-amber-500",
  danger: "bg-red-600",
  unknown: "bg-stone-300",
};

function Indicator({
  label,
  value,
  tone,
  detail,
}: {
  label: string;
  value: string;
  tone: Tone;
  detail?: string;
}) {
  return (
    <div className="rounded-xl bg-stone-50 p-3">
      <dt className="text-xs tracking-wide text-stone-500 uppercase">{label}</dt>
      <dd className="mt-1 flex items-center justify-center gap-2 font-semibold text-stone-900">
        <span aria-hidden="true" className={`h-2.5 w-2.5 rounded-full ${TONE_CLASSES[tone]}`} />
        {value}
      </dd>
      {detail && <dd className="mt-1 text-xs text-stone-500">{detail}</dd>}
    </div>
  );
}

/** Santé du dispositif : connexion, batterie, caméra (issue #28). */
export function SystemStatusCard({
  status,
  now,
  live,
}: {
  status: CoopStatus;
  now: Date;
  live: boolean;
}) {
  const lastSeen = formatLastSeen(status.last_seen_at, now);
  const camera = cameraState(status.camera_ok);
  const lowBattery = status.battery !== null && status.battery < LOW_BATTERY;

  return (
    <section
      aria-label="État du système"
      className="mt-3 rounded-xl border border-stone-200 p-3 text-center"
    >
      <div className="mb-3 flex items-center justify-between text-left">
        <h2 className="text-sm font-semibold text-stone-700">État du système</h2>
        {live && <span className="text-xs text-emerald-700">● en direct</span>}
      </div>

      {!status.online && (
        <p role="alert" className="mb-3 rounded-lg bg-red-50 p-3 text-left text-sm text-red-800">
          Le poulailler ne répond plus (dernière communication : {lastSeen}). Vérifiez le câble
          réseau et l'alimentation du Raspberry Pi.
        </p>
      )}

      <dl className="grid grid-cols-1 gap-2 sm:grid-cols-3">
        <Indicator
          label="Connexion"
          value={status.online ? "Connecté" : "Hors ligne"}
          tone={status.online ? "ok" : "danger"}
          detail={`Dernière communication : ${lastSeen}`}
        />
        <Indicator
          label="Batterie"
          value={status.battery === null ? "Inconnue" : `${String(status.battery)} %`}
          tone={batteryTone(status.battery)}
          detail={lowBattery ? "À recharger" : undefined}
        />
        <Indicator label="Caméra" value={camera.label} tone={camera.tone} />
      </dl>
    </section>
  );
}
