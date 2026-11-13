"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { FileSpreadsheet, Menu, PanelLeftClose, PanelLeftOpen, Search } from "lucide-react";
import { useCurrentSession } from "@/lib/session-store";
import { cn } from "@/lib/utils";
import { Logo } from "@/components/logo";
import { ThemeSwitcher } from "@/components/theme-switcher";
import { Button } from "@/components/ui/button";
import { Sheet, SheetContent, SheetDescription, SheetTitle, SheetTrigger } from "@/components/ui/sheet";
import { TooltipProvider } from "@/components/ui/tooltip";
import { CommandPalette } from "./command-palette";
import { LocalModeBadge } from "./local-mode-badge";
import { SidebarNav } from "./sidebar-nav";
import { StatusIndicator } from "./status-indicator";

const KEY = "dd:sidebar-collapsed";

/** App layout: collapsible navy sidebar on desktop, glass top bar, slide-out drawer on smaller screens. */
export function AppShell({ children }: { children: React.ReactNode }) {
  const [drawer, setDrawer] = useState(false);
  const [collapsed, setCollapsed] = useState(false);
  const [palette, setPalette] = useState(false);
  const session = useCurrentSession();

  useEffect(() => {
    try {
      setCollapsed(localStorage.getItem(KEY) === "1");
    } catch {
      /* ignore */
    }
  }, []);
  const toggle = () =>
    setCollapsed((c) => {
      try {
        localStorage.setItem(KEY, c ? "0" : "1");
      } catch {
        /* ignore */
      }
      return !c;
    });

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === "k") {
        e.preventDefault();
        setPalette((p) => !p);
      }
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, []);

  return (
    <TooltipProvider>
      <div className="min-h-screen" data-sidebar={collapsed ? "collapsed" : "expanded"}>
        <a
          href="#main"
          className="sr-only z-[60] rounded-md bg-primary px-3 py-2 text-primary-foreground focus:not-sr-only focus:fixed focus:top-3 focus:left-3"
        >
          Skip to content
        </a>

        <aside
          className={cn(
            "fixed inset-y-0 left-0 z-40 hidden flex-col gap-5 border-r border-sidebar-border bg-sidebar py-4 transition-[width] duration-200 ease-out lg:flex",
            collapsed ? "w-[4.25rem] px-2.5" : "w-64 px-3",
          )}
          data-testid="sidebar"
        >
          <div className={cn("flex items-center", collapsed ? "justify-center" : "justify-between px-2")}>
            <Link href="/" className="rounded-md outline-none focus-visible:ring-2 focus-visible:ring-sidebar-ring" aria-label="DataDoctor AI home">
              <Logo inverted iconOnly={collapsed} />
            </Link>
          </div>
          <SidebarNav collapsed={collapsed} />
          <div className={cn("flex items-center gap-2", collapsed ? "flex-col" : "justify-between px-1")}>
            {!collapsed && <ThemeSwitcher compact onDark />}
            <button
              type="button"
              onClick={toggle}
              aria-label={collapsed ? "Expand sidebar" : "Collapse sidebar"}
              aria-pressed={collapsed}
              className="grid size-8 cursor-pointer place-items-center rounded-md text-sidebar-foreground outline-none hover:bg-sidebar-accent hover:text-sidebar-accent-foreground focus-visible:ring-2 focus-visible:ring-sidebar-ring"
            >
              {collapsed ? <PanelLeftOpen className="size-4" /> : <PanelLeftClose className="size-4" />}
            </button>
          </div>
        </aside>

        <div className={cn("transition-[padding] duration-200 ease-out", collapsed ? "lg:pl-[4.25rem]" : "lg:pl-64")}>
          <header className="glass sticky top-0 z-30 flex h-14 items-center gap-3 border-b px-4 sm:px-6">
            <Sheet open={drawer} onOpenChange={setDrawer}>
              <SheetTrigger asChild>
                <Button variant="ghost" size="icon" className="lg:hidden" aria-label="Open navigation menu">
                  <Menu className="size-5" />
                </Button>
              </SheetTrigger>
              <SheetContent side="left" className="gap-6 border-sidebar-border bg-sidebar px-3 py-5 text-sidebar-foreground">
                <SheetTitle className="px-2">
                  <Logo inverted />
                </SheetTitle>
                <SheetDescription className="sr-only">Main navigation</SheetDescription>
                <SidebarNav onNavigate={() => setDrawer(false)} />
                <div className="px-2">
                  <ThemeSwitcher compact onDark />
                </div>
              </SheetContent>
            </Sheet>
            <Link href="/" className="rounded-md outline-none focus-visible:ring-2 focus-visible:ring-ring lg:hidden">
              <Logo />
            </Link>

            {session && (
              <Link
                href={`/s/${session.id}/health`}
                className="hidden min-w-0 items-center gap-2 rounded-full border bg-card/60 px-3 py-1 text-xs outline-none hover:bg-card focus-visible:ring-2 focus-visible:ring-ring lg:flex"
                data-testid="dataset-chip"
                title="Current dataset"
              >
                <FileSpreadsheet className="size-3.5 shrink-0 text-primary dark:text-link" aria-hidden />
                <span className="truncate font-medium">{session.original_filename}</span>
                <span className="shrink-0 text-muted-foreground">· {session.sheet_name}</span>
              </Link>
            )}

            <div className="ml-auto flex items-center gap-2">
              <StatusIndicator />
              <button
                type="button"
                onClick={() => setPalette(true)}
                className="hidden h-8 cursor-pointer items-center gap-2 rounded-lg border bg-card/60 px-2.5 text-xs text-muted-foreground outline-none hover:bg-card hover:text-foreground focus-visible:ring-2 focus-visible:ring-ring md:inline-flex"
                title="Open the command palette"
              >
                <Search className="size-3.5" aria-hidden /> Search
                <kbd className="rounded border bg-muted px-1 text-[10px]">Ctrl K</kbd>
              </button>
              <Button variant="ghost" size="icon" className="md:hidden" aria-label="Open command palette" onClick={() => setPalette(true)}>
                <Search className="size-4" />
              </Button>
              <LocalModeBadge />
            </div>
          </header>
          <main id="main" tabIndex={-1} className="mx-auto w-full max-w-[1440px] px-4 py-6 outline-none sm:px-6 lg:px-8 lg:py-8">
            {children}
          </main>
        </div>
        <CommandPalette open={palette} onOpenChange={setPalette} />
      </div>
    </TooltipProvider>
  );
}
