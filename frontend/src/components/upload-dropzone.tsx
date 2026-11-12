"use client";
import { useRef, useState } from "react";
import { useRouter } from "next/navigation";
import { FileSpreadsheet, Loader2, UploadCloud } from "lucide-react";
import { api } from "@/lib/api";
import { cn } from "@/lib/utils";
import { Alert } from "@/components/ui/alert";

export function UploadDropzone() {
  const router = useRouter();
  const input = useRef<HTMLInputElement>(null);
  const [drag, setDrag] = useState(false);
  const [busy, setBusy] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  async function handle(file: File | undefined) {
    if (!file) return;
    setError(null);
    setBusy(file.name);
    try {
      const ds = await api.upload(file);
      router.push(`/datasets/${ds.id}?tab=clean`);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Upload failed");
      setBusy(null);
    }
  }

  return (
    <div className="space-y-3">
      <button
        type="button"
        onClick={() => input.current?.click()}
        onDragOver={(e) => { e.preventDefault(); setDrag(true); }}
        onDragLeave={() => setDrag(false)}
        onDrop={(e) => { e.preventDefault(); setDrag(false); handle(e.dataTransfer.files?.[0]); }}
        disabled={!!busy}
        className={cn(
          "flex w-full flex-col items-center justify-center gap-3 rounded-xl border-2 border-dashed bg-card px-6 py-10 text-center transition-colors cursor-pointer",
          drag ? "border-primary bg-secondary/60" : "border-input hover:border-primary/60 hover:bg-muted/40",
        )}
      >
        {busy ? (
          <>
            <Loader2 className="h-9 w-9 animate-spin text-primary" />
            <div className="text-sm font-medium">Reading {busy}…</div>
          </>
        ) : (
          <>
            <span className="grid h-12 w-12 place-items-center rounded-full bg-secondary text-secondary-foreground">
              <UploadCloud className="h-6 w-6" />
            </span>
            <div>
              <div className="font-medium">Drop a CSV or Excel file, or click to browse</div>
              <div className="mt-1 text-sm text-muted-foreground">
                Smart-meter exports, sub-meter logs or monthly bills. Up to 25 MB.
              </div>
            </div>
            <div className="flex items-center gap-1.5 text-xs text-muted-foreground">
              <FileSpreadsheet className="h-3.5 w-3.5" /> .csv · .xlsx
            </div>
          </>
        )}
      </button>
      <input
        ref={input}
        type="file"
        accept=".csv,.txt,.xlsx,.xlsm,text/csv,application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        className="hidden"
        onChange={(e) => handle(e.target.files?.[0])}
      />
      {error && <Alert variant="destructive">{error}</Alert>}
    </div>
  );
}
