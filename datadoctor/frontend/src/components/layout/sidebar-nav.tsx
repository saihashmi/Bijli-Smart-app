"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { lastSession, sessionIdFromPath } from "@/lib/last-session";
import { FOOTER_NAV, PRIMARY_NAV, SESSION_NAV, isActive, sessionHref, type NavItem } from "@/lib/nav";
import { cn } from "@/lib/utils";

const itemBase =
  "flex items-center gap-3 rounded-md px-3 py-2 text-sm font-medium outline-none transition-colors focus-visible:ring-2 focus-visible:ring-sidebar-ring";

function NavLink({ item, href, pathname, onNavigate }: { item: NavItem; href: string; pathname: string; onNavigate?: () => void }) {
  const active = isActive(pathname, href);
  return (
    <Link
      href={href}
      onClick={onNavigate}
      aria-current={active ? "page" : undefined}
      className={cn(
        itemBase,
        active
          ? "bg-sidebar-primary text-sidebar-primary-foreground"
          : "text-sidebar-foreground hover:bg-sidebar-accent hover:text-sidebar-accent-foreground",
      )}
    >
      <item.icon className="size-4 shrink-0" aria-hidden />
      {item.label}
    </Link>
  );
}

/** Navigation shared by the desktop sidebar and the mobile drawer. */
export function SidebarNav({ onNavigate }: { onNavigate?: () => void }) {
  const pathname = usePathname();
  // The open session comes from the URL; elsewhere, the last session opened in this browser.
  const [remembered, setRemembered] = useState<string | null>(null);
  useEffect(() => setRemembered(lastSession()), [pathname]);
  const sessionId = sessionIdFromPath(pathname) ?? remembered;
  return (
    <nav aria-label="Main" className="flex flex-1 flex-col gap-6 overflow-y-auto">
      <ul className="space-y-1">
        {PRIMARY_NAV.map((item) => (
          <li key={item.href}>
            <NavLink item={item} href={item.href} pathname={pathname} onNavigate={onNavigate} />
          </li>
        ))}
      </ul>

      <div>
        <p className="px-3 pb-2 text-xs font-semibold tracking-wide text-sidebar-foreground/70 uppercase">Current analysis</p>
        <ul className="space-y-1">
          {SESSION_NAV.map((item) => {
            const href = sessionHref(item, sessionId);
            return (
              <li key={item.href}>
                {href ? (
                  <NavLink item={item} href={href} pathname={pathname} onNavigate={onNavigate} />
                ) : (
                  <span aria-disabled="true" className={cn(itemBase, "cursor-not-allowed text-sidebar-foreground/70")}>
                    <item.icon className="size-4 shrink-0" aria-hidden />
                    {item.label}
                  </span>
                )}
              </li>
            );
          })}
        </ul>
        {!sessionId && <p className="px-3 pt-2 text-xs text-sidebar-foreground/70">Open or upload a dataset to use these tools.</p>}
      </div>

      <ul className="mt-auto space-y-1">
        {FOOTER_NAV.map((item) => (
          <li key={item.href}>
            <NavLink item={item} href={item.href} pathname={pathname} onNavigate={onNavigate} />
          </li>
        ))}
      </ul>
    </nav>
  );
}
