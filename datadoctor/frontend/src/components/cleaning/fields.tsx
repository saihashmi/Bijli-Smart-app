"use client";

import { useEffect, useState } from "react";
import { ArrowDown, ArrowUp, Loader2 } from "lucide-react";
import { api, ApiError, type CategoryGroup, type ColumnProfile, type OpField } from "@/lib/api";
import { formatInteger } from "@/lib/format";
import { TYPE_META } from "@/components/health/column-type";
import { Button } from "@/components/ui/button";
import { Checkbox } from "@/components/ui/checkbox";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { NativeSelect } from "@/components/ui/native-select";
import { RadioGroup, RadioGroupItem } from "@/components/ui/radio-group";
import { Switch } from "@/components/ui/switch";

export type Values = Record<string, unknown>;

const FAMILY_FOR_FILTER: Record<string, string> = { text: "text", number: "number", date: "date" };

function matches(profile: ColumnProfile | undefined, filter?: string) {
  if (!filter || !profile) return true;
  return profile.family === FAMILY_FOR_FILTER[filter];
}

function columnLabel(name: string, p?: ColumnProfile) {
  return p ? `${name} · ${TYPE_META[p.type]?.label ?? p.type}` : name;
}

/** Columns matching the field's filter first, then the rest. */
function orderedColumns(columns: string[], profiles: Map<string, ColumnProfile>, filter?: string) {
  const good = columns.filter((c) => matches(profiles.get(c), filter));
  return [...good, ...columns.filter((c) => !good.includes(c))];
}

type FieldProps = {
  field: OpField;
  values: Values;
  setValue: (name: string, value: unknown) => void;
  columns: string[];
  profiles: Map<string, ColumnProfile>;
  sessionId: string;
};

export function Field(props: FieldProps) {
  const { field, values, setValue, columns, profiles } = props;
  const id = `f-${field.name}`;
  const value = values[field.name];

  if (field.show_if && !Object.entries(field.show_if).every(([k, v]) => values[k] === v)) return null;

  const wrap = (control: React.ReactNode, labelFor: string | undefined = id) => (
    <div className="space-y-1.5">
      <Label htmlFor={labelFor}>
        {field.label}
        {field.optional && <span className="font-normal text-muted-foreground"> (optional)</span>}
      </Label>
      {control}
      {field.help && <p className="text-xs text-muted-foreground">{field.help}</p>}
    </div>
  );

  switch (field.kind) {
    case "column":
      return wrap(
        <NativeSelect id={id} value={(value as string) ?? ""} onChange={(e) => setValue(field.name, e.target.value)}>
          <option value="" disabled>
            Choose a column…
          </option>
          {orderedColumns(columns, profiles, field.filter).map((c) => (
            <option key={c} value={c}>
              {columnLabel(c, profiles.get(c))}
            </option>
          ))}
        </NativeSelect>,
      );
    case "columns": {
      const selected = new Set((value as string[]) ?? []);
      const toggle = (c: string, on: boolean) => {
        const next = new Set(selected);
        if (on) next.add(c);
        else next.delete(c);
        setValue(field.name, columns.filter((x) => next.has(x)));
      };
      return wrap(
        <div className="max-h-56 space-y-1 overflow-y-auto rounded-md border p-2" role="group" aria-label={field.label} id={id}>
          {orderedColumns(columns, profiles, field.filter).map((c) => (
            <label key={c} className="flex cursor-pointer items-center gap-2 rounded px-1 py-0.5 text-sm hover:bg-muted">
              <Checkbox checked={selected.has(c)} onCheckedChange={(v) => toggle(c, v === true)} aria-label={c} />
              <span className="truncate">{columnLabel(c, profiles.get(c))}</span>
            </label>
          ))}
        </div>,
        undefined,
      );
    }
    case "select":
      return wrap(
        <NativeSelect id={id} value={(value as string) ?? ""} onChange={(e) => setValue(field.name, e.target.value)}>
          {field.options?.map((o) => (
            <option key={o.value} value={o.value}>
              {o.label}
            </option>
          ))}
        </NativeSelect>,
      );
    case "boolean":
      return (
        <div className="flex items-center justify-between gap-3">
          <Label htmlFor={id}>{field.label}</Label>
          <Switch id={id} checked={Boolean(value)} onCheckedChange={(v) => setValue(field.name, v)} />
        </div>
      );
    case "text":
      return wrap(<Input id={id} value={(value as string) ?? ""} onChange={(e) => setValue(field.name, e.target.value)} />);
    case "number":
      return wrap(
        <Input
          id={id}
          type="number"
          inputMode="decimal"
          value={value === undefined || value === null ? "" : String(value)}
          onChange={(e) => setValue(field.name, e.target.value === "" ? null : Number(e.target.value))}
        />,
      );
    case "tokens":
      return wrap(
        <Input
          id={id}
          placeholder="e.g. TBD, unknown"
          value={((value as string[]) ?? []).join(", ")}
          onChange={(e) =>
            setValue(
              field.name,
              e.target.value
                .split(",")
                .map((t) => t.trim())
                .filter(Boolean),
            )
          }
        />,
      );
    case "category_mapping":
      return <CategoryMapping {...props} />;
    case "rename_mapping":
      return <RenameMapping {...props} />;
    case "column_order":
      return <ColumnOrder {...props} />;
    case "date_interpretation":
      return <DateInterpretation {...props} />;
  }
}

