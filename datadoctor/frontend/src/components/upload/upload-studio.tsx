"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import { AlertTriangle, ArrowRight, FileSpreadsheet, Info, Loader2, RotateCcw, X } from "lucide-react";
import { toast } from "sonner";
import { api, ApiError, uploadFile, type Dataset, type Peek } from "@/lib/api";
import { formatBytes, formatDate, precheckFile } from "@/lib/format";
import { useSettings } from "@/lib/use-preferences";
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Progress } from "@/components/ui/progress";
import { Skeleton } from "@/components/ui/skeleton";
import { Dropzone } from "./dropzone";
import { HeaderRowPreview } from "./header-row-preview";
import { SheetPicker } from "./sheet-picker";

type Phase =
  | { kind: "pick" }
  | { kind: "uploading"; file: File; loaded: number; total: number }
  | { kind: "processing"; file: File }
  | { kind: "ready"; dataset: Dataset };

const TYPE_LABEL: Record<string, string> = { xlsx: "Excel workbook", xls: "Excel 97–2003 workbook", csv: "CSV file" };

export function UploadStudio() {
  const router = useRouter();
  const params = useSearchParams();
  const settings = useSettings();
  const [phase, setPhase] = useState<Phase>({ kind: "pick" });
  const [error, setError] = useState<{ title: string; message: string } | null>(null);
  const [sheet, setSheet] = useState<number | null>(null);
  const [headerRow, setHeaderRow] = useState(0);
  const [peek, setPeek] = useState<Peek | null>(null);
  const [peekError, setPeekError] = useState<string | null>(null);
  const [starting, setStarting] = useState(false);
  const abort = useRef<AbortController | null>(null);
  const loadedId = useRef<string | null>(null);
  const maxMb = settings?.system.max_upload_mb ?? null;
  const prefs = settings?.preferences;

  const showDataset = useCallback((ds: Dataset) => {
    loadedId.current = ds.id;
    setPhase({ kind: "ready", dataset: ds });
    const first = ds.sheets.find((s) => s.selectable && s.visibility === "visible") ?? ds.sheets.find((s) => s.selectable);
    setSheet(first ? first.index : null);
    setHeaderRow(0);
  }, []);

  // Resume an earlier upload: /upload?dataset=<id>
  const resumeId = params.get("dataset");
  useEffect(() => {
    // Skip when the dataset is already on screen (e.g. right after uploading) so upload-time warnings stay visible.
    if (!resumeId || loadedId.current === resumeId) return;
    api
      .dataset(resumeId)
      .then(showDataset)
      .catch((e: unknown) => setError({ title: "Could not open that upload", message: e instanceof ApiError ? e.message : "Unknown error." }));
  }, [resumeId, showDataset]);

  // Load the raw first rows whenever the chosen sheet changes.
  const datasetId = phase.kind === "ready" ? phase.dataset.id : null;
  useEffect(() => {
    if (!datasetId || sheet === null) return;
    let alive = true;
    setPeek(null);
    setPeekError(null);
    api
      .peek(datasetId, sheet, 15)
      .then((p) => alive && setPeek(p))
      .catch((e: unknown) => alive && setPeekError(e instanceof ApiError ? e.message : "Could not read the sheet."));
    return () => {
      alive = false;
    };
  }, [datasetId, sheet]);

  async function handleFile(file: File) {
    setError(null);
    const problem = precheckFile(file, maxMb ?? 20);
    if (problem) {
      setError({ title: "This file can't be uploaded", message: problem });
      return;
    }
    abort.current = new AbortController();
    setPhase({ kind: "uploading", file, loaded: 0, total: file.size });
    try {
      const ds = await uploadFile(
        file,
        (loaded, total) =>
          setPhase(loaded >= total ? { kind: "processing", file } : { kind: "uploading", file, loaded, total }),
        abort.current.signal,
      );
      showDataset(ds);
      router.replace(`/upload?dataset=${ds.id}`, { scroll: false });
      toast.success(`${ds.original_filename} uploaded`);
    } catch (e) {
      setPhase({ kind: "pick" });
      if (e instanceof ApiError && e.code === "ABORTED") return;
      setError({ title: "Upload failed", message: e instanceof ApiError ? e.message : "Unknown error." });
    }
  }

  async function start(ds: Dataset) {
    if (sheet === null) return;
    setStarting(true);
    try {
      const sess = await api.createSession(ds.id, sheet, headerRow);
      toast.success(`Analysis session created for “${sess.sheet_name}”`);
      router.push(`/workspace?created=${sess.id}`);
    } catch (e) {
      toast.error(e instanceof ApiError ? e.message : "Could not start the analysis.");
      setStarting(false);
    }
  }

  function reset() {
    loadedId.current = null;
    setPhase({ kind: "pick" });
    setError(null);
    setPeek(null);
    router.replace("/upload", { scroll: false });
  }

  return (
    <div className="space-y-6">
      {error && (
        <Alert variant="destructive">
          <AlertTriangle aria-hidden />
          <AlertTitle>{error.title}</AlertTitle>
          <AlertDescription>{error.message}</AlertDescription>
        </Alert>
      )}

      {phase.kind === "pick" && <Dropzone maxMb={maxMb} onFile={handleFile} />}

      {(phase.kind === "uploading" || phase.kind === "processing") && (
        <Card aria-live="polite">
          <CardContent className="space-y-4 py-2">
            <div className="flex items-center gap-3">
              <FileSpreadsheet className="size-8 shrink-0 text-primary" aria-hidden />
              <div className="min-w-0 flex-1">
                <p className="truncate font-medium">{phase.file.name}</p>
                <p className="text-sm text-muted-foreground">
                  {phase.kind === "uploading"
                    ? `Uploading… ${formatBytes(phase.loaded)} of ${formatBytes(phase.total)}`
                    : "Checking the file and reading its worksheets…"}
                </p>
              </div>
              {phase.kind === "uploading" && (
                <Button variant="ghost" size="sm" onClick={() => abort.current?.abort()}>
                  <X /> Cancel
                </Button>
              )}
              {phase.kind === "processing" && <Loader2 className="size-5 animate-spin text-primary" aria-hidden />}
            </div>
            <Progress
              aria-label="Upload progress"
              value={phase.kind === "uploading" ? Math.round((phase.loaded / Math.max(1, phase.total)) * 100) : 100}
            />
          </CardContent>
        </Card>
      )}

      {phase.kind === "ready" && (
        <div className="grid gap-6 xl:grid-cols-[minmax(0,22rem)_minmax(0,1fr)]">
          <div className="space-y-6">
            <Card>
              <CardHeader>
                <CardTitle className="flex items-center gap-2 break-all">
                  <FileSpreadsheet className="size-5 shrink-0 text-primary" aria-hidden />
                  {phase.dataset.original_filename}
                </CardTitle>
                <CardDescription>
                  {TYPE_LABEL[phase.dataset.file_type]} · {formatBytes(phase.dataset.file_size)}
                </CardDescription>
              </CardHeader>
              <CardContent className="space-y-3 text-sm">
                {phase.dataset.csv && (
                  <p>
                    Read as <Badge variant="secondary">{phase.dataset.csv.encoding.toUpperCase()}</Badge> text,{" "}
                    <Badge variant="secondary">{phase.dataset.csv.delimiter_label}</Badge>-separated.
                  </p>
                )}
                {prefs && (
                  <p className="text-muted-foreground">
                    Stored until {formatDate(new Date(phase.dataset.expires_at), prefs.display_timezone, prefs.date_display)}, then
                    deleted automatically.
                  </p>
                )}
                {phase.dataset.warnings.map((w) => (
                  <Alert key={w} variant="warning">
                    <Info aria-hidden />
                    <AlertDescription>{w}</AlertDescription>
                  </Alert>
                ))}
                <Button variant="outline" size="sm" onClick={reset}>
                  <RotateCcw /> Upload a different file
                </Button>
              </CardContent>
            </Card>

            <Card>
              <CardHeader>
                <CardTitle>1. Choose a {phase.dataset.file_type === "csv" ? "table" : "worksheet"}</CardTitle>
                <CardDescription>
                  {phase.dataset.sheets.length} {phase.dataset.sheets.length === 1 ? "table" : "sheets"} found, including hidden ones.
                </CardDescription>
              </CardHeader>
              <CardContent>
                <SheetPicker
                  sheets={phase.dataset.sheets}
                  value={sheet}
                  onChange={(i) => {
                    setSheet(i);
                    setHeaderRow(0);
                  }}
                />
              </CardContent>
            </Card>
          </div>

          <Card className="min-w-0">
            <CardHeader>
              <CardTitle>2. Check the first rows and pick the header row</CardTitle>
              <CardDescription>Values are shown exactly as stored in the file. Nothing has been cleaned or converted yet.</CardDescription>
            </CardHeader>
            <CardContent className="space-y-5">
              {sheet === null && <p className="text-sm text-muted-foreground">No worksheet in this file has data that can be analysed.</p>}
              {sheet !== null && peekError && (
                <Alert variant="destructive">
                  <AlertTriangle aria-hidden />
                  <AlertDescription>{peekError}</AlertDescription>
                </Alert>
              )}
              {sheet !== null && !peek && !peekError && <Skeleton className="h-64" />}
              {peek && <HeaderRowPreview peek={peek} headerRow={headerRow} onHeaderRow={setHeaderRow} />}
              <div className="flex flex-wrap items-center gap-3 border-t pt-5">
                <Button size="lg" disabled={sheet === null || !peek || starting} onClick={() => start(phase.dataset)}>
                  {starting ? <Loader2 className="animate-spin" /> : <ArrowRight />} Start analysis
                </Button>
                <span className="text-sm text-muted-foreground">Creates an analysis session. Your original file stays unchanged.</span>
              </div>
            </CardContent>
          </Card>
        </div>
      )}

      {phase.kind === "pick" && resumeId && !error && <Skeleton className="h-40" />}
    </div>
  );
}
