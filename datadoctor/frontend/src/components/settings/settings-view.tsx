"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import { Bot, Clock, Database, Loader2, RotateCw, Trash2 } from "lucide-react";
import { toast } from "sonner";
import { api, ApiError, type DateDisplay, type Preferences, type SettingsResponse } from "@/lib/api";
import { formatDateTime, formatInteger, timeZoneOptions } from "@/lib/format";
import { BackendStatus } from "@/components/backend-status";
import { LocalModeBadge } from "@/components/layout/local-mode-badge";
import { ThemeSwitcher } from "@/components/theme-switcher";
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
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Label } from "@/components/ui/label";
import { NativeSelect } from "@/components/ui/native-select";
import { Skeleton } from "@/components/ui/skeleton";
import { Switch } from "@/components/ui/switch";

const DATE_FORMATS: DateDisplay[] = ["DD/MM/YYYY", "MM/DD/YYYY", "YYYY-MM-DD"];

function Row({ label, value }: { label: string; value: React.ReactNode }) {
  return (
    <div className="flex justify-between gap-4 border-b py-2 text-sm last:border-0">
      <dt className="text-muted-foreground">{label}</dt>
      <dd className="text-right font-medium">{value}</dd>
    </div>
  );
}

export function SettingsView() {
  const [data, setData] = useState<SettingsResponse | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [saving, setSaving] = useState<keyof Preferences | null>(null);
  const [deleting, setDeleting] = useState(false);

  const load = useCallback(() => {
    setError(null);
    api
      .settings()
      .then(setData)
      .catch((e: unknown) => setError(e instanceof ApiError ? e.message : "Could not load settings."));
  }, []);
  useEffect(load, [load]);

  async function save<K extends keyof Preferences>(key: K, value: Preferences[K]) {
    if (!data) return;
    const previous = data;
    setData({ ...data, preferences: { ...data.preferences, [key]: value } }); // optimistic
    setSaving(key);
    try {
      setData(await api.updateSettings({ [key]: value } as Partial<Preferences>));
      toast.success("Setting saved");
    } catch (e) {
      setData(previous);
      toast.error(e instanceof ApiError ? e.message : "Could not save the setting.");
    } finally {
      setSaving(null);
    }
  }

  async function deleteAll() {
    setDeleting(true);
    try {
      const res = await api.deleteAllData();
      toast.success(
        res.datasets_deleted === 0
          ? "There was no stored data to delete."
          : `Deleted ${res.datasets_deleted} dataset${res.datasets_deleted === 1 ? "" : "s"} and their files.`,
      );
    } catch (e) {
      toast.error(e instanceof ApiError ? e.message : "Could not delete data.");
    } finally {
      setDeleting(false);
    }
  }

  const zones = useMemo(() => timeZoneOptions(data?.preferences.display_timezone), [data?.preferences.display_timezone]);
  const now = useMemo(() => new Date(), []);

  return (
    <div className="grid gap-6 lg:grid-cols-2">
      <Card>
        <CardHeader>
          <CardTitle>Appearance</CardTitle>
          <CardDescription>Choose a theme or follow your device setting. Saved in this browser.</CardDescription>
        </CardHeader>
        <CardContent>
          <ThemeSwitcher />
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>System status</CardTitle>
          <CardDescription>Live check of the DataDoctor server.</CardDescription>
        </CardHeader>
        <CardContent className="text-sm">
          <BackendStatus />
        </CardContent>
      </Card>

      {error && (
        <Card className="lg:col-span-2" role="alert">
          <CardHeader>
            <CardTitle className="text-destructive-text">Settings could not be loaded</CardTitle>
            <CardDescription>{error}</CardDescription>
          </CardHeader>
          <CardContent>
            <Button variant="outline" onClick={load}>
              <RotateCw /> Try again
            </Button>
          </CardContent>
        </Card>
      )}

      {!data && !error && (
        <>
          <Skeleton className="h-56 rounded-xl" />
          <Skeleton className="h-56 rounded-xl" />
        </>
      )}

      {data && (
        <>
          <Card>
            <CardHeader>
              <CardTitle className="flex items-center gap-2">
                <Clock className="size-4 text-teal" aria-hidden /> Dates and time
              </CardTitle>
              <CardDescription>Used for dates shown in the app and the timestamps on exported reports.</CardDescription>
            </CardHeader>
            <CardContent className="space-y-5">
              <div className="space-y-2">
                <Label htmlFor="tz">Display time zone</Label>
                <NativeSelect
                  id="tz"
                  value={data.preferences.display_timezone}
                  disabled={saving === "display_timezone"}
                  onChange={(e) => save("display_timezone", e.target.value)}
                >
                  {zones.map((z) => (
                    <option key={z} value={z}>
                      {z.replaceAll("_", " ")}
                    </option>
                  ))}
                </NativeSelect>
              </div>
              <div className="space-y-2">
                <Label htmlFor="date-display">Date display format</Label>
                <NativeSelect
                  id="date-display"
                  value={data.preferences.date_display}
                  disabled={saving === "date_display"}
                  onChange={(e) => save("date_display", e.target.value as DateDisplay)}
                >
                  {DATE_FORMATS.map((f) => (
                    <option key={f} value={f}>
                      {f}
                    </option>
                  ))}
                </NativeSelect>
                <p className="text-xs text-muted-foreground">
                  Only changes how dates are <em>shown</em>. Dates inside your files are never re-interpreted using this
                  setting.
                </p>
              </div>
              <p className="rounded-md bg-muted px-3 py-2 text-sm" data-testid="date-preview">
                Now: <span className="font-medium">{formatDateTime(now, data.preferences.display_timezone, data.preferences.date_display)}</span>
              </p>
            </CardContent>
          </Card>

          <Card>
            <CardHeader>
              <CardTitle className="flex items-center gap-2">
                <Bot className="size-4 text-teal" aria-hidden /> AI and privacy
              </CardTitle>
              <CardDescription>AI is optional. Every analysis works without it.</CardDescription>
            </CardHeader>
            <CardContent className="space-y-5">
              <div className="flex items-center gap-2 text-sm">
                AI provider:
                {data.system.ai_configured ? (
                  <Badge variant="success">
                    {data.system.ai_provider} · {data.system.ai_model}
                  </Badge>
                ) : (
                  <Badge variant="outline">Not configured</Badge>
                )}
              </div>
              {!data.system.ai_configured && (
                <p className="text-sm text-muted-foreground">
                  To enable AI explanations, set <code className="rounded bg-muted px-1">GROQ_API_KEY</code> in the
                  server&rsquo;s <code className="rounded bg-muted px-1">.env</code> file and restart it.
                </p>
              )}
              <div className="flex items-start justify-between gap-4">
                <div className="space-y-1">
                  <Label htmlFor="share-names">Share column names with AI</Label>
                  <p className="text-xs text-muted-foreground">
                    When off, columns are sent as anonymous labels (col_1, col_2…). Spreadsheet rows and cell values are
                    never sent either way.
                  </p>
                </div>
                <Switch
                  id="share-names"
                  checked={data.preferences.ai_share_column_names}
                  disabled={saving === "ai_share_column_names"}
                  onCheckedChange={(v) => save("ai_share_column_names", v)}
                />
              </div>
            </CardContent>
          </Card>

          <Card>
            <CardHeader>
              <CardTitle className="flex items-center gap-2">
                <Database className="size-4 text-teal" aria-hidden /> Data retention and limits
              </CardTitle>
              <CardDescription>Set by the server administrator in the .env file.</CardDescription>
            </CardHeader>
            <CardContent>
              <dl>
                <Row label="Uploaded files deleted after" value={`${data.system.retention_days} days`} />
                <Row label="Maximum file size" value={`${data.system.max_upload_mb} MB`} />
                <Row label="Maximum rows" value={formatInteger(data.system.max_rows)} />
                <Row label="Maximum columns" value={formatInteger(data.system.max_columns)} />
                <Row label="Maximum cells" value={formatInteger(data.system.max_cells)} />
                <Row label="Processing time limit" value={`${data.system.process_timeout_s} s per step`} />
              </dl>
            </CardContent>
          </Card>

          <Card>
            <CardHeader>
              <CardTitle className="flex items-center gap-2">
                Access mode <LocalModeBadge />
              </CardTitle>
              <CardDescription>
                DataDoctor AI runs for a single user on this computer. There are no user accounts yet, so it must not be
                hosted publicly with private data.
              </CardDescription>
            </CardHeader>
          </Card>

          <Card className="border-destructive/40">
            <CardHeader>
              <CardTitle className="text-destructive-text">Delete all my data</CardTitle>
              <CardDescription>
                Permanently removes every uploaded file, cleaned copy and export from this server for this browser.
              </CardDescription>
            </CardHeader>
            <CardContent>
              <AlertDialog>
                <AlertDialogTrigger asChild>
                  <Button variant="destructive" disabled={deleting}>
                    {deleting ? <Loader2 className="animate-spin" /> : <Trash2 />} Delete all data
                  </Button>
                </AlertDialogTrigger>
                <AlertDialogContent>
                  <AlertDialogHeader>
                    <AlertDialogTitle>Delete all data?</AlertDialogTitle>
                    <AlertDialogDescription>
                      All uploaded files, cleaned versions, histories and exports for this browser will be permanently
                      deleted. This cannot be undone.
                    </AlertDialogDescription>
                  </AlertDialogHeader>
                  <AlertDialogFooter>
                    <AlertDialogCancel>Cancel</AlertDialogCancel>
                    <AlertDialogAction destructive onClick={deleteAll}>
                      Delete everything
                    </AlertDialogAction>
                  </AlertDialogFooter>
                </AlertDialogContent>
              </AlertDialog>
            </CardContent>
          </Card>
        </>
      )}
    </div>
  );
}
