import {
  BarChart3,
  Bot,
  FileDown,
  FolderKanban,
  HeartPulse,
  Settings,
  Upload,
  Wand2,
  type LucideIcon,
} from "lucide-react";

export type NavItem = {
  label: string;
  href: string;
  icon: LucideIcon;
  /** Milestone in which the screen becomes functional (PLAN.md §8). */
  milestone: number;
  /** Screens that only make sense once a dataset is open. */
  needsSession?: boolean;
};

export const PRIMARY_NAV: NavItem[] = [
  { label: "Workspace", href: "/workspace", icon: FolderKanban, milestone: 4 },
  { label: "Upload Studio", href: "/upload", icon: Upload, milestone: 4 },
];

export const SESSION_NAV: NavItem[] = [
  { label: "Data Health", href: "health", icon: HeartPulse, milestone: 6, needsSession: true },
  { label: "Cleaning Studio", href: "clean", icon: Wand2, milestone: 7, needsSession: true },
  { label: "Dashboard Studio", href: "dashboard", icon: BarChart3, milestone: 10, needsSession: true },
  { label: "AI Analyst", href: "analyst", icon: Bot, milestone: 11, needsSession: true },
  { label: "Export Center", href: "export", icon: FileDown, milestone: 13, needsSession: true },
];

export const FOOTER_NAV: NavItem[] = [{ label: "Settings", href: "/settings", icon: Settings, milestone: 3 }];

/** Resolve a session-scoped nav item to its URL, or null when no dataset is open. */
export function sessionHref(item: NavItem, sessionId: string | null): string | null {
  return sessionId ? `/s/${sessionId}/${item.href}` : null;
}

export function isActive(pathname: string, href: string): boolean {
  return pathname === href || pathname.startsWith(`${href}/`);
}
