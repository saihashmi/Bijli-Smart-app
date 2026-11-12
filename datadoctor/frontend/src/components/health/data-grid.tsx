"use client";

import { useCallback, useEffect, useRef, useState } from "react";
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
}: {
  sessionId: string;
  columns: string[];
  total: number;
  profiles?: ColumnProfile[];
}) {
  const scroller = useRef<HTMLDivElement>(null);
  const pages = useRef(new Map<number, (string | null)[][]>());
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
        .rows(sessionId, page * PAGE, PAGE)
        .then((res) => {
          pages.current.set(page, res.rows);
          setTick((t) => t + 1);
        })
        .catch((e: unknown) => setError(e instanceof ApiError ? e.message : "Could not load rows."))
        .finally(() => pending.current.delete(page));
    },
    [sessionId],
  );

  const items = rowV.getVirtualItems();
  const first = items[0]?.index ?? 0;
  const last = items[items.length - 1]?.index ?? 0;
  useEffect(() => {
    for (let p = Math.floor(first / PAGE); p <= Math.floor(last / PAGE); p++) load(p);
  }, [first, last, load]);

  const cell = (r: number, c: number) => pages.current.get(Math.floor(r / PAGE))?.[r % PAGE]?.[c];
  const types = new Map(profiles?.map((p) => [p.name, p]));
  const width = NUM_W + colV.getTotalSize();

  if (error) return <p className="text-sm text-destructive-text">{error}</p>;
  if (total === 0) return <p className="text-sm text-muted-foreground">This sheet has no data rows below the header.</p>;

  return (
    <div className="space-y-2">
      <div
        ref={scroller}
        className="relative h-[60vh] min-h-80 overflow-auto rounded-lg border bg-card text-sm"
        role="grid"
        aria-rowcount={total + 1}
        aria-colcount={columns.length + 1}
        aria-label="Data preview"
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
                className="sticky left-0 z-10 flex shrink-0 items-center justify-end border-r bg-muted/80 px-2 text-xs text-muted-foreground tabular-nums"
                style={{ width: NUM_W }}
              >
                {r.index + 1}
              </div>
              <div className="relative" style={{ width: colV.getTotalSize() }}>
                {colV.getVirtualItems().map((c) => {
                  const v = cell(r.index, c.index);
                  return (
                    <div
                      key={c.key}
                      role="gridcell"
                      className="absolute top-0 flex h-full items-center truncate border-r px-2 font-mono text-xs whitespace-pre"
                      style={{ left: c.start, width: c.size }}
                      title={v ?? ""}
                    >
                      {v === undefined ? <span className="h-3 w-16 animate-pulse rounded bg-muted" /> : v === null ? <span className="text-muted-foreground/60">·</span> : v}
                    </div>
                  );
                })}
              </div>
            </div>
          ))}
        </div>
      </div>
      <p className="text-xs text-muted-foreground">
        {formatInteger(total)} rows × {formatInteger(columns.length)} columns. Values are shown exactly as stored; empty cells
        show as ·. Rows load as you scroll.
      </p>
    </div>
  );
}
