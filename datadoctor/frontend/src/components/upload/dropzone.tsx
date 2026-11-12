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
          "flex w-full cursor-pointer flex-col items-center justify-center gap-4 rounded-2xl border-2 border-dashed bg-card px-6 py-14 text-center transition-colors outline-none focus-visible:ring-[3px] focus-visible:ring-ring/50 disabled:cursor-not-allowed disabled:opacity-60",
          over ? "border-primary bg-accent" : "border-input hover:border-primary/60 hover:bg-muted/40",
        )}
      >
        <span className="grid size-14 place-items-center rounded-full bg-accent text-primary">
          <UploadCloud className="size-7" aria-hidden />
        </span>
        <span className="space-y-1">
          <span className="block text-lg font-semibold">Drop your spreadsheet here</span>
          <span className="block text-muted-foreground">
            or <span className="font-medium text-link underline underline-offset-4">browse your computer</span>
          </span>
        </span>
        <span id="dropzone-help" className="flex flex-wrap items-center justify-center gap-x-3 gap-y-1 text-xs text-muted-foreground">
          <span className="inline-flex items-center gap-1">
            <FileSpreadsheet className="size-3.5" aria-hidden /> .xlsx · .xlsm · .xls · .csv
          </span>
          <span>Up to {maxMb ?? "…"} MB</span>
          <span>Macros and formulas are never run</span>
        </span>
      </button>
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
