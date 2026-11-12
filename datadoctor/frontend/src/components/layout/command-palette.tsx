"use client";

import { useEffect, useMemo, useRef, useState } from "react";
import { useRouter } from "next/navigation";
import { useTheme } from "next-themes";
import { CornerDownLeft, FileSpreadsheet, Monitor, Moon, Search, Sun, Wand2, type LucideIcon } from "lucide-react";
import { api, type AnalysisSession, type OperationSpec } from "@/lib/api";
import { FOOTER_NAV, PRIMARY_NAV, SESSION_NAV } from "@/lib/nav";
import { useCurrentSession } from "@/lib/session-store";
import { cn } from "@/lib/utils";
import { Dialog, DialogContent, DialogDescription, DialogTitle } from "@/components/ui/dialog";

type Command = { id: string; group: string; label: string; hint?: string; icon: LucideIcon; run: () => void };

/** Ctrl/⌘ K: jump to a screen, open a recent session, start a cleaning tool, switch theme. Only real actions are listed. */
export function CommandPalette({ open, onOpenChange }: { open: boolean; onOpenChange: (o: boolean) => void }) {
  const router = useRouter();
  const { setTheme } = useTheme();
  const session = useCurrentSession();
  const [query, setQuery] = useState("");
  const [index, setIndex] = useState(0);
  const [sessions, setSessions] = useState<AnalysisSession[]>([]);
  const [ops, setOps] = useState<OperationSpec[]>([]);
  const listRef = useRef<HTMLUListElement>(null);

  useEffect(() => {
    if (!open) return;
    setQuery("");
    setIndex(0);
    api.sessions().then(setSessions).catch(() => setSessions([]));
    if (session) api.operations().then(setOps).catch(() => setOps([]));
  }, [open, session]);

  const commands = useMemo<Command[]>(() => {
    const go = (href: string) => () => router.push(href);
    const list: Command[] = [...PRIMARY_NAV, ...FOOTER_NAV].map((n) => ({
      id: `nav:${n.href}`, group: "Go to", label: n.label, icon: n.icon, run: go(n.href),
    }));
    if (session) {
      SESSION_NAV.forEach((n) =>
        list.push({ id: `nav:${n.href}`, group: "Go to", label: n.label, hint: session.original_filename, icon: n.icon, run: go(`/s/${session.id}/${n.href}`) }),
      );
      ops.forEach((o) =>
        list.push({ id: `op:${o.id}`, group: "Cleaning tools", label: o.title, hint: o.group, icon: Wand2, run: go(`/s/${session.id}/clean?op=${o.id}`) }),
      );
    }
    sessions.slice(0, 8).forEach((s) =>
      list.push({
        id: `session:${s.id}`, group: "Recent sessions", label: `${s.original_filename} · ${s.sheet_name ?? ""}`,
        hint: `${(s.rows ?? 0).toLocaleString("en-US")} rows`, icon: FileSpreadsheet, run: go(`/s/${s.id}/health`),
      }),
    );
    list.push(
      { id: "theme:light", group: "Theme", label: "Light theme", icon: Sun, run: () => setTheme("light") },
      { id: "theme:dark", group: "Theme", label: "Dark theme", icon: Moon, run: () => setTheme("dark") },
      { id: "theme:system", group: "Theme", label: "Match my device", icon: Monitor, run: () => setTheme("system") },
    );
    return list;
  }, [router, session, sessions, ops, setTheme]);

  const filtered = useMemo(() => {
    const q = query.trim().toLowerCase();
    if (!q) return commands;
    const words = q.split(/\s+/);
    return commands.filter((c) => words.every((w) => `${c.label} ${c.group} ${c.hint ?? ""}`.toLowerCase().includes(w)));
  }, [commands, query]);

  useEffect(() => setIndex(0), [query]);
  useEffect(() => {
    listRef.current?.querySelector<HTMLElement>(`[data-index="${index}"]`)?.scrollIntoView({ block: "nearest" });
  }, [index]);

  const run = (c?: Command) => {
    if (!c) return;
    onOpenChange(false);
    c.run();
  };

  let lastGroup = "";
  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent hideClose className="top-[18%] max-w-xl translate-y-0 gap-0 overflow-hidden p-0" aria-describedby="cmd-desc">
        <DialogTitle className="sr-only">Command palette</DialogTitle>
        <DialogDescription id="cmd-desc" className="sr-only">
          Type to search screens, sessions, cleaning tools and themes. Use the arrow keys and Enter.
        </DialogDescription>
        <div className="flex items-center gap-2 border-b px-4">
          <Search className="size-4 text-muted-foreground" aria-hidden />
          <input
            autoFocus
            role="combobox"
            aria-expanded="true"
            aria-controls="cmd-list"
            aria-activedescendant={filtered[index] ? `cmd-${filtered[index].id}` : undefined}
            aria-label="Search commands"
            placeholder="Search screens, sessions, tools…"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === "ArrowDown") {
                e.preventDefault();
                setIndex((i) => Math.min(filtered.length - 1, i + 1));
              } else if (e.key === "ArrowUp") {
                e.preventDefault();
                setIndex((i) => Math.max(0, i - 1));
              } else if (e.key === "Enter") {
                e.preventDefault();
                run(filtered[index]);
              }
            }}
            className="h-12 w-full bg-transparent text-sm outline-none placeholder:text-muted-foreground"
          />
          <kbd className="rounded border bg-muted px-1.5 py-0.5 text-[10px] text-muted-foreground">Esc</kbd>
        </div>
        <ul id="cmd-list" ref={listRef} role="listbox" aria-label="Commands" className="max-h-80 overflow-y-auto p-2">
          {filtered.length === 0 && <li className="px-3 py-6 text-center text-sm text-muted-foreground">No matching commands.</li>}
          {filtered.map((c, i) => {
            const header = c.group !== lastGroup ? c.group : null;
            lastGroup = c.group;
            return (
              <li key={c.id} role="presentation">
                {header && <p className="px-3 pt-2 pb-1 text-[11px] font-semibold tracking-wider text-muted-foreground uppercase">{header}</p>}
                <div
                  id={`cmd-${c.id}`}
                  role="option"
                  aria-selected={i === index}
                  data-index={i}
                  onMouseMove={() => setIndex(i)}
                  onClick={() => run(c)}
                  className={cn("flex cursor-pointer items-center gap-3 rounded-lg px-3 py-2 text-sm", i === index && "bg-accent text-accent-foreground")}
                >
                  <c.icon className="size-4 shrink-0 text-muted-foreground" aria-hidden />
                  <span className="min-w-0 flex-1 truncate">{c.label}</span>
                  {c.hint && <span className="shrink-0 truncate text-xs text-muted-foreground">{c.hint}</span>}
                  {i === index && <CornerDownLeft className="size-3.5 text-muted-foreground" aria-hidden />}
                </div>
              </li>
            );
          })}
        </ul>
      </DialogContent>
    </Dialog>
  );
}
