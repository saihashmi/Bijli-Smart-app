"use client";

import { useCallback, useEffect, useState } from "react";
import { Check, Download, FileSpreadsheet, FileText, Loader2, ShieldCheck, Trash2 } from "lucide-react";
import { toast } from "sonner";
import { ApiError } from "@/lib/api";
import { exportsApi, type ExportJob, type ExportType } from "@/lib/exports";
import { formatBytes, formatDateTime, formatInteger } from "@/lib/format";
import { useSettings } from "@/lib/use-preferences";
import { useAnalysisSession } from "@/components/session/session-context";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Checkbox } from "@/components/ui/checkbox";
import { EmptyState } from "@/components/ui/empty-state";
import { Skeleton } from "@/components/ui/skeleton";

const KINDS: Record<ExportType, { title: string; icon: typeof FileText; blurb: string; contents: string[] }> = {
  xlsx: {
    title: "Excel workbook",
    icon: FileSpreadsheet,
    blurb: "Your cleaned data with a full record of what was checked and changed.",
    contents: [
      "Cleaned Data: every row, with numbers and dates kept as real numbers and dates",
      "Data Quality Report: health score, its breakdown and every finding",
      "Cleaning Audit Log: each step, its settings and rows affected",
      "Summary Statistics: one line per column",
    ],
  },
  pdf: {
    title: "PDF report",
    icon: FileText,
    blurb: "A printable summary to share with people who will not open the data.",
    contents: [
      "Dataset summary and Data Health Score with its breakdown",
      "Key statistics, data-quality findings and the cleaning summary",
      "Your saved dashboard: KPI figures and bar, line and histogram charts",
      "Computed answers from the AI Analyst, labelled as calculations",
    ],
  },
};

function describe(job: ExportJob): string {
  const d = job.details;
  if (!d) return "";
  const parts: string[] = [];
  if (d.rows !== undefined) parts.push(`${formatInteger(d.rows)} rows × ${formatInteger(d.columns ?? 0)} columns`);
  if (d.pages !== undefined) parts.push(`${d.pages} ${d.pages === 1 ? "page" : "pages"}`);
  if (d.charts) parts.push(`${d.charts} ${d.charts === 1 ? "chart" : "charts"}`);
  if (d.size !== undefined) parts.push(formatBytes(d.size));
  if (d.neutralised_cells) parts.push(`${formatInteger(d.neutralised_cells)} cells made safe against formula injection`);
  return parts.join(" · ");
}

