/** Mise en forme de l'état du système pour l'affichage. */

export const LOW_BATTERY = 20;

export type Tone = "ok" | "warning" | "danger" | "unknown";

export function formatLastSeen(lastSeen: string | null, now: Date): string {
  if (!lastSeen) {
    return "jamais";
  }
  const date = new Date(lastSeen);
  const minutes = Math.floor((now.getTime() - date.getTime()) / 60_000);
  if (minutes < 1) {
    return "à l'instant";
  }
  if (minutes < 60) {
    return `il y a ${String(minutes)} min`;
  }
  const hours = Math.floor(minutes / 60);
  if (hours < 24) {
    return `il y a ${String(hours)} h`;
  }
  const day = date.toLocaleDateString("fr-BE", { day: "2-digit", month: "2-digit" });
  const time = date.toLocaleTimeString("fr-BE", { hour: "2-digit", minute: "2-digit" });
  return `le ${day} à ${time}`;
}

export function batteryTone(battery: number | null): Tone {
  if (battery === null) {
    return "unknown";
  }
  if (battery < LOW_BATTERY) {
    return "danger";
  }
  if (battery < 40) {
    return "warning";
  }
  return "ok";
}

export function cameraState(cameraOk: boolean | null): { label: string; tone: Tone } {
  if (cameraOk === null) {
    return { label: "Inconnue", tone: "unknown" };
  }
  return cameraOk ? { label: "OK", tone: "ok" } : { label: "En panne", tone: "danger" };
}
