"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { cn } from "@/lib/utils";
import { useVirtualizer } from "@tanstack/react-virtual";
import { api, ApiError, type ColumnProfile } from "@/lib/api";
import { formatInteger } from "@/lib/format";
import { TypeLabel } from "./column-type";

const PAGE = 200;
const ROW_H = 34;
const COL_W = 170;
const NUM_W = 64;

/** Virtualised, server-paged spreadsheet view. Only visible rows/columns are rendered; pages load on demand. */
export function DataGrid({
  sessionId,
  columns,
  total,
  profiles,
  view = "current",
  version = 0,
  showFlags = false,
  height = "60vh",
}: {
  sessionId: string;
  columns: string[];
  total: number;
  profiles?: ColumnProfile[];
  view?: "current" | "original";
  /** Changing the version clears cached pages (data changed). */
  version?: number;
  /** Highlight missing values, invalid dates, duplicate rows and corrected cells (with a legend). */
  showFlags?: boolean;
  height?: string;
}) {
  const scroller = useRef<HTMLDivElement>(null);
  const pages = useRef(new Map<number, { rows: (string | null)[][]; nums: number[]; cells: string[][] | null; rowFlags: string[] | null }>());
  const [active, setActive] = useState<{ r: number; c: number } | null>(null);
  const pending = useRef(new Set<number>());
  const [, setTick] = useState(0);
  const [error, setError] = useState<string | null>(null);

  const rowV = useVirtualizer({ count: total, getScrollElement: () => scroller.current, estimateSize: () => ROW_H, overscan: 12 });
  const colV = useVirtualizer({
    horizontal: true,
    count: columns.length,
    getScrollElement: () => scroller.current,
    estimateSize: () => COL_W,
    overscan: 3,
  });

  const load = useCallback(
    (page: number) => {
      if (pages.current.has(page) || pending.current.has(page)) return;
      pending.current.add(page);
      api
        .rows(sessionId, page * PAGE, PAGE, view, showFlags)
        .then((res) => {
          pages.current.set(page, { rows: res.rows, nums: res.row_numbers, cells: res.cell_flags, rowFlags: res.row_flags });
          setTick((t) => t + 1);
        })
        .catch((e: unknown) => setError(e instanceof ApiError ? e.message : "Could not load rows."))
        .finally(() => pending.current.delete(page));
    },
    [sessionId, view, showFlags],
  );

  // When the data changes (a cleaning step, undo, reset) drop cached pages and reload what is on screen.
  const [epoch, setEpoch] = useState(0);
  useEffect(() => {
    pages.current.clear();
    pending.current.clear();
    setEpoch((e) => e + 1);
  }, [version, view]);

  const items = rowV.getVirtualItems();
  const first = items[0]?.index ?? 0;
  const last = items[items.length - 1]?.index ?? 0;
  useEffect(() => {
    for (let p = Math.floor(first / PAGE); p <= Math.floor(last / PAGE); p++) load(p);
  }, [first, last, load, epoch]);

  const cell = (r: number, c: number) => pages.current.get(Math.floor(r / PAGE))?.rows[r % PAGE]?.[c];
  const rowNumber = (r: number) => pages.current.get(Math.floor(r / PAGE))?.nums[r % PAGE];
  const flag = (r: number, c: number) => pages.current.get(Math.floor(r / PAGE))?.cells?.[r % PAGE]?.[c] ?? "";
  const isDup = (r: number) => pages.current.get(Math.floor(r / PAGE))?.rowFlags?.[r % PAGE] === "d";

  // Keyboard navigation: arrows move the active cell; the grid scrolls to keep it visible.
  const onKeyDown = (e: React.KeyboardEvent) => {
    const cur = active ?? { r: 0, c: 0 };
    const visible = Math.max(1, Math.floor((scroller.current?.clientHeight ?? 400) / ROW_H) - 2);
    const moves: Record<string, { r: number; c: number }> = {
      ArrowDown: { r: cur.r + 1, c: cur.c },
      ArrowUp: { r: cur.r - 1, c: cur.c },
      ArrowRight: { r: cur.r, c: cur.c + 1 },
      ArrowLeft: { r: cur.r, c: cur.c - 1 },
      PageDown: { r: cur.r + visible, c: cur.c },
      PageUp: { r: cur.r - visible, c: cur.c },
      Home: e.ctrlKey ? { r: 0, c: 0 } : { r: cur.r, c: 0 },
      End: e.ctrlKey ? { r: total - 1, c: columns.length - 1 } : { r: cur.r, c: columns.length - 1 },
    };
    const next = moves[e.key];
    if (!next) return;
    e.preventDefault();
    const r = Math.min(total - 1, Math.max(0, next.r));
    const c = Math.min(columns.length - 1, Math.max(0, next.c));
    setActive({ r, c });
    rowV.scrollToIndex(r, { align: "auto" });
    colV.scrollToIndex(c, { align: "auto" });
  };
  const activeValue = active ? cell(active.r, active.c) : undefined;
  const describe = (f: string, dup: boolean) =>
    [f.includes("m") && "missing value", f.includes("i") && "invalid date", f.includes("c") && "corrected", dup && "duplicate row"]
      .filter(Boolean)
      .join(", ");
  const types = new Map(profiles?.map((p) => [p.name, p]));
  const width = NUM_W + colV.getTotalSize();

  if (error) return <p className="text-sm text-destructive-text">{error}</p>;
  if (total === 0) return <p className="text-sm text-muted-foreground">This sheet has no data rows below the header.</p>;

  return (
    <div className="space-y-2">
      <div
        ref={scroller}
        className="relative min-h-80 overflow-auto rounded-lg border bg-card text-sm outline-none focus-visible:ring-2 focus-visible:ring-ring"
        style={{ height: `min(${height}, ${Math.max(rowV.getTotalSize(), ROW_H * 4) + ROW_H * 1.6 + 18}px)` }}
        onKeyDown={onKeyDown}
        onFocus={() => setActive((a) => a ?? { r: first, c: 0 })}
        role="grid"
        aria-rowcount={total + 1}
        aria-colcount={columns.length + 1}
        aria-label={view === "original" ? "Original data" : "Data preview"}
        tabIndex={0}
        data-testid="data-grid"
      >
        <div style={{ width, height: rowV.getTotalSize() + ROW_H * 1.6 }} className="relative">
          {/* header */}
          <div className="sticky top-0 z-20 flex border-b bg-muted" style={{ width, height: ROW_H * 1.6 }} role="row">
            <div className="sticky left-0 z-30 shrink-0 border-r bg-muted" style={{ width: NUM_W }} role="columnheader" aria-label="Row number" />
            <div className="relative" style={{ width: colV.getTotalSize() }}>
              {colV.getVirtualItems().map((c) => {
                const p = types.get(columns[c.index]);
                return (
                  <div
                    key={c.key}
                    role="columnheader"
                    className="absolute top-0 flex h-full flex-col justify-center border-r px-2"
                    style={{ left: c.start, width: c.size }}
                    title={columns[c.index]}
                  >
                    <span className="truncate text-xs font-semibold text-foreground">{columns[c.index]}</span>
                    {p && <TypeLabel type={p.type} mixed={p.mixed} />}
                  </div>
                );
              })}
            </div>
          </div>
          {/* body */}
          {items.map((r) => (
            <div
              key={r.key}
              role="row"
              aria-rowindex={r.index + 2}
              className="absolute left-0 flex border-b"
              style={{ top: r.start + ROW_H * 1.6, height: r.size, width }}
            >
              <div
                role="rowheader"
                className={cn(
                  "sticky left-0 z-10 flex shrink-0 items-center justify-end gap-1 border-r bg-muted px-2 text-xs text-muted-foreground tabular-nums",
                  isDup(r.index) && "border-l-[3px] border-l-violet",
                )}
                style={{ width: NUM_W }}
                title={isDup(r.index) ? "Exact duplicate of another row" : undefined}
              >
                {isDup(r.index) && <span className="rounded bg-violet/20 px-1 text-[9px] font-bold text-violet-text">DUP</span>}
                {rowNumber(r.index) ?? ""}
              </div>
              <div className="relative" style={{ width: colV.getTotalSize() }}>
                {colV.getVirtualItems().map((c) => {
                  const v = cell(r.index, c.index);
                  const f = flag(r.index, c.index);
                  const isActive = active?.r === r.index && active?.c === c.index;
                  const note = describe(f, false);
                  return (
                    <div
                      key={c.key}
                      role="gridcell"
                      aria-selected={isActive}
                      data-flags={f || undefined}
                      onClick={() => setActive({ r: r.index, c: c.index })}
                      className={cn(
                        "absolute top-0 flex h-full items-center gap-1 truncate border-r px-2 font-mono text-xs whitespace-pre",
                        f.includes("m") && "bg-warning/10",
                        f.includes("i") && "bg-destructive/10",
                        f.includes("c") && !f.includes("m") && "bg-success/10",
                        isActive && "z-[5] ring-2 ring-ring ring-inset",
                      )}
                      style={{ left: c.start, width: c.size }}
                      title={[v ?? "", note].filter(Boolean).join(" · ")}
                    >
                      {f.includes("i") && <span className="size-1.5 shrink-0 rotate-45 bg-destructive" aria-hidden />}
                      {f.includes("m") && <span className="size-1.5 shrink-0 rounded-full border border-warning" aria-hidden />}
                      {f.includes("c") && <span className="size-1.5 shrink-0 rounded-full bg-success" aria-hidden />}
                      {v === undefined ? <span className="h-3 w-16 animate-pulse rounded bg-muted" /> : v === null ? <span className="text-muted-foreground/60">·</span> : v}
                    </div>
                  );
                })}
              </div>
            </div>
          ))}
        </div>
      </div>
      <p className="sr-only" aria-live="polite" data-testid="grid-active">
        {active
          ? `Row ${rowNumber(active.r) ?? ""}, ${columns[active.c]}: ${activeValue ?? "empty"}${
              describe(flag(active.r, active.c), isDup(active.r)) ? ` (${describe(flag(active.r, active.c), isDup(active.r))})` : ""
            }`
          : ""}
      </p>
      {showFlags && (
        <ul className="flex flex-wrap gap-x-4 gap-y-1 text-xs text-muted-foreground" aria-label="Cell markers" data-testid="grid-legend">
          <li className="inline-flex items-center gap-1.5">
            <span className="size-2 rounded-full border border-warning" /> Missing value
          </li>
          <li className="inline-flex items-center gap-1.5">
            <span className="size-2 rotate-45 bg-destructive" /> Invalid date
          </li>
          <li className="inline-flex items-center gap-1.5">
            <span className="rounded bg-violet/20 px-1 text-[9px] font-bold text-violet-text">DUP</span> Duplicate row
          </li>
          <li className="inline-flex items-center gap-1.5">
            <span className="size-2 rounded-full bg-success" /> Corrected by cleaning
          </li>
        </ul>
      )}
      <p className="text-xs text-muted-foreground">
        {formatInteger(total)} rows × {formatInteger(columns.length)} columns. Row numbers are the rows of your original
        sheet. Empty cells show as ·. Rows load as you scroll; use the arrow keys to move between cells.
      </p>
    </div>
  );
}