export function ExportCenter() {
  const { session } = useAnalysisSession();
  const sid = session.id;
  const preferences = useSettings()?.preferences;
  const [jobs, setJobs] = useState<ExportJob[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [creating, setCreating] = useState<ExportType | null>(null);
  const [withDashboard, setWithDashboard] = useState(true);
  const [withAnswers, setWithAnswers] = useState(true);

  const load = useCallback(
    () =>
      exportsApi
        .list(sid)
        .then((r) => {
          setJobs(r.exports);
          return r.exports;
        })
        .catch((e) => {
          setError(e instanceof ApiError ? e.message : "Exports could not be loaded.");
          return [] as ExportJob[];
        }),
    [sid],
  );
  useEffect(() => {
    void load();
  }, [load]);

  const create = async (type: ExportType) => {
    setCreating(type);
    try {
      const job = await exportsApi.create(sid, { type, include_dashboard: withDashboard, include_answers: withAnswers });
      if (job.status === "done") toast.success(`${KINDS[type].title} is ready to download.`);
      else toast.error(job.error ?? "The export could not be created.");
      await load();
    } catch (e) {
      toast.error(e instanceof ApiError ? (e.status === 429 ? "Too many exports in a short time. Please wait a minute." : e.message) : "The export could not be created.");
    } finally {
      setCreating(null);
    }
  };

  // Download links are short-lived, so a fresh one is fetched at the moment of the click.
  const download = async (jobId: string) => {
    const fresh = (await load()).find((j) => j.id === jobId);
    if (!fresh?.download_url) {
      toast.error("This file is no longer available. Create the export again.");
      return;
    }
    window.location.assign(fresh.download_url);
  };

  const remove = async (job: ExportJob) => {
    try {
      await exportsApi.remove(job.id);
      toast.success("Export deleted.");
      await load();
    } catch {
      toast.error("The export could not be deleted.");
    }
  };

  const when = (iso: string | null) => (iso && preferences ? formatDateTime(new Date(iso), preferences.display_timezone, preferences.date_display) : "");

  return (
    <div className="space-y-6" data-testid="export-center">
      <div className="grid gap-4 lg:grid-cols-2">
        {(Object.keys(KINDS) as ExportType[]).map((type) => {
          const k = KINDS[type];
          const Icon = k.icon;
          const busy = creating === type;
          return (
            <section key={type} aria-label={k.title} className="flex flex-col rounded-2xl border bg-card p-5 shadow-sm" data-testid={`export-${type}`}>
              <div className="flex items-start gap-3">
                <span className="grid size-11 shrink-0 place-items-center rounded-xl bg-accent text-primary dark:text-link">
                  <Icon className="size-5" aria-hidden />
                </span>
                <div>
                  <h2 className="text-lg font-semibold">{k.title}</h2>
                  <p className="text-sm text-muted-foreground">{k.blurb}</p>
                </div>
              </div>
              <ul className="my-4 space-y-1.5 text-sm">
                {k.contents.map((c) => (
                  <li key={c} className="flex gap-2">
                    <Check className="mt-0.5 size-4 shrink-0 text-success" aria-hidden />
                    <span>{c}</span>
                  </li>
                ))}
              </ul>
              {type === "pdf" && (
                <div className="mb-4 space-y-2 rounded-xl border p-3 text-sm">
                  <label className="flex cursor-pointer items-center gap-2">
                    <Checkbox checked={withDashboard} onCheckedChange={(v) => setWithDashboard(Boolean(v))} />
                    Include my saved dashboard
                  </label>
                  <label className="flex cursor-pointer items-center gap-2">
                    <Checkbox checked={withAnswers} onCheckedChange={(v) => setWithAnswers(Boolean(v))} />
                    Include AI Analyst answers
                  </label>
                </div>
              )}
              <Button className="mt-auto w-full sm:w-fit" onClick={() => create(type)} disabled={creating !== null}>
                {busy ? <Loader2 className="animate-spin" aria-hidden /> : <Icon aria-hidden />}
                {busy ? "Building the file from your data…" : `Create ${k.title}`}
              </Button>
            </section>
          );
        })}
      </div>

      <p className="flex items-start gap-2 rounded-2xl border bg-card px-4 py-3 text-sm text-muted-foreground">
        <ShieldCheck className="mt-0.5 size-4 shrink-0 text-success" aria-hidden />
        <span>
          Exports use the same calculations as the app, so the figures match. Your original upload is never changed. Each file carries its creation time
          in your time zone, can be downloaded only from this browser, and is deleted automatically after 24 hours.
        </span>
      </p>

      <section aria-label="Your exports" className="space-y-3">
        <h2 className="text-lg font-semibold">Your exports</h2>
        {error && (
          <p className="text-sm text-destructive-text" role="alert">
            {error}
          </p>
        )}
        {jobs === null && !error && <Skeleton className="h-20 rounded-2xl" />}
        {jobs?.length === 0 && <EmptyState icon={Download} title="No exports yet" description="Create an Excel workbook or a PDF report above. Finished files appear here." className="py-8" />}
        {jobs && jobs.length > 0 && (
          <ul className="space-y-2" data-testid="export-list">
            {jobs.map((job) => {
              const Icon = KINDS[job.type].icon;
              return (
                <li key={job.id} className="flex flex-wrap items-center gap-3 rounded-2xl border bg-card p-4" data-testid="export-job" data-status={job.status}>
                  <Icon className="size-5 shrink-0 text-muted-foreground" aria-hidden />
                  <div className="min-w-0 flex-1">
                    <p className="truncate font-medium">{job.file_name ?? KINDS[job.type].title}</p>
                    <p className="text-xs text-muted-foreground">
                      {job.status === "failed" ? (job.error ?? "The export failed.") : describe(job)}
                      {job.completed_at && <> · created {when(job.completed_at)}</>}
                    </p>
                    {job.status === "done" && job.expires_at && <p className="text-xs text-muted-foreground">Deleted automatically on {when(job.expires_at)}</p>}
                  </div>
                  {job.status === "done" && <Badge variant="secondary">Ready</Badge>}
                  {job.status === "expired" && <Badge variant="outline">Expired and deleted</Badge>}
                  {job.status === "failed" && <Badge variant="destructive">Failed</Badge>}
                  {job.status === "done" && (
                    <Button size="sm" onClick={() => download(job.id)}>
                      <Download aria-hidden />
                      Download
                    </Button>
                  )}
                  <Button variant="ghost" size="icon" aria-label={`Delete export ${job.file_name ?? ""}`} onClick={() => remove(job)}>
                    <Trash2 aria-hidden />
                  </Button>
                </li>
              );
            })}
          </ul>
        )}
      </section>
    </div>
  );
}
