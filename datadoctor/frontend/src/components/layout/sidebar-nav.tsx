"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { FOOTER_NAV, PRIMARY_NAV, SESSION_NAV, isActive, sessionHref, type NavItem } from "@/lib/nav";
import { lastSession, sessionIdFromPath } from "@/lib/last-session";
import { cn } from "@/lib/utils";
import { Tooltip, TooltipContent, TooltipTrigger } from "@/components/ui/tooltip";

const itemBase =
  "relative flex items-center gap-3 rounded-lg px-3 py-2 text-sm font-medium outline-none transition-colors duration-150 focus-visible:ring-2 focus-visible:ring-sidebar-ring";

function Item({
  item,
  href,
  pathname,
  collapsed,
  onNavigate,
}: {
  item: NavItem;
  href: string | null;
  pathname: string;
  collapsed: boolean;
  onNavigate?: () => void;
}) {
  const active = href ? isActive(pathname, href) : false;
  const inner = (
    <>
      {active && <span className="absolute top-1.5 bottom-1.5 left-0 w-0.5 rounded-full bg-cyan" aria-hidden />}
      <item.icon className="size-4 shrink-0" aria-hidden />
      <span className={cn("truncate", collapsed && "sr-only")}>{item.label}</span>
    </>
  );
  const node = href ? (
    <Link
      href={href}
      onClick={onNavigate}
      aria-current={active ? "page" : undefined}
      className={cn(
        itemBase,
        collapsed && "justify-center px-0",
        active
          ? "bg-sidebar-primary/90 text-sidebar-primary-foreground shadow-[0_0_24px_-6px_var(--brand)]"
          : "text-sidebar-foreground hover:bg-sidebar-accent hover:text-sidebar-accent-foreground",
      )}
    >
      {inner}
    </Link>
  ) : (
    <span aria-disabled="true" className={cn(itemBase, "cursor-not-allowed text-sidebar-foreground/70", collapsed && "justify-center px-0")}>
      {inner}
    </span>
  );
  if (!collapsed) return node;
  return (
    <Tooltip>
      <TooltipTrigger asChild>{node}</TooltipTrigger>
      <TooltipContent side="right">{href ? item.label : `${item.label}: open a dataset first`}</TooltipContent>
    </Tooltip>
  );
}

/** Navigation shared by the desktop sidebar and the mobile drawer. */
export function SidebarNav({ onNavigate, collapsed = false }: { onNavigate?: () => void; collapsed?: boolean }) {
  const pathname = usePathname();
  // The open session comes from the URL; elsewhere, the last session opened in this browser.
  const [remembered, setRemembered] = useState<string | null>(null);
  useEffect(() => setRemembered(lastSession()), [pathname]);
  const sessionId = sessionIdFromPath(pathname) ?? remembered;

  return (
    <nav aria-label="Main" className="flex flex-1 flex-col gap-5 overflow-x-hidden overflow-y-auto">
      <ul className="space-y-1">
        {PRIMARY_NAV.map((item) => (
          <li key={item.href}>
            <Item item={item} href={item.href} pathname={pathname} collapsed={collapsed} onNavigate={onNavigate} />
          </li>
        ))}
      </ul>

      <div>
        {collapsed ? (
          <div className="mx-auto mb-2 h-px w-6 bg-sidebar-border" aria-hidden />
        ) : (
          <p className="px-3 pb-2 text-[11px] font-semibold tracking-wider text-sidebar-foreground/70 uppercase">Current analysis</p>
        )}
        <ul className="space-y-1">
          {SESSION_NAV.map((item) => (
            <li key={item.href}>
              <Item item={item} href={sessionHref(item, sessionId)} pathname={pathname} collapsed={collapsed} onNavigate={onNavigate} />
            </li>
          ))}
        </ul>
        {!sessionId && !collapsed && (
          <p className="px-3 pt-2 text-xs text-sidebar-foreground/70">Open or upload a dataset to use these tools.</p>
        )}
      </div>

      <ul className="mt-auto space-y-1">
        {FOOTER_NAV.map((item) => (
          <li key={item.href}>
            <Item item={item} href={item.href} pathname={pathname} collapsed={collapsed} onNavigate={onNavigate} />
          </li>
        ))}
      </ul>
    </nav>
  );
}
