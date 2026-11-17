import { useState } from "react";

import type { HabitHour } from "../api/client";
import { chartSummary, niceScale, plural } from "./format";

/**
 * Passages par heure de la journée : sorties et entrées côte à côte (SVG fait main, sans
 * bibliothèque). Couleurs vérifiées pour les daltoniens (outil de validation de palette) :
 * sorties amber-600 (#e17100), entrées emerald-700 (#007a55), écart ΔE 9,7 au pire.
 */

const WIDTH = 720;
const HEIGHT = 220;
const MARGIN = { top: 12, right: 8, bottom: 26, left: 34 };
const PLOT_W = WIDTH - MARGIN.left - MARGIN.right;
const PLOT_H = HEIGHT - MARGIN.top - MARGIN.bottom;
const SLOT = PLOT_W / 24;
const GAP = 2; // espace entre les deux barres d'une même heure
const BAR = Math.min(10, (SLOT * 0.7 - GAP) / 2);
const RADIUS = 4;

const SERIES = [
  { key: "exits", label: "Sorties", className: "fill-amber-600", swatch: "bg-amber-600" },
  { key: "entries", label: "Entrées", className: "fill-emerald-700", swatch: "bg-emerald-700" },
] as const;

/** Barre arrondie de 4 px en haut, carrée sur la ligne de base. */
function barPath(x: number, y: number, width: number, height: number): string {
  const r = Math.min(RADIUS, width / 2, height);
  const n = (value: number) => value.toFixed(2);
  return [
    `M${n(x)},${n(y + height)}`,
    `V${n(y + r)}`,
    `Q${n(x)},${n(y)} ${n(x + r)},${n(y)}`,
    `H${n(x + width - r)}`,
    `Q${n(x + width)},${n(y)} ${n(x + width)},${n(y + r)}`,
    `V${n(y + height)}Z`,
  ].join("");
}

export function HourChart({ hours }: { hours: HabitHour[] }) {
  const [active, setActive] = useState<number | null>(null);
  const max = Math.max(0, ...hours.map((h) => Math.max(h.exits, h.entries)));
  const { top, step } = niceScale(max);
  const ticks = Array.from({ length: Math.round(top / step) + 1 }, (_, i) => i * step);
  const y = (value: number) => MARGIN.top + PLOT_H - (value / top) * PLOT_H;
  const activeHour = active === null ? undefined : hours.find((h) => h.hour === active);

  return (
    <figure className="flex flex-col gap-2">
      <figcaption className="flex flex-wrap items-center justify-between gap-2">
        <span className="text-sm font-medium text-stone-800">Passages par heure</span>
        <span className="flex gap-4 text-sm text-stone-600">
          {SERIES.map((serie) => (
            <span key={serie.key} className="flex items-center gap-1.5">
              <span aria-hidden="true" className={`size-3 rounded-sm ${serie.swatch}`} />
              {serie.label}
            </span>
          ))}
        </span>
      </figcaption>

      {/* Sur téléphone, le graphique garde une largeur lisible et défile dans la carte. */}
      <div className="relative overflow-x-auto">
        <svg
          viewBox={`0 0 ${String(WIDTH)} ${String(HEIGHT)}`}
          className="h-auto w-full min-w-[36rem]"
          role="img"
          aria-label={`Passages par heure. ${chartSummary(hours)}`}
          onMouseLeave={() => {
            setActive(null);
          }}
        >
          {ticks.map((tick) => (
            <g key={tick}>
              <line
                x1={MARGIN.left}
                x2={WIDTH - MARGIN.right}
                y1={y(tick)}
                y2={y(tick)}
                className="stroke-stone-200"
                strokeWidth={1}
              />
              <text
                x={MARGIN.left - 6}
                y={y(tick)}
                textAnchor="end"
                dominantBaseline="middle"
                className="fill-stone-500 text-[11px] tabular-nums"
              >
                {tick}
              </text>
            </g>
          ))}

          {hours.map((hour) => {
            const slotX = MARGIN.left + hour.hour * SLOT;
            const groupX = slotX + (SLOT - (2 * BAR + GAP)) / 2;
            return (
              <g key={hour.hour}>
                {active === hour.hour && (
                  <rect
                    x={slotX}
                    y={MARGIN.top}
                    width={SLOT}
                    height={PLOT_H}
                    className="fill-stone-100"
                  />
                )}
                {SERIES.map((serie, index) => {
                  const value = hour[serie.key];
                  if (value === 0) return null;
                  const barY = y(value);
                  return (
                    <path
                      key={serie.key}
                      d={barPath(groupX + index * (BAR + GAP), barY, BAR, y(0) - barY)}
                      className={serie.className}
                    />
                  );
                })}
                {hour.hour % 3 === 0 && (
                  <text
                    x={slotX + SLOT / 2}
                    y={HEIGHT - 8}
                    textAnchor="middle"
                    className="fill-stone-500 text-[11px]"
                  >
                    {hour.hour} h
                  </text>
                )}
                {/* Zone de survol plus large que les barres. */}
                <rect
                  x={slotX}
                  y={MARGIN.top}
                  width={SLOT}
                  height={PLOT_H}
                  fill="transparent"
                  data-testid={`heure-${String(hour.hour)}`}
                  onMouseEnter={() => {
                    setActive(hour.hour);
                  }}
                />
              </g>
            );
          })}

          <line
            x1={MARGIN.left}
            x2={WIDTH - MARGIN.right}
            y1={y(0)}
            y2={y(0)}
            className="stroke-stone-400"
            strokeWidth={1}
          />
        </svg>

        {activeHour && (
          <div
            role="status"
            className="pointer-events-none absolute top-0 -translate-x-1/2 rounded-lg bg-stone-900 px-2.5 py-1.5 text-xs whitespace-nowrap text-white shadow"
            style={{
              left: `${String(((MARGIN.left + (activeHour.hour + 0.5) * SLOT) / WIDTH) * 100)}%`,
            }}
          >
            <span className="font-semibold">
              {activeHour.hour} h – {activeHour.hour + 1} h
            </span>{" "}
            · {plural(activeHour.exits, "sortie", "sorties")} ·{" "}
            {plural(activeHour.entries, "entrée", "entrées")}
          </div>
        )}
      </div>

      <details className="text-sm text-stone-600">
        <summary className="cursor-pointer">Voir les passages heure par heure</summary>
        <table className="mt-2 w-full max-w-sm text-left tabular-nums">
          <thead>
            <tr className="text-stone-500">
              <th className="py-1 font-medium">Heure</th>
              <th className="py-1 font-medium">Sorties</th>
              <th className="py-1 font-medium">Entrées</th>
            </tr>
          </thead>
          <tbody>
            {hours.map((hour) => (
              <tr key={hour.hour} className="border-t border-stone-100">
                <td className="py-0.5">
                  {hour.hour} h – {hour.hour + 1} h
                </td>
                <td className="py-0.5">{hour.exits}</td>
                <td className="py-0.5">{hour.entries}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </details>
    </figure>
  );
}
