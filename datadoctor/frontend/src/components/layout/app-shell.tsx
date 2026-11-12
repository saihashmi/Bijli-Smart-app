"use client";

import { useState } from "react";
import Link from "next/link";
import { Menu } from "lucide-react";
import { Logo } from "@/components/logo";
import { ThemeSwitcher } from "@/components/theme-switcher";
import { Button } from "@/components/ui/button";
import { Sheet, SheetContent, SheetDescription, SheetTitle, SheetTrigger } from "@/components/ui/sheet";
import { LocalModeBadge } from "./local-mode-badge";
import { SidebarNav } from "./sidebar-nav";

/** App layout: fixed navy sidebar on desktop (lg+), top bar with a slide-out drawer on smaller screens. */
export function AppShell({ children }: { children: React.ReactNode }) {
  const [open, setOpen] = useState(false);

  return (
    <div className="min-h-screen">
      <a
        href="#main"
        className="sr-only z-[60] rounded-md bg-primary px-3 py-2 text-primary-foreground focus:not-sr-only focus:fixed focus:top-3 focus:left-3"
      >
        Skip to content
      </a>

      <aside className="fixed inset-y-0 left-0 z-40 hidden w-64 flex-col gap-6 border-r border-sidebar-border bg-sidebar px-3 py-5 lg:flex">
        <Link href="/" className="rounded-md px-2 outline-none focus-visible:ring-2 focus-visible:ring-sidebar-ring">
          <Logo inverted />
        </Link>
        <SidebarNav />
        <div className="px-2">
          <ThemeSwitcher compact onDark />
        </div>
      </aside>

      <div className="lg:pl-64">
        <header className="sticky top-0 z-30 flex h-14 items-center gap-3 border-b bg-background/90 px-4 backdrop-blur sm:px-6">
          <Sheet open={open} onOpenChange={setOpen}>
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
              <SidebarNav onNavigate={() => setOpen(false)} />
              <div className="px-2">
                <ThemeSwitcher compact onDark />
              </div>
            </SheetContent>
          </Sheet>
          <Link href="/" className="rounded-md outline-none focus-visible:ring-2 focus-visible:ring-ring lg:hidden">
            <Logo />
          </Link>
          <div className="ml-auto flex items-center gap-2">
            <LocalModeBadge />
          </div>
        </header>
        <main id="main" tabIndex={-1} className="mx-auto w-full max-w-7xl px-4 py-6 outline-none sm:px-6 lg:px-8 lg:py-8">
          {children}
        </main>
      </div>
    </div>
  );
}
