"use client";

import { AlertTriangle, EyeOff, Table2 } from "lucide-react";
import type { Sheet } from "@/lib/api";
import { formatInteger } from "@/lib/format";
import { cn } from "@/lib/utils";
import { Badge } from "@/components/ui/badge";
import { RadioGroup, RadioGroupItem } from "@/components/ui/radio-group";

export function SheetPicker({ sheets, value, onChange }: { sheets: Sheet[]; value: number | null; onChange: (i: number) => void }) {
  return (
    <RadioGroup
      aria-label="Worksheet"
      value={value === null ? "" : String(value)}
      onValueChange={(v) => onChange(Number(v))}
      className="gap-2"
    >
      {sheets.map((s) => {
        const id = `sheet-${s.index}`;
        return (
          <label
            key={s.index}
            htmlFor={id}
            data-testid={`sheet-option-${s.index}`}
            className={cn(
              "flex items-start gap-3 rounded-lg border p-3 transition-colors",
              s.selectable ? "cursor-pointer hover:bg-muted/50" : "cursor-not-allowed opacity-70",
              value === s.index && "border-primary bg-accent/60",
            )}
          >
            <RadioGroupItem id={id} value={String(s.index)} disabled={!s.selectable} className="mt-0.5" />
            <span className="min-w-0 flex-1 space-y-1">
              <span className="flex flex-wrap items-center gap-2">
                <Table2 className="size-4 text-muted-foreground" aria-hidden />
                <span className="font-medium break-all">{s.name}</span>
                {s.visibility !== "visible" && (
                  <Badge variant="outline">
                    <EyeOff aria-hidden /> {s.visibility === "hidden" ? "Hidden" : "Very hidden"}
                  </Badge>
                )}
              </span>
              <span className="block text-sm text-muted-foreground">
                {s.selectable ? `${plural(s.rows, "row")} × ${plural(s.columns, "column")}` : s.problem}
              </span>
              {s.formula_cells_without_cache > 0 && (
                <span className="flex items-start gap-1.5 text-xs text-warning-text">
                  <AlertTriangle className="mt-px size-3.5 shrink-0" aria-hidden />
                  {formatInteger(s.formula_cells_without_cache)} formula cell
                  {s.formula_cells_without_cache === 1 ? " has" : "s have"} no saved result and will appear empty. Open and save
                  the file in Excel to fix this.
                </span>
              )}
            </span>
          </label>
        );
      })}
    </RadioGroup>
  );
}

function plural(n: number, word: string) {
  return `${formatInteger(n)} ${word}${n === 1 ? "" : "s"}`;
}
