"use client";

import { useCallback, useEffect, useState } from "react";
import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { CalendarClock, FileSpreadsheet, FolderOpen, Layers, Loader2, RotateCw, Settings2, Trash2, Upload } from "lucide-react";
import { toast } from "sonner";
import { api, ApiError, type Dataset } from "@/lib/api";
import { forgetSession } from "@/lib/last-session";
import { formatBytes, formatDate, formatInteger } from "@/lib/format";
import { useSettings } from "@/lib/use-preferences";
import { cn } from "@/lib/utils";
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
  AlertDialogTrigger,
} from "@/components/ui/alert-dialog";
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";

export function WorkspaceView() {
  const settings = useSettings();
  const created = useSearchParams().get("created");
  const [datasets, setDatasets] = useState<Dataset[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [deleting, setDeleting] = useState<string | null>(null);

  const load = useCallback(() => {
    setError(null);
    api
      .datasets()
      .then(setDatasets)
      .catch((e: unknown) => setError(e instanceof ApiError ? e.message : "Could not load your datasets."));
  }, []);
  useEffect(load, [load]);

  const fmt = (iso: string) =>
    settings ? formatDate(new Date(iso), settings.preferences.display_timezone, settings.preferences.date_display) : "…";

  async function remove(ds: Dataset) {
    setDeleting(ds.id);
    try {
      await api.deleteDataset(ds.id);
      ds.sessions.forEach((s) => forgetSession(s.id));
      setDatasets((list) => list?.filter((d) => d.id !== ds.id) ?? null);
      toast.success(`Deleted ${ds.original_filename}`);
    } catch (e) {
      toast.error(e instanceof ApiError ? e.message : "Could not delete the dataset.");
    } finally {
      setDeleting(null);
    }
  }

  if (error)
    return (
      <Alert variant="destructive">
        <AlertTitle>Could not load the workspace</AlertTitle>
        <AlertDescription className="space-y-3">
          <p>{error}</p>
          <Button variant="outline" size="sm" onClick={load}>
            <RotateCw /> Try again
          </Button>
        </AlertDescription>
      </Alert>
    );

  if (datasets === null)
    return (
      <div className="space-y-3" aria-busy="true" aria-label="Loading datasets">
        <Skeleton className="h-28 rounded-xl" />
        <Skeleton className="h-28 rounded-xl" />
      </div>
    );

  if (datasets.length === 0)
    return (
      <Card className="items-center py-14 text-center" data-testid="workspace-empty">
        <span className="grid size-14 place-items-center rounded-full bg-accent text-primary">
          <FolderOpen className="size-7" aria-hidden />
        </span>
        <div className="space-y-1 px-6">
          <h2 className="text-lg font-semibold">No datasets yet</h2>
          <p className="text-muted-foreground">Upload an Excel or CSV file to start your first analysis.</p>
        </div>
        <Button asChild>
          <Link href="/upload">
            <Upload /> Upload a spreadsheet
          </Link>
        </Button>
      </Card>
    );

  return (
    <ul className="space-y-3" aria-label="Datasets">
      {datasets.map((ds) => (
        <li key={ds.id}>
          <Card className={cn("gap-3", ds.sessions.some((s) => s.id === created) && "ring-2 ring-primary")} data-testid="dataset-card">
            <CardContent className="flex flex-col gap-4 sm:flex-row sm:items-start">
              <FileSpreadsheet className="hidden size-9 shrink-0 text-primary sm:block" aria-hidden />
              <div className="min-w-0 flex-1 space-y-2">
                <div className="flex flex-wrap items-center gap-2">
                  <h2 className="font-semibold break-all">{ds.original_filename}</h2>
                  <Badge variant="outline">{ds.file_type.toUpperCase()}</Badge>
                  <span className="text-sm text-muted-foreground">{formatBytes(ds.file_size)}</span>
                </div>
                <p className="flex flex-wrap gap-x-4 gap-y-1 text-sm text-muted-foreground">
                  <span>Uploaded {fmt(ds.uploaded_at)}</span>
                  <span className="inline-flex items-center gap-1">
                    <CalendarClock className="size-3.5" aria-hidden /> Deleted automatically on {fmt(ds.expires_at)}
                  </span>
                </p>
                {ds.sessions.length === 0 ? (
                  <p className="text-sm">
                    <Badge variant="warning">Setup not finished</Badge>{" "}
                    <span className="text-muted-foreground">Choose a worksheet to start the analysis.</span>
                  </p>
                ) : (
                  <ul className="space-y-1.5" aria-label="Analysis sessions">
                    {ds.sessions.map((s) => {
                      const sheet = ds.sheets.find((sh) => sh.index === s.sheet_index);
                      return (
                        <li key={s.id} className="flex flex-wrap items-center gap-2 text-sm">
                          <Layers className="size-4 text-teal" aria-hidden />
                          <span className="font-medium">{s.sheet_name}</span>
                          {sheet && (
                            <span className="text-muted-foreground">
                              {formatInteger(sheet.rows)} row{sheet.rows === 1 ? "" : "s"} × {formatInteger(sheet.columns)} column
                              {sheet.columns === 1 ? "" : "s"} · header on row {s.header_row + 1}
                            </span>
                          )}
                          <Button asChild size="sm" className="ml-auto sm:ml-2">
                            <Link href={`/s/${s.id}/health`}>Open</Link>
                          </Button>
                        </li>
                      );
                    })}
                  </ul>
                )}
              </div>
              <div className="flex shrink-0 gap-2">
                <Button asChild variant="outline" size="sm">
                  <Link href={`/upload?dataset=${ds.id}`}>
                    <Settings2 /> {ds.sessions.length ? "Analyse another sheet" : "Continue setup"}
                  </Link>
                </Button>
                <AlertDialog>
                  <AlertDialogTrigger asChild>
                    <Button variant="ghost" size="icon" aria-label={`Delete ${ds.original_filename}`} disabled={deleting === ds.id}>
                      {deleting === ds.id ? <Loader2 className="animate-spin" /> : <Trash2 />}
                    </Button>
                  </AlertDialogTrigger>
                  <AlertDialogContent>
                    <AlertDialogHeader>
                      <AlertDialogTitle>Delete {ds.original_filename}?</AlertDialogTitle>
                      <AlertDialogDescription>
                        The uploaded file and {ds.sessions.length === 1 ? "its analysis session" : `all ${ds.sessions.length} analysis sessions`} will
                        be permanently deleted. This cannot be undone.
                      </AlertDialogDescription>
                    </AlertDialogHeader>
                    <AlertDialogFooter>
                      <AlertDialogCancel>Cancel</AlertDialogCancel>
                      <AlertDialogAction destructive onClick={() => remove(ds)}>
                        Delete
                      </AlertDialogAction>
                    </AlertDialogFooter>
                  </AlertDialogContent>
                </AlertDialog>
              </div>
            </CardContent>
          </Card>
        </li>
      ))}
    </ul>
  );
}
