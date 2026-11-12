"use client";

import { useState } from "react";
import { AlertTriangle, ChevronsLeftRight } from "lucide-react";
import { cn } from "@/lib/utils";

type Cell = { v: string; issue?: string };
type Row = { messy: Cell[]; clean: string[]; removed?: boolean };

const HEADERS = ["Invoice", "Date", "City", "Amount (PKR)", "Status"];

// Synthetic example data, written for this illustration. Not real records.
const ROWS: Row[] = [
  { messy: [{ v: "INV-1001" }, { v: "25/03/2026" }, { v: "Lahore" }, { v: "Rs 1,250", issue: "Number stored as text" }, { v: "Paid" }], clean: ["INV-1001", "2026-03-25", "Lahore", "1,250", "Paid"] },
  { messy: [{ v: "INV-1002" }, { v: "03/04/2026", issue: "Ambiguous date" }, { v: " lahore", issue: "Extra space, different capitals" }, { v: "(250)", issue: "Brackets mean negative" }, { v: "paid", issue: "Inconsistent label" }], clean: ["INV-1002", "2026-04-03", "Lahore", "-250", "Paid"] },
  { messy: [{ v: "INV-1002", issue: "Duplicate row" }, { v: "03/04/2026", issue: "Duplicate row" }, { v: " lahore", issue: "Duplicate row" }, { v: "(250)", issue: "Duplicate row" }, { v: "paid", issue: "Duplicate row" }], clean: ["", "", "", "", ""], removed: true },
  { messy: [{ v: "INV-1003" }, { v: "2026-04-05" }, { v: "KARACHI", issue: "Different capitals" }, { v: "N/A", issue: "Placeholder, not a value" }, { v: "Pending" }], clean: ["INV-1003", "2026-04-05", "Karachi", "", "Pending"] },
  { messy: [{ v: "INV-1004" }, { v: "12-Jan-2026", issue: "Different date format" }, { v: "Karachi" }, { v: "4,200.50", issue: "Number stored as text" }, { v: "Paid " , issue: "Trailing space" }], clean: ["INV-1004", "2026-01-12", "Karachi", "4,200.5", "Paid"] },
  { messy: [{ v: "INV-1005" }, { v: "31/02/2026", issue: "Impossible date" }, { v: "Islamabad" }, { v: "900" }, { v: "Refunded" }], clean: ["INV-1005", "", "Islamabad", "900", "Refunded"] },
];

function Grid({ side }: { side: "messy" | "clean" }) {
  return (
    <table className="w-full min-w-[34rem] border-collapse text-left text-[13px]">
      <thead>
        <tr className="text-xs text-slate-400">
          {HEADERS.map((h) => (
            <th key={h} scope="col" className="border-b border-white/10 px-3 py-2 font-medium whitespace-nowrap">
              {h}
            </th>
          ))}
        </tr>
      </thead>
      <tbody className="font-mono">
        {ROWS.map((row, r) => {
          if (side === "clean" && row.removed)
            return (
              <tr key={r}>
                <td colSpan={5} className="border-b border-white/5 px-3 py-2 text-xs text-slate-500 italic">
                  duplicate row removed
                </td>
              </tr>
            );
          return (
            <tr key={r}>
              {HEADERS.map((_, c) => {
                const messy = row.messy[c];
                const value = side === "messy" ? messy.v : row.clean[c];
                const fixed = side === "clean" && (messy.issue || row.clean[c] !== messy.v);
                return (
                  <td
                    key={c}
                    title={side === "messy" ? messy.issue : undefined}
                    className={cn(
                      "border-b border-white/5 px-3 py-2 whitespace-pre",
                      side === "messy" && messy.issue && "bg-amber-400/10 text-amber-200",
                      side === "messy" && messy.issue?.includes("Impossible") && "bg-red-400/15 text-red-200",
                      side === "messy" && !messy.issue && "text-slate-300",
                      side === "clean" && (fixed ? "text-teal-200" : "text-slate-300"),
                    )}
                  >
                    {value === "" ? <span className="text-slate-600">empty</span> : value}
                  </td>
                );
              })}
            </tr>
          );
        })}
      </tbody>
    </table>
  );
}

/** Draggable before/after comparison. A native range input drives it, so arrow keys and screen readers work. */
export function CompareSlider() {
  const [pos, setPos] = useState(55);
  return (
    <figure className="hairline overflow-hidden rounded-2xl bg-[#0B1222] shadow-lg">
      <figcaption className="flex flex-wrap items-center justify-between gap-2 border-b border-white/10 px-4 py-3 text-sm">
        <span className="flex items-center gap-4">
          <span className="flex items-center gap-1.5 text-amber-200">
            <AlertTriangle className="size-3.5" aria-hidden /> Before: as uploaded
          </span>
          <span className="text-teal-200">After: cleaned</span>
        </span>
        <span className="rounded-md bg-white/5 px-2 py-0.5 text-xs text-slate-300">Synthetic example data</span>
      </figcaption>
      <div className="relative overflow-x-auto">
        <div className="relative min-w-[34rem]" data-testid="compare-slider" style={{ "--pos": `${pos}%` } as React.CSSProperties}>
          <div aria-hidden={pos > 97}>
            <Grid side="clean" />
          </div>
          <div className="absolute inset-0 bg-[#0B1222]" style={{ clipPath: `inset(0 ${100 - pos}% 0 0)` }} aria-hidden={pos < 3}>
            <Grid side="messy" />
          </div>
          <div className="pointer-events-none absolute inset-y-0 w-px bg-cyan" style={{ left: `${pos}%` }} aria-hidden>
            <span className="absolute top-1/2 left-1/2 grid size-9 -translate-x-1/2 -translate-y-1/2 place-items-center rounded-full border border-cyan/60 bg-[#0B1222] text-cyan shadow-glow">
              <ChevronsLeftRight className="size-4" />
            </span>
          </div>
          <input
            type="range"
            min={0}
            max={100}
            value={pos}
            onChange={(e) => setPos(Number(e.target.value))}
            aria-label="Before and after comparison. Move left to see more of the cleaned data, right to see more of the original."
            aria-valuetext={`${pos}% original, ${100 - pos}% cleaned`}
            className="absolute inset-0 size-full cursor-ew-resize opacity-0"
          />
        </div>
      </div>
    </figure>
  );
}
