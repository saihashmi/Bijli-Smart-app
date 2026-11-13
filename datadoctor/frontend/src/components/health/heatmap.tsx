import type { Profile } from "@/lib/api";
import { formatInteger } from "@/lib/format";

/** Missing-value heatmap: one row per column, one cell per block of consecutive data rows. */
export function MissingHeatmap({ map, totalRows }: { map: NonNullable<Profile["missing_map"]>; totalRows: number }) {
  if (!map.buckets || map.columns.length === 0) return <p className="text-sm text-muted-foreground">No data rows to map.</p>;
  const anyMissing = map.values.some((row) => row.some((v) => v > 0));
  const summary = map.columns
    .map((c, i) => ({ c, share: map.values[i].reduce((a, b) => a + b, 0) / map.buckets }))
    .filter((x) => x.share > 0)
    .sort((a, b) => b.share - a.share)
    .slice(0, 3)
    .map((x) => `${x.c} (${Math.round(x.share * 100)}%)`)
    .join(", ");

  return (
    <figure data-testid="missing-heatmap">
      <div
        role="img"
        aria-label={anyMissing ? `Missing-value map. Most affected columns: ${summary}.` : "Missing-value map: no missing values."}
        className="max-h-80 overflow-auto"
      >
        <div className="grid min-w-[28rem] items-center gap-x-3 gap-y-1" style={{ gridTemplateColumns: "minmax(5rem, 10rem) 1fr" }}>
          {map.columns.map((col, i) => (
            <div key={col} className="contents">
              <span className="truncate text-xs font-medium" title={col}>
                {col}
              </span>
              <div className="grid h-4 gap-px" style={{ gridTemplateColumns: `repeat(${map.buckets}, minmax(0, 1fr))` }}>
                {map.values[i].map((v, b) => {
                  const from = b * map.bucket_rows + 1;
                  const to = Math.min(totalRows, (b + 1) * map.bucket_rows);
                  return (
                    <span
                      key={b}
                      title={`${col} · rows ${formatInteger(from)}–${formatInteger(to)}: ${Math.round(v * 100)}% missing`}
                      className="rounded-[2px]"
                      style={{
                        background:
                          v === 0
                            ? "var(--muted)"
                            : `color-mix(in srgb, ${v > 0.5 ? "var(--destructive)" : "var(--warning)"} ${Math.round(30 + v * 70)}%, var(--muted))`,
                      }}
                    />
                  );
                })}
              </div>
            </div>
          ))}
        </div>
      </div>
      <figcaption className="mt-3 flex flex-wrap items-center gap-x-4 gap-y-1 text-xs text-muted-foreground">
        <span>Left to right: first to last row ({formatInteger(map.bucket_rows)} row{map.bucket_rows === 1 ? "" : "s"} per block).</span>
        <span className="inline-flex items-center gap-1.5">
          <span className="size-2.5 rounded-[2px] bg-muted" /> none
          <span className="ml-2 size-2.5 rounded-[2px] bg-warning" /> some missing
          <span className="ml-2 size-2.5 rounded-[2px] bg-destructive" /> mostly missing
        </span>
      </figcaption>
    </figure>
  );
}
