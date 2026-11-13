"use client";

import { useRef, useState } from "react";
import { FileSpreadsheet, UploadCloud } from "lucide-react";
import { ACCEPTED_EXTENSIONS } from "@/lib/format";
import { cn } from "@/lib/utils";

/** Drag-and-drop zone that is also a normal keyboard-focusable button opening the file browser. */
export function Dropzone({ maxMb, onFile, disabled }: { maxMb: number | null; onFile: (f: File) => void; disabled?: boolean }) {
  const input = useRef<HTMLInputElement>(null);
  const [over, setOver] = useState(false);

  return (
    <div>
      <div className="dd-animated-border shadow-glow" data-active={over}>
        <button
          type="button"
          disabled={disabled}
          onClick={() => input.current?.click()}
          onDragOver={(e) => {
            e.preventDefault();
            setOver(true);
          }}
          onDragLeave={() => setOver(false)}
          onDrop={(e) => {
            e.preventDefault();
            setOver(false);
            const f = e.dataTransfer.files?.[0];
            if (f) onFile(f);
          }}
          aria-describedby="dropzone-help"
          className={cn(
            "dd-animated-border-inner flex w-full cursor-pointer flex-col items-center justify-center gap-5 bg-card px-6 py-16 text-center transition-colors duration-200 outline-none focus-visible:ring-[3px] focus-visible:ring-ring/60 disabled:cursor-not-allowed disabled:opacity-60",
            over ? "bg-accent" : "hover:bg-surface-2/60",
          )}
        >
          <span
            className={cn(
              "grid size-16 place-items-center rounded-2xl bg-brand-gradient text-white shadow-glow transition-transform duration-200",
              over && "scale-110",
            )}
          >
            <UploadCloud className="size-8" aria-hidden />
          </span>
          <span className="space-y-1.5">
            <span className="block text-xl font-semibold tracking-tight">Drop your spreadsheet here</span>
            <span className="block text-muted-foreground">
              or <span className="font-medium text-link underline underline-offset-4">browse your computer</span>
            </span>
          </span>
          <span id="dropzone-help" className="flex flex-wrap items-center justify-center gap-2 text-xs text-muted-foreground">
            <span className="inline-flex items-center gap-1 rounded-full border px-2.5 py-1">
              <FileSpreadsheet className="size-3.5" aria-hidden /> .xlsx · .xlsm · .xls · .csv
            </span>
            <span className="rounded-full border px-2.5 py-1">Up to {maxMb ?? "…"} MB</span>
            <span className="rounded-full border px-2.5 py-1">Macros and formulas are never run</span>
          </span>
        </button>
      </div>
      <input
        ref={input}
        type="file"
        className="sr-only"
        tabIndex={-1}
        aria-label="Choose a spreadsheet file"
        accept={ACCEPTED_EXTENSIONS.join(",")}
        data-testid="file-input"
        onChange={(e) => {
          const f = e.target.files?.[0];
          if (f) onFile(f);
          e.target.value = "";
        }}
      />
    </div>
  );
}