function CategoryMapping({ field, values, setValue, sessionId }: FieldProps) {
  const column = values.column as string | undefined;
  const [groups, setGroups] = useState<CategoryGroup[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [targets, setTargets] = useState<string[]>([]);
  const [chosen, setChosen] = useState<Set<string>[]>([]);

  useEffect(() => {
    if (!column) return;
    let alive = true;
    setGroups(null);
    setError(null);
    api
      .categorySuggestions(sessionId, column)
      .then((r) => {
        if (!alive) return;
        setGroups(r.groups);
        setTargets(r.groups.map((g) => g.suggested));
        setChosen(r.groups.map((g) => new Set(g.variants.map((v) => v.label))));
      })
      .catch((e: unknown) => alive && setError(e instanceof ApiError ? e.message : "Could not load labels."));
    return () => {
      alive = false;
    };
  }, [column, sessionId]);

  useEffect(() => {
    if (!groups) return;
    const mapping: Record<string, string> = {};
    groups.forEach((g, i) =>
      g.variants.forEach((v) => {
        if (chosen[i]?.has(v.label) && v.label !== targets[i] && targets[i]?.trim()) mapping[v.label] = targets[i];
      }),
    );
    setValue(field.name, mapping);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [groups, targets, chosen]);

  if (!column) return <p className="text-sm text-muted-foreground">Choose a column to see labels that differ only in capitals or spaces.</p>;
  if (error) return <p className="text-sm text-destructive-text">{error}</p>;
  if (!groups)
    return (
      <p className="flex items-center gap-2 text-sm text-muted-foreground">
        <Loader2 className="size-4 animate-spin" aria-hidden /> Finding label variants…
      </p>
    );
  if (groups.length === 0) return <p className="text-sm text-muted-foreground">No labels in “{column}” differ only by capitals or spaces.</p>;

  return (
    <div className="space-y-3" data-testid="category-mapping">
      <p className="text-sm font-medium">{field.label}</p>
      {groups.map((g, i) => (
        <div key={g.suggested + i} className="space-y-2 rounded-lg border p-3">
          <div className="space-y-1">
            <Label htmlFor={`target-${i}`} className="text-xs text-muted-foreground">
              Use this label
            </Label>
            <Input
              id={`target-${i}`}
              value={targets[i] ?? ""}
              onChange={(e) => setTargets((t) => t.map((x, j) => (j === i ? e.target.value : x)))}
            />
          </div>
          <ul className="space-y-1">
            {g.variants.map((v) => (
              <li key={v.label}>
                <label className="flex cursor-pointer items-center gap-2 text-sm">
                  <Checkbox
                    checked={chosen[i]?.has(v.label) ?? false}
                    onCheckedChange={(on) =>
                      setChosen((all) =>
                        all.map((set, j) => {
                          if (j !== i) return set;
                          const next = new Set(set);
                          if (on === true) next.add(v.label);
                          else next.delete(v.label);
                          return next;
                        }),
                      )
                    }
                    aria-label={`Merge “${v.label}”`}
                  />
                  <span className="font-mono whitespace-pre">“{v.label}”</span>
                  <span className="text-xs text-muted-foreground">{formatInteger(v.count)} rows</span>
                </label>
              </li>
            ))}
          </ul>
        </div>
      ))}
    </div>
  );
}

function RenameMapping({ field, values, setValue, columns }: FieldProps) {
  const [names, setNames] = useState<Record<string, string>>(() => Object.fromEntries(columns.map((c) => [c, c])));
  useEffect(() => {
    const mapping = Object.fromEntries(Object.entries(names).filter(([k, v]) => k !== v && v.trim()));
    setValue(field.name, mapping);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [names]);
  void values;
  return (
    <div className="space-y-2">
      <p className="text-sm font-medium">{field.label}</p>
      <div className="max-h-80 space-y-2 overflow-y-auto pr-1">
        {columns.map((c) => (
          <div key={c} className="grid grid-cols-[minmax(0,1fr)_minmax(0,1.3fr)] items-center gap-2">
            <Label htmlFor={`rename-${c}`} className="truncate font-mono text-xs font-normal text-muted-foreground" title={c}>
              {c}
            </Label>
            <Input id={`rename-${c}`} value={names[c] ?? c} onChange={(e) => setNames((n) => ({ ...n, [c]: e.target.value }))} />
          </div>
        ))}
      </div>
    </div>
  );
}

function ColumnOrder({ field, setValue, columns }: FieldProps) {
  const [order, setOrder] = useState(columns);
  useEffect(() => setValue(field.name, order), [order]); // eslint-disable-line react-hooks/exhaustive-deps
  const move = (i: number, d: -1 | 1) =>
    setOrder((o) => {
      const next = [...o];
      [next[i], next[i + d]] = [next[i + d], next[i]];
      return next;
    });
  return (
    <div className="space-y-2">
      <p className="text-sm font-medium">{field.label}</p>
      <ol className="max-h-80 space-y-1 overflow-y-auto">
        {order.map((c, i) => (
          <li key={c} className="flex items-center gap-2 rounded-md border px-2 py-1 text-sm">
            <span className="w-6 text-right text-xs text-muted-foreground tabular-nums">{i + 1}</span>
            <span className="min-w-0 flex-1 truncate">{c}</span>
            <Button type="button" variant="ghost" size="icon" className="size-7" disabled={i === 0} onClick={() => move(i, -1)} aria-label={`Move ${c} up`}>
              <ArrowUp />
            </Button>
            <Button type="button" variant="ghost" size="icon" className="size-7" disabled={i === order.length - 1} onClick={() => move(i, 1)} aria-label={`Move ${c} down`}>
              <ArrowDown />
            </Button>
          </li>
        ))}
      </ol>
    </div>
  );
}

function DateInterpretation({ field, values, setValue, profiles }: FieldProps) {
  const column = values.column as string | undefined;
  const p = column ? profiles.get(column) : undefined;
  const ev = p?.date?.evidence ?? {};
  const dmy = ev.dmy_only ?? 0;
  const mdy = ev.mdy_only ?? 0;
  const ambiguous = ev.ambiguous ?? 0;
  const value = values[field.name] as string | undefined;

  // Pre-select only what the evidence supports; with no evidence the user must choose. Re-runs when the
  // column profile arrives (it loads separately from the form).
  useEffect(() => {
    if (!column || value || !p) return;
    if (dmy > 0 && mdy === 0) setValue(field.name, "DMY");
    else if (mdy > 0 && dmy === 0) setValue(field.name, "MDY");
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [column, p, dmy, mdy]);

  const options = [
    { v: "DMY", label: "Day first: DD/MM/YYYY", hint: "03/04/2026 = 3 April 2026", count: dmy },
    { v: "MDY", label: "Month first: MM/DD/YYYY", hint: "03/04/2026 = 4 March 2026", count: mdy },
    { v: "YMD", label: "Year first: YYYY/MM/DD", hint: "2026/04/03 = 3 April 2026" },
    { v: "excel_serial_1900", label: "Excel serial numbers (Windows)", hint: "45658 = 1 January 2025" },
    { v: "excel_serial_1904", label: "Excel serial numbers (old Mac 1904 system)", hint: "Rare" },
  ];

  return (
    <fieldset className="space-y-2" data-testid="date-interpretation">
      <legend className="text-sm font-medium">{field.label}</legend>
      {column && p?.date && (
        <div className="rounded-md bg-muted px-3 py-2 text-xs">
          <p className="font-medium text-foreground">Evidence in “{column}”</p>
          <p>
            {formatInteger(dmy)} value(s) only make sense day-first · {formatInteger(mdy)} only month-first ·{" "}
            <span className={ambiguous ? "font-semibold text-warning-text" : ""}>{formatInteger(ambiguous)} ambiguous</span>
          </p>
          {dmy > 0 && mdy > 0 && (
            <p className="mt-1 text-warning-text">
              This column mixes both orders. Values that contradict your choice will be reported, not changed.
            </p>
          )}
          {ambiguous > 0 && dmy === 0 && mdy === 0 && (
            <p className="mt-1 text-warning-text">There is no evidence either way. Please choose how your source system writes dates.</p>
          )}
        </div>
      )}
      <RadioGroup value={value ?? ""} onValueChange={(v) => setValue(field.name, v)} aria-label={field.label}>
        {options.map((o) => (
          <label key={o.v} className="flex cursor-pointer items-start gap-2 text-sm">
            <RadioGroupItem value={o.v} className="mt-0.5" />
            <span>
              {o.label}
              <span className="block text-xs text-muted-foreground">
                {o.hint}
                {o.count !== undefined && o.count > 0 && ` · supported by ${formatInteger(o.count)} value(s)`}
              </span>
            </span>
          </label>
        ))}
      </RadioGroup>
    </fieldset>
  );
}
