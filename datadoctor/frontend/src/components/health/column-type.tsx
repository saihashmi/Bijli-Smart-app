import { Calendar, CalendarClock, CircleHelp, CircleOff, Hash, Tags, ToggleLeft, Type } from "lucide-react";
import type { ColumnType } from "@/lib/api";

export const TYPE_META: Record<ColumnType, { label: string; icon: typeof Hash }> = {
  integer: { label: "Whole number", icon: Hash },
  number: { label: "Number", icon: Hash },
  date: { label: "Date", icon: Calendar },
  datetime: { label: "Date & time", icon: CalendarClock },
  boolean: { label: "Yes / No", icon: ToggleLeft },
  category: { label: "Category", icon: Tags },
  text: { label: "Text", icon: Type },
  other: { label: "Other", icon: CircleHelp },
  empty: { label: "Empty", icon: CircleOff },
};

export function TypeLabel({ type, mixed }: { type: ColumnType; mixed?: boolean }) {
  const meta = TYPE_META[type] ?? TYPE_META.other;
  return (
    <span className="inline-flex items-center gap-1 text-xs font-medium text-muted-foreground">
      <meta.icon className="size-3.5" aria-hidden />
      {meta.label}
      {mixed && <span className="text-warning-text">· mixed</span>}
    </span>
  );
}
