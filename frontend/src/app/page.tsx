"use client";
import { useEffect, useState } from "react";
import Link from "next/link";
import { BarChart3, Brush, ChevronRight, FileDown, Sparkles, Trash2 } from "lucide-react";
import { api, type Dataset, type Job } from "@/lib/api";
import { fmt, fmtDate } from "@/lib/utils";
import { UploadDropzone } from "@/components/upload-dropzone";
import { JobList } from "@/components/job-list";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { Alert } from "@/components/ui/alert";

const STEPS = [
  { icon: Brush, title: "Clean", text: "Duplicates, unreadable dates, unit strings, negative or missing readings — found and counted for you." },
  { icon: BarChart3, title: "Analyse", text: "Daily, monthly and hourly patterns, peak-hour share, always-on load, unusual days." },
  { icon: Sparkles, title: "Explain", text: "Plain-language findings. Optional AI only restates verified numbers." },
  { icon: FileDown, title: "Export", text: "An Excel workbook with charts and cleaned data, or a PDF report." },
];

export default function Home() {
  const [datasets, setDatasets] = useState<Dataset[] | null>(null);
  const [jobs, setJobs] = useState<Job[]>([]);
  const [error, setError] = useState<string | null>(null);

  async function load() {
    try {
      const [d, j] = await Promise.all([api.datasets(), api.jobs()]);
      setDatasets(d);
      setJobs(j);
      setError(null);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Could not reach the API");
      setDatasets([]);
    }
  }
  useEffect(() => { load(); }, []);

  async function remove(id: string) {
    if (!confirm("Delete this dataset and its history?")) return;
    await api.remove(id);
    load();
  }

  return (
    <div className="space-y-8">
      <section className="grid gap-6 lg:grid-cols-[1.1fr_1fr] lg:items-center">
        <div className="space-y-3">
          <h1 className="text-3xl font-bold tracking-tight sm:text-4xl">See where your electricity goes.</h1>
          <p className="max-w-xl text-muted-foreground">
            Upload meter readings or bills. Bijli Smart cleans the file, computes your usage patterns and shows
            what you could save — every number comes straight from your data.
          </p>
        </div>
        <UploadDropzone />
      </section>

      <section className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
        {STEPS.map((s, i) => (
          <div key={s.title} className="rounded-xl border bg-card p-4">
            <div className="flex items-center gap-2 text-sm font-semibold">
              <span className="grid h-6 w-6 place-items-center rounded-md bg-secondary text-xs text-secondary-foreground">{i + 1}</span>
              <s.icon className="h-4 w-4 text-primary" /> {s.title}
            </div>
            <p className="mt-2 text-sm text-muted-foreground">{s.text}</p>
          </div>
        ))}
      </section>

      {error && <Alert variant="destructive">API unavailable: {error}. Start the backend on port 8000.</Alert>}

      <section className="grid gap-6 lg:grid-cols-[2fr_1fr]">
        <Card>
          <CardHeader>
            <CardTitle>Your datasets</CardTitle>
            <CardDescription>Uploaded files and their cleaning status.</CardDescription>
          </CardHeader>
          <CardContent className="space-y-2">
            {datasets === null ? (
              <>
                <Skeleton className="h-16" />
                <Skeleton className="h-16" />
              </>
            ) : datasets.length === 0 ? (
              <p className="text-sm text-muted-foreground">
                Nothing uploaded yet. Try one of the files in <code className="rounded bg-muted px-1">sample-data/</code>.
              </p>
            ) : (
              datasets.map((d) => (
                <div key={d.id} className="group flex items-center gap-3 rounded-lg border p-3 hover:bg-muted/40">
                  <Link href={`/datasets/${d.id}`} className="flex min-w-0 flex-1 items-center gap-3">
                    <div className="min-w-0 flex-1">
                      <div className="flex flex-wrap items-center gap-2">
                        <span className="truncate font-medium">{d.name}</span>
                        <Badge variant={d.status === "cleaned" ? "success" : "secondary"}>
                          {d.status === "cleaned" ? "Cleaned" : "Needs cleaning"}
                        </Badge>
                      </div>
                      <div className="mt-0.5 text-xs text-muted-foreground">
                        {d.original_filename} · {fmt(d.rows_raw)} rows
                        {d.rows_clean !== null && ` → ${fmt(d.rows_clean)} clean`} · {fmtDate(d.created_at, true)}
                      </div>
                    </div>
                    <ChevronRight className="h-4 w-4 text-muted-foreground" />
                  </Link>
                  <Button variant="ghost" size="icon" aria-label="Delete dataset" onClick={() => remove(d.id)}>
                    <Trash2 className="text-muted-foreground" />
                  </Button>
                </div>
              ))
            )}
          </CardContent>
        </Card>
        <Card>
          <CardHeader>
            <CardTitle>Recent activity</CardTitle>
            <CardDescription>Job history across all datasets.</CardDescription>
          </CardHeader>
          <CardContent>
            <JobList jobs={jobs.slice(0, 10)} />
          </CardContent>
        </Card>
      </section>
    </div>
  );
}
