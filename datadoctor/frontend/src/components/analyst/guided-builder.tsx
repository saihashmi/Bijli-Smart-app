"use client";

import { useEffect, useId, useMemo, useState } from "react";
import { Play } from "lucide-react";
import { AGG_LABEL, type Agg, type Field } from "@/lib/analytics";
import { paramLabel, type FormField, type Operation } from "@/lib/analyst";
import { Button } from "@/components/ui/button";
import { Checkbox } from "@/components/ui/checkbox";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { NativeSelect } from "@/components/ui/native-select";

const NONE = "__none__";
const GRAINS = ["day", "week", "month", "quarter", "year"];

function columnsFor(role: FormField["role"], fields: Field[]): Field[] {
  if (role === "number") return fields.filter((f) => f.kind === "number");
  if (role === "date") return fields.filter((f) => f.kind === "date");
  if (role === "group") return fields.filter((f) => f.can_group && f.kind !== "date");
  return fields.filter((f) => f.kind !== "empty");
}

/** Every allowlisted calculation, reachable without typing a question (works with no AI key). */
export function GuidedBuilder({
  operations,
  fields,
  busy,
  onRun,
}: {
  operations: Operation[];
  fields: Field[];
  busy: boolean;
  onRun: (operation: string, params: Record<string, unknown>, label: string) => void;
}) {
  const uid = useId();
  const [opId, setOpId] = useState(operations[0]?.id ?? "");
  const [values, setValues] = useState<Record<string, unknown>>({});
  const op = operations.find((o) => o.id === opId);

  // Sensible starting values whenever the calculation changes.
  useEffect(() => {
    if (!op) return;
    const next: Record<string, unknown> = {};
    const used: string[] = [];
    for (const f of op.fields) {
      if (["any", "group", "date", "number"].includes(f.role)) {
        if (f.optional) next[f.name] = NONE;
        else {
          const pick = columnsFor(f.role, fields).find((c) => !used.includes(c.name));
          next[f.name] = pick?.name ?? "";
          if (pick) used.push(pick.name);
        }
      } else if (f.role === "agg") next[f.name] = "count";
      else if (f.role === "grain") next[f.name] = "month";
      else if (f.role === "order") next[f.name] = "desc";
      else if (f.role === "which") next[f.name] = "max";
      else if (f.role === "int") next[f.name] = "10";
      else next[f.name] = [];
    }
    setValues(next);
  }, [op, fields]);

  const set = (name: string, v: unknown) =>
    setValues((prev) => ({ ...prev, [name]: v, ...(name === "group_by" && "values" in prev ? { values: [] } : {}) }));
  const measureName = typeof values.measure === "string" && values.measure !== NONE ? values.measure : null;
  const measureField = fields.find((f) => f.name === measureName);
  const aggs: Agg[] = useMemo(() => (measureField ? measureField.aggregations : ["count"]), [measureField]);
  useEffect(() => {
    if (op?.fields.some((f) => f.role === "agg") && !aggs.includes(values.agg as Agg)) set("agg", aggs[0] ?? "count");
    // eslint-disable-next-line react-hooks/exhaustive-deps -- only when the allowed calculations change
  }, [aggs]);
  const groupField = fields.find((f) => f.name === values.group_by);

  if (!op) return null;

  let problem: string | null = null;
  for (const f of op.fields) {
    const v = values[f.name];
    if (["any", "group", "date", "number"].includes(f.role) && !f.optional && !v) problem = `This data has no column that fits “${paramLabel(f.name)}”.`;
    if (f.role === "values" && (!Array.isArray(v) || v.length < 2 || v.length > 5)) problem = "Tick 2 to 5 values to compare.";
  }
  if (op.id === "correlation" && values.x && values.x === values.y) problem = "Choose two different columns.";

  const run = () => {
    const params: Record<string, unknown> = {};
    for (const f of op.fields) {
      const v = values[f.name];
      if (v === NONE || v === "" || v === undefined) continue;
      if (f.role === "int") params[f.name] = Math.min(50, Math.max(1, Number(v) || 10));
      else if (f.role === "columns" && Array.isArray(v) && v.length === 0) continue;
      else if (f.role === "agg" && !measureName && op.fields.some((x) => x.name === "measure" && x.optional)) params[f.name] = "count";
      else params[f.name] = v;
    }
    onRun(op.id, params, op.title);
  };

  return (
    <form
      className="space-y-3"
      data-testid="guided-builder"
      onSubmit={(e) => {
        e.preventDefault();
        if (!problem && !busy) run();
      }}
    >
      <div className="space-y-1.5">
        <Label htmlFor={`${uid}-op`}>Calculation</Label>
        <NativeSelect id={`${uid}-op`} value={opId} onChange={(e) => setOpId(e.target.value)}>
          {operations.map((o) => (
            <option key={o.id} value={o.id}>
              {o.title}
            </option>
          ))}
        </NativeSelect>
        <p className="text-xs text-muted-foreground">For questions like “{op.example}”</p>
      </div>

      {op.fields.map((f) => {
        const id = `${uid}-${f.name}`;
        const label = paramLabel(f.name) + (f.optional ? " (optional)" : "");
        if (["any", "group", "date", "number"].includes(f.role)) {
          const options = columnsFor(f.role, fields);
          return (
            <div key={f.name} className="space-y-1.5">
              <Label htmlFor={id}>{label}</Label>
              <NativeSelect id={id} value={String(values[f.name] ?? "")} onChange={(e) => set(f.name, e.target.value)}>
                {f.optional && <option value={NONE}>Count rows instead</option>}
                {!f.optional && !options.length && <option value="">No suitable column</option>}
                {options.map((c) => (
                  <option key={c.name} value={c.name}>
                    {c.name} ({c.kind})
                  </option>
                ))}
              </NativeSelect>
            </div>
          );
        }
        if (f.role === "agg")
          return (
            <div key={f.name} className="space-y-1.5">
              <Label htmlFor={id}>{label}</Label>
              <NativeSelect id={id} value={String(values[f.name] ?? "count")} disabled={!measureName} onChange={(e) => set(f.name, e.target.value)}>
                {aggs.map((a) => (
                  <option key={a} value={a}>
                    {AGG_LABEL[a]}
                  </option>
                ))}
              </NativeSelect>
            </div>
          );
        if (f.role === "grain" || f.role === "order" || f.role === "which") {
          const opts =
            f.role === "grain"
              ? GRAINS.map((g) => [g, g[0].toUpperCase() + g.slice(1)])
              : f.role === "order"
                ? [
                    ["desc", "Largest first"],
                    ["asc", "Smallest first"],
                  ]
                : [
                    ["max", "Highest"],
                    ["min", "Lowest"],
                  ];
          return (
            <div key={f.name} className="space-y-1.5">
              <Label htmlFor={id}>{label}</Label>
              <NativeSelect id={id} value={String(values[f.name] ?? "")} onChange={(e) => set(f.name, e.target.value)}>
                {opts.map(([v, l]) => (
                  <option key={v} value={v}>
                    {l}
                  </option>
                ))}
              </NativeSelect>
            </div>
          );
        }
        if (f.role === "int")
          return (
            <div key={f.name} className="space-y-1.5">
              <Label htmlFor={id}>{label}</Label>
              <Input id={id} type="number" min={1} max={50} value={String(values[f.name] ?? "10")} onChange={(e) => set(f.name, e.target.value)} />
            </div>
          );
        const picked = Array.isArray(values[f.name]) ? (values[f.name] as string[]) : [];
        const options = f.role === "values" ? (groupField?.values ?? []).slice(0, 30) : fields.map((c) => c.name);
        return (
          <fieldset key={f.name} className="space-y-1.5">
            <legend className="text-sm font-medium">{f.role === "values" ? `Values of ${groupField?.name ?? "the group"} to compare` : label}</legend>
            <div className="grid max-h-36 gap-1.5 overflow-y-auto rounded-md border p-2">
              {options.map((v) => (
                <label key={v} className="flex cursor-pointer items-center gap-2 text-sm">
                  <Checkbox checked={picked.includes(v)} onCheckedChange={(on) => set(f.name, on ? [...picked, v] : picked.filter((x) => x !== v))} />
                  <span className="truncate">{v}</span>
                </label>
              ))}
              {!options.length && <p className="text-xs text-muted-foreground">Nothing to choose from.</p>}
            </div>
          </fieldset>
        );
      })}

      {problem && (
        <p className="text-xs text-muted-foreground" role="status">
          {problem}
        </p>
      )}
      <Button type="submit" className="w-full" disabled={Boolean(problem) || busy}>
        <Play aria-hidden />
        Run calculation
      </Button>
    </form>
  );
}
