"use client";

import { FileSpreadsheet, Table2 } from "lucide-react";
import type { AnalysisSession } from "@/lib/api";
import { formatBytes, formatDate, formatInteger } from "@/lib/format";
import { useSettings } from "@/lib/use-preferences";
import { Badge } from "@/components/ui/badge";

export function SessionHeader({ session }: { session: AnalysisSession }) {
  const settings = useSettings();
  const expires = settings
    ? formatDate(new Date(session.expires_at), settings.preferences.display_timezone, settings.preferences.date_display)
    : "…";
  return (
    <div className="mb-6 flex flex-col gap-2 rounded-xl border bg-card px-4 py-3 text-sm sm:flex-row sm:flex-wrap sm:items-center sm:gap-x-5">
      <span className="flex min-w-0 items-center gap-2 font-medium">
        <FileSpreadsheet className="size-4 shrink-0 text-primary" aria-hidden />
        <span className="truncate" data-testid="session-file">{session.original_filename}</span>
      </span>
      <span className="flex items-center gap-2">
        <Table2 className="size-4 text-teal" aria-hidden />
        {session.sheet_name}
      </span>
      <span className="text-muted-foreground">
        {formatInteger(session.rows ?? 0)} rows × {formatInteger(session.columns ?? 0)} columns · {formatBytes(session.file_size)}
      </span>
      <span className="text-muted-foreground sm:ml-auto">Deleted automatically on {expires}</span>
      <Badge variant="secondary">{session.version === 0 ? "Original data" : `Cleaned · v${session.version}`}</Badge>
    </div>
  );
}
