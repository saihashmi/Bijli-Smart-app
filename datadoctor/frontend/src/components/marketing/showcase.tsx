"use client";

import { useState } from "react";
import Image from "next/image";
import { cn } from "@/lib/utils";

const SCREENS = [
  {
    id: "health",
    tab: "Data Health",
    title: "See what is wrong, with exact counts",
    text: "A score with its formula and breakdown, every issue counted, and the affected rows one click away.",
    alt: "Data Health Center showing a health score gauge with its four components, tiles for rows, missing values, duplicate rows and inconsistent formats, and issues grouped by severity.",
  },
  {
    id: "cleaning",
    tab: "Cleaning",
    title: "Preview every fix before it is applied",
    text: "Each change is shown on your full data first, recorded in a history, and can be undone. The original file is never touched.",
    alt: "Cleaning Studio with a list of cleaning tools, a preview of converting text amounts to numbers, and the data grid with problem cells marked.",
  },
  {
    id: "dashboard",
    tab: "Dashboard",
    title: "Charts chosen from your column types",
    text: "An automatic first dashboard with the reason for each chart, then filters, drill-down and your own widgets.",
    alt: "Dashboard Studio in a dark theme with KPI cards, a monthly line chart, a bar chart by channel and a donut chart by product, each with a note about rows left out.",
  },
  {
    id: "analyst",
    tab: "AI Analyst",
    title: "Ask in plain language, get a calculated answer",
    text: "The answer, the chart and the exact calculation used are shown together, so you can check how the question was understood.",
    alt: "AI Analyst answering which region has the highest total amount, with a computed result, a bar chart, and the calculation settings listed underneath.",
  },
  {
    id: "export",
    tab: "Export",
    title: "Take the cleaned data and a report with you",
    text: "An Excel workbook with an audit log and a PDF report, built from the same figures the app shows.",
    alt: "Export Center with cards for an Excel workbook and a PDF report and a list of finished exports ready to download.",
  },
] as const;

/** Real screens of the product (captured by scripts/capture-showcase.mjs), not illustrations. */
export function Showcase() {
  const [active, setActive] = useState(0);
  const screen = SCREENS[active];

  const onKey = (e: React.KeyboardEvent) => {
    const step = e.key === "ArrowRight" ? 1 : e.key === "ArrowLeft" ? -1 : 0;
    if (!step) return;
    e.preventDefault();
    const next = (active + step + SCREENS.length) % SCREENS.length;
    setActive(next);
    document.getElementById(`showcase-tab-${SCREENS[next].id}`)?.focus();
  };

  return (
    <div className="space-y-6" data-testid="showcase">
      <div role="tablist" aria-label="Product screens" className="mx-auto flex w-fit max-w-full flex-wrap justify-center gap-1 rounded-xl border border-white/10 bg-white/[0.04] p-1" onKeyDown={onKey}>
        {SCREENS.map((s, i) => (
          <button
            key={s.id}
            id={`showcase-tab-${s.id}`}
            type="button"
            role="tab"
            aria-selected={i === active}
            aria-controls="showcase-panel"
            tabIndex={i === active ? 0 : -1}
            onClick={() => setActive(i)}
            className={cn(
              "cursor-pointer rounded-lg px-3.5 py-1.5 text-sm font-medium text-slate-300 transition-colors outline-none hover:text-white focus-visible:ring-2 focus-visible:ring-cyan",
              i === active && "bg-white/10 text-white",
            )}
          >
            {s.tab}
          </button>
        ))}
      </div>

      <div id="showcase-panel" role="tabpanel" aria-labelledby={`showcase-tab-${screen.id}`} className="space-y-5">
        <div className="mx-auto max-w-2xl text-center">
          <h3 className="text-xl font-semibold text-white">{screen.title}</h3>
          <p className="mt-1.5 text-slate-300">{screen.text}</p>
        </div>
        <figure className="hairline overflow-hidden rounded-2xl bg-[#080D1B] shadow-[0_30px_80px_-30px_rgba(34,211,238,0.35)]">
          <Image
            key={screen.id}
            src={`/showcase/${screen.id}.jpg`}
            alt={screen.alt}
            width={1440}
            height={900}
            sizes="(min-width: 1280px) 1152px, 100vw"
            className="h-auto w-full"
            priority={false}
          />
          <figcaption className="border-t border-white/10 px-4 py-2.5 text-center text-xs text-slate-400">
            A real screen of DataDoctor AI. The data shown is the bundled synthetic sales sample, not a customer&apos;s.
          </figcaption>
        </figure>
      </div>
    </div>
  );
}
