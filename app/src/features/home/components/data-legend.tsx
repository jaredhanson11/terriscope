import { IconChartDots, IconX } from "@tabler/icons-react"

import { DOT_COLOR_STOPS } from "@/features/home/components/map/utils"
import type { LayerDataStats } from "@/features/home/components/map/config"
import type { components } from "@/lib/api/v1"

type DataFieldConfig = components["schemas"]["DataFieldConfig"]

export type LegendLayer = {
  id: number
  name: string
  /** MVT property name for the active data field, e.g. "revenue_sum" */
  field: string
  /** Stats for `field` from GET /layers (winsorized normalization driver) */
  stats: LayerDataStats[string]
  /** Layer order — 0 = zip layer (no aggregation suffix) */
  order: number
}

type DataLegendProps = {
  /** Layers that currently have dots on, in render order. */
  layers: LegendLayer[]
  /** Map-level field config used to resolve a display label for `field`. */
  dataFieldConfig: DataFieldConfig[]
  /** When true, render the open icon button instead of the panel. */
  dismissed: boolean
  onDismiss: () => void
  onRestore: () => void
  /** True when the right-side selection sheet is open — pushes the panel left
   *  to mirror the top-right hover-hierarchy box's transition. */
  shiftedLeft: boolean
}

/**
 * Float a color-bucket legend at the bottom-right of the map for every layer
 * that has data dots turned on. One column per layer, stacked. Buckets follow
 * the winsorized normalization used by the dot paint expression (lo = p5
 * unless p5 == p95, in which case it falls back to min/max).
 */
export function DataLegend({
  layers,
  dataFieldConfig,
  dismissed,
  onDismiss,
  onRestore,
  shiftedLeft,
}: DataLegendProps) {
  if (layers.length === 0) return null

  const positionClass = shiftedLeft ? "right-100" : "right-4"

  if (dismissed) {
    return (
      <button
        onClick={onRestore}
        className={`absolute bottom-4 rounded-lg border bg-background/90 p-2 shadow-md backdrop-blur-sm transition-[right] duration-200 ease-in-out hover:bg-background ${positionClass}`}
        aria-label="Show legend"
      >
        <IconChartDots className="h-4 w-4" />
      </button>
    )
  }

  return (
    <div
      className={`absolute bottom-4 rounded-lg border bg-background/90 px-3 py-2 shadow-md backdrop-blur-sm transition-[right] duration-200 ease-in-out ${positionClass}`}
    >
      <div className="mb-1.5 flex items-center justify-between gap-3">
        <span className="text-muted-foreground text-[10px] font-semibold uppercase tracking-wider">
          Legend
        </span>
        <button
          onClick={onDismiss}
          className="text-muted-foreground/60 hover:text-foreground transition-colors"
          aria-label="Hide legend"
        >
          <IconX className="h-3.5 w-3.5" />
        </button>
      </div>
      <div className="space-y-2">
        {layers.map((layer) => {
          const fieldLabel = resolveFieldLabel(
            layer.field,
            layer.order,
            dataFieldConfig,
          )
          const buckets = computeBuckets(layer.field, layer.stats)
          return (
            <div key={layer.id}>
              <div className="text-xs font-medium leading-tight">
                {layer.name}
              </div>
              <div className="text-muted-foreground mb-1 text-[10px] leading-tight">
                {fieldLabel}
              </div>
              <div className="space-y-0.5">
                {buckets.map((b, i) => (
                  <div
                    key={i}
                    className="flex items-center gap-2 text-[11px] leading-tight"
                  >
                    <span
                      className="h-3 w-3 shrink-0 rounded-sm"
                      style={{ backgroundColor: DOT_COLOR_STOPS[i] }}
                    />
                    <span className="font-mono tabular-nums">{b.label}</span>
                  </div>
                ))}
              </div>
            </div>
          )
        })}
      </div>
    </div>
  )
}

/** "revenue_sum" + zip-layer flag → "Revenue (sum)" / "Revenue" */
function resolveFieldLabel(
  field: string,
  order: number,
  dataFieldConfig: DataFieldConfig[],
): string {
  // Zip layer uses the raw field name; territory layers use field_aggregation.
  if (order === 0) {
    const cfg = dataFieldConfig.find((f) => f.field === field)
    return cfg?.label || field
  }
  const cfg = dataFieldConfig.find((f) => field.startsWith(`${f.field}_`))
  if (!cfg) return field
  const agg = field.slice(cfg.field.length + 1)
  return `${cfg.label || cfg.field} (${agg})`
}

/** Five winsorized buckets matching the dot paint expression's color steps.
 *  Returns user-facing range labels formatted with K/M shorthand and a
 *  $-prefix when the field looks like a revenue/currency field. */
function computeBuckets(
  field: string,
  stats: LayerDataStats[string],
): { label: string }[] {
  const lo = stats.p5 < stats.p95 ? stats.p5 : stats.min
  const hi = stats.p5 < stats.p95 ? stats.p95 : stats.max
  const range = hi - lo

  // All-equal case: one bucket gets all the data, no thresholds to show.
  if (range <= 0) {
    return [
      { label: formatValue(lo, field) },
      { label: "—" },
      { label: "—" },
      { label: "—" },
      { label: "—" },
    ]
  }

  const t1 = lo + 0.2 * range
  const t2 = lo + 0.4 * range
  const t3 = lo + 0.6 * range
  const t4 = lo + 0.8 * range
  const fmt = (v: number) => formatValue(v, field)
  return [
    { label: `≤ ${fmt(t1)}` },
    { label: `${fmt(t1)} – ${fmt(t2)}` },
    { label: `${fmt(t2)} – ${fmt(t3)}` },
    { label: `${fmt(t3)} – ${fmt(t4)}` },
    { label: `≥ ${fmt(t4)}` },
  ]
}

/** Match the K/M abbreviation + revenue $-prefix used by the hover-hierarchy
 *  box so the legend reads consistently with the rest of the map UI. */
function formatValue(raw: number, field: string): string {
  const prefix = field.includes("revenue") ? "$" : ""
  const abs = Math.abs(raw)
  if (abs >= 1_000_000) return `${prefix}${(raw / 1_000_000).toFixed(1)}M`
  if (abs >= 10_000) return `${prefix}${(raw / 1_000).toFixed(0)}K`
  if (abs >= 1_000) return `${prefix}${(raw / 1_000).toFixed(1)}K`
  return `${prefix}${raw.toFixed(0)}`
}
