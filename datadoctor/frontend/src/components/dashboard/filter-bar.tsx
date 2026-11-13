"use client";

import { useEffect, useId, useState } from "react";
import { Filter as FilterIcon, Plus, X } from "lucide-react";
import type { Field, Filter } from "@/lib/analytics";
import { Button } from "@/components/ui/button";
import { Checkbox } from "@/components/ui/checkbox";
import { Dialog, DialogContent, DialogDescription, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { NativeSelect } from "@/components/ui/native-select";
import { Segmented } from "@/components/ui/segmented";

export function describeFilter(f: Filter): string {
  if (f.op === "range") {
    if (f.min != null && f.max != null) return `${f.column} from ${f.min} to ${f.max}`;
    return f.min != null ? `${f.column} at least ${f.min}` : `${f.column} at most ${f.max}`;
  }
  if (f.op === "date_range") {
    if (f.start && f.end) return `${f.column} from ${f.start} to ${f.end}`;
    return f.start ? `${f.column} from ${f.start}` : `${f.column} until ${f.end}`;
  }
  const items = [...f.values, ...(f.include_missing ? ["(missing)"] : [])];
  const list = items.length > 3 ? `${items.slice(0, 3).join(", ")} +${items.length - 3} more` : items.join(", ");
  return `${f.column} ${f.op === "in" ? "is" : "is not"} ${list}`;
}

type Mode = "values" | "range" | "date_range";
const modeFor = (f: Field | undefined): Mode => (f?.kind === "number" && !f.values ? "range" : f?.kind === "date" ? "date_range" : f?.kind === "number" ? "range" : "values");

function FilterDialog({
  open,
  fields,
  initial,
  onClose,
  onSave,
}: {
  open: boolean;
  fields: Field[];
  initial: Filter | null;
  onClose: () => void;
  onSave: (f: Filter) => void;
}) {
  const uid = useId();
  const usable = fields.filter((f) => f.kind === "number" || f.kind === "date" || (f.values && f.values.length > 0));
  const [column, setColumn] = useState("");
  const [op, setOp] = useState<"in" | "not_in">("in");
  const [values, setValues] = useState<string[]>([]);
  const [missing, setMissing] = useState(false);
  const [min, setMin] = useState("");
  const [max, setMax] = useState("");
  const [start, setStart] = useState("");
  const [end, setEnd] = useState("");

  useEffect(() => {
    if (!open) return;
    const f = initial;
    setColumn(f?.column ?? usable[0]?.name ?? "");
    setOp(f && (f.op === "in" || f.op === "not_in") ? f.op : "in");
    setValues(f && (f.op === "in" || f.op === "not_in") ? f.values : []);
    setMissing(Boolean(f && (f.op === "in" || f.op === "not_in") && f.include_missing));
    setMin(f?.op === "range" && f.min != null ? String(f.min) : "");
    setMax(f?.op === "range" && f.max != null ? String(f.max) : "");
    setStart(f?.op === "date_range" ? (f.start ?? "") : "");
    setEnd(f?.op === "date_range" ? (f.end ?? "") : "");
    // eslint-disable-next-line react-hooks/exhaustive-deps -- reset only when the dialog opens
  }, [open, initial]);

  const field = usable.find((f) => f.name === column);
  const mode = modeFor(field);
  const lo = min.trim() === "" ? null : Number(min);
  const hi = max.trim() === "" ? null : Number(max);

  let problem: string | null = null;
  if (!field) problem = "Choose a column.";
  else if (mode === "values" && !values.length && !missing) problem = "Tick at least one value.";
  else if (mode === "range") {
    if (lo === null && hi === null) problem = "Enter a minimum, a maximum or both.";
    else if ((lo !== null && Number.isNaN(lo)) || (hi !== null && Number.isNaN(hi))) problem = "Enter numbers only.";
    else if (lo !== null && hi !== null && lo > hi) problem = "The minimum is greater than the maximum.";
  } else if (mode === "date_range") {
    if (!start && !end) problem = "Choose a start date, an end date or both.";
    else if (start && end && start > end) problem = "The start date is after the end date.";
  }

  const save = () => {
    if (problem || !field) return;
    if (mode === "values") onSave({ op, column, values, include_missing: missing });
    else if (mode === "range") onSave({ op: "range", column, min: lo, max: hi });
    else onSave({ op: "date_range", column, start: start || null, end: end || null });
  };

  return (
    <Dialog open={open} onOpenChange={(o) => !o && onClose()}>
      <DialogContent className="max-w-lg" data-testid="filter-dialog">
        <DialogHeader>
          <DialogTitle>{initial ? "Edit filter" : "Add a filter"}</DialogTitle>
          <DialogDescription>Filters apply to every widget on this dashboard. Your data is not changed.</DialogDescription>
        </DialogHeader>
        <div className="space-y-4">
          <div className="space-y-1.5">
            <Label htmlFor={`${uid}-col`}>Column</Label>
            <NativeSelect
              id={`${uid}-col`}
              value={column}
              onChange={(e) => {
                setColumn(e.target.value);
                setValues([]);
                setMissing(false);
              }}
            >
              {usable.map((f) => (
                <option key={f.name} value={f.name}>
                  {f.name} ({f.kind})
                </option>
              ))}
            </NativeSelect>
          </div>

          {field && mode === "values" && (
            <>
              <Segmented
                label="Filter mode"
                size="sm"
                value={op}
                onChange={setOp}
                options={[
                  { value: "in", label: "Keep only ticked" },
                  { value: "not_in", label: "Leave out ticked" },
                ]}
              />
              <fieldset>
                <legend className="mb-1.5 text-sm font-medium">Values, most frequent first</legend>
                <div className="grid max-h-56 gap-1.5 overflow-y-auto rounded-md border p-2 sm:grid-cols-2">
                  {(field.values ?? []).map((v) => (
                    <label key={v} className="flex cursor-pointer items-center gap-2 text-sm">
                      <Checkbox checked={values.includes(v)} onCheckedChange={(on) => setValues(on ? [...values, v] : values.filter((x) => x !== v))} />
                      <span className="truncate font-mono text-xs" title={v}>
                        {v.replace(/^ +| +$/g, (m) => "␣".repeat(m.length))}
                      </span>
                    </label>
                  ))}
                  {field.missing > 0 && (
                    <label className="flex cursor-pointer items-center gap-2 text-sm">
                      <Checkbox checked={missing} onCheckedChange={(on) => setMissing(Boolean(on))} />
                      <span className="text-muted-foreground">(missing), {field.missing} rows</span>
                    </label>
                  )}
                </div>
                {field.unique > (field.values?.length ?? 0) && (
                  <p className="mt-1 text-xs text-muted-foreground">
                    Showing the {field.values?.length} most frequent of {field.unique} values.
                  </p>
                )}
              </fieldset>
            </>
          )}

          {field && mode === "range" && (
            <div className="grid gap-3 sm:grid-cols-2">
              <div className="space-y-1.5">
                <Label htmlFor={`${uid}-min`}>Minimum</Label>
                <Input id={`${uid}-min`} inputMode="decimal" value={min} onChange={(e) => setMin(e.target.value)} placeholder={field.min != null ? String(field.min) : ""} />
              </div>
              <div className="space-y-1.5">
                <Label htmlFor={`${uid}-max`}>Maximum</Label>
                <Input id={`${uid}-max`} inputMode="decimal" value={max} onChange={(e) => setMax(e.target.value)} placeholder={field.max != null ? String(field.max) : ""} />
              </div>
              <p className="text-xs text-muted-foreground sm:col-span-2">
                Values in the data run from {String(field.min)} to {String(field.max)}. Rows without a number in this column are left out.
              </p>
            </div>
          )}

          {field && mode === "date_range" && (
            <div className="grid gap-3 sm:grid-cols-2">
              <div className="space-y-1.5">
                <Label htmlFor={`${uid}-start`}>From</Label>
                <Input id={`${uid}-start`} type="date" value={start} onChange={(e) => setStart(e.target.value)} />
              </div>
              <div className="space-y-1.5">
                <Label htmlFor={`${uid}-end`}>To (inclusive)</Label>
                <Input id={`${uid}-end`} type="date" value={end} onChange={(e) => setEnd(e.target.value)} />
              </div>
              <p className="text-xs text-muted-foreground sm:col-span-2">
                Dates in the data run from {String(field.min)} to {String(field.max)}. Rows without a clear date are left out.
              </p>
            </div>
          )}

          {!usable.length && <p className="text-sm text-muted-foreground">No column in this data can be filtered.</p>}
        </div>
        <div className="flex flex-wrap items-center justify-end gap-2">
          {problem && (
            <p className="mr-auto text-xs text-muted-foreground" role="status">
              {problem}
            </p>
          )}
          <Button variant="outline" onClick={onClose}>
            Cancel
          </Button>
          <Button onClick={save} disabled={Boolean(problem)}>
            {initial ? "Update filter" : "Apply filter"}
          </Button>
        </div>
      </DialogContent>
    </Dialog>
  );
}

export function FilterBar({
  filters,
  fields,
  rowsKept,
  rowsTotal,
  onChange,
}: {
  filters: Filter[];
  fields: Field[];
  rowsKept: number | null;
  rowsTotal: number;
  onChange: (filters: Filter[]) => void;
}) {
  const [editing, setEditing] = useState<number | "new" | null>(null);
  return (
    <div className="flex flex-wrap items-center gap-2" data-testid="filter-bar">
      <span className="inline-flex items-center gap-1.5 text-sm font-medium">
        <FilterIcon className="size-4 text-muted-foreground" aria-hidden />
        Filters
      </span>
      {filters.map((f, i) => (
        <span key={i} className="inline-flex max-w-full items-center rounded-full border bg-card text-xs" data-testid="filter-chip">
          <button type="button" className="min-w-0 cursor-pointer truncate rounded-l-full py-1 pr-1 pl-3 outline-none hover:underline focus-visible:ring-2 focus-visible:ring-ring" onClick={() => setEditing(i)} title="Edit filter">
            {describeFilter(f)}
          </button>
          <button
            type="button"
            aria-label={`Remove filter: ${describeFilter(f)}`}
            className="grid size-6 shrink-0 cursor-pointer place-items-center rounded-full text-muted-foreground outline-none hover:text-foreground focus-visible:ring-2 focus-visible:ring-ring"
            onClick={() => onChange(filters.filter((_, j) => j !== i))}
          >
            <X className="size-3.5" aria-hidden />
          </button>
        </span>
      ))}
      <Button variant="outline" size="sm" onClick={() => setEditing("new")} disabled={filters.length >= 20}>
        <Plus aria-hidden />
        Add filter
      </Button>
      {filters.length > 0 && (
        <>
          <Button variant="ghost" size="sm" onClick={() => onChange([])}>
            Clear all
          </Button>
          {rowsKept !== null && (
            <span className="text-xs text-muted-foreground tabular-nums" data-testid="filter-count" role="status">
              {rowsKept.toLocaleString("en-US")} of {rowsTotal.toLocaleString("en-US")} rows match
            </span>
          )}
        </>
      )}
      <FilterDialog
        open={editing !== null}
        fields={fields}
        initial={typeof editing === "number" ? filters[editing] : null}
        onClose={() => setEditing(null)}
        onSave={(f) => {
          onChange(typeof editing === "number" ? filters.map((x, i) => (i === editing ? f : x)) : [...filters, f]);
          setEditing(null);
        }}
      />
    </div>
  );
}
