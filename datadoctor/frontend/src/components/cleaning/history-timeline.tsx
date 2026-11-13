"use client";

import { RotateCcw, ShieldCheck, Undo2, Wand2 } from "lucide-react";
import type { Timeline, TimelineEvent } from "@/lib/api";
import { formatDateTime, formatInteger } from "@/lib/format";
import { useSettings } from "@/lib/use-preferences";
import { Badge } from "@/components/ui/badge";

type OpRef = { sequence_number: number; title: string };

function describe(e: TimelineEvent): { icon: typeof Wand2; title: string; body?: string } {
  const d = e.details as Record<string, unknown>;
  if (e.type === "apply")
    return {
      icon: Wand2,
      title: `Applied #${d.sequence_number}: ${d.title ?? d.operation_type}`,
      body: `${d.summary ?? ""}`,
    };
  if (e.type === "undo") {
    const op = (d.operations as OpRef[] | undefined)?.[0];
    return { icon: Undo2, title: `Undid #${op?.sequence_number}: ${op?.title ?? ""}` };
  }
  if (e.type === "reset") {
    const n = (d.operations as OpRef[] | undefined)?.length ?? 0;
    return { icon: RotateCcw, title: `Reset to original (${formatInteger(n)} change${n === 1 ? "" : "s"} undone)` };
  }
  if (e.type === "sensitive_columns") {
    const added = (d.added as string[]) ?? [];
    const removed = (d.removed as string[]) ?? [];
    return {
      icon: ShieldCheck,
      title: "Sensitive columns changed",
      body: [added.length ? `Marked: ${added.join(", ")}` : "", removed.length ? `Unmarked: ${removed.join(", ")}` : ""]
        .filter(Boolean)
        .join(" · "),
    };
  }
  if (e.type === "export") {
    const kind = d.type === "pdf" ? "PDF report" : "Excel workbook";
    return { icon: Wand2, title: d.status === "done" ? `Exported: ${kind}` : `Export failed: ${kind}` };
  }
  return { icon: Wand2, title: e.type };
}

/** Audit trail, oldest first. Undone steps stay visible: nothing is ever deleted from the history. */
export function HistoryTimeline({ timeline }: { timeline: Timeline }) {
  const settings = useSettings();
  const prefs = settings?.preferences;
  if (timeline.events.length === 0)
    return <p className="text-sm text-muted-foreground">No changes yet. The current data is identical to the original.</p>;
  const status = new Map(timeline.operations.map((o) => [o.sequence_number, o.status]));
  return (
    <ol className="relative space-y-4 border-l pl-6" data-testid="timeline">
      {timeline.events.map((e) => {
        const { icon: Icon, title, body } = describe(e);
        const seq = (e.details as { sequence_number?: number }).sequence_number;
        const undone = e.type === "apply" && seq !== undefined && status.get(seq) === "undone";
        return (
          <li key={e.id} className="relative">
            <span className="absolute top-0.5 -left-[33px] grid size-6 place-items-center rounded-full border bg-card">
              <Icon className="size-3.5 text-primary" aria-hidden />
            </span>
            <div className="flex flex-wrap items-baseline gap-2 text-sm">
              <span className={undone ? "text-muted-foreground line-through" : "font-medium"}>{title}</span>
              {undone && <Badge variant="secondary">Undone</Badge>}
              <span className="ml-auto text-xs text-muted-foreground">
                {prefs ? formatDateTime(new Date(e.created_at), prefs.display_timezone, prefs.date_display) : ""}
              </span>
            </div>
            {body && <p className="mt-0.5 text-sm text-muted-foreground">{body}</p>}
          </li>
        );
      })}
    </ol>
  );
}
