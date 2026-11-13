"use client";

import { useEffect, useRef, useState } from "react";
import { useTheme } from "next-themes";
import { Bot, Calculator, CircleHelp, CornerDownLeft, Info, ListChecks, Loader2, ShieldCheck, Sparkles, User } from "lucide-react";
import { ApiError } from "@/lib/api";
import { analytics, type Field } from "@/lib/analytics";
import { analyst, describeParams, type AskResponse, type Catalogue, type Interaction, type Suggestion } from "@/lib/analyst";
import { CHART_THEMES } from "@/lib/chart-theme";
import { useAnalysisSession } from "@/components/session/session-context";
import { ChartBody } from "@/components/dashboard/charts";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Skeleton } from "@/components/ui/skeleton";
import { GuidedBuilder } from "./guided-builder";

type Turn = { key: number; asked: string; response: AskResponse | null; error: string | null };

function AnswerCard({ turn, onAlternative }: { turn: Turn; onAlternative: (s: Suggestion) => void }) {
  const { resolvedTheme } = useTheme();
  const theme = CHART_THEMES[resolvedTheme === "dark" ? "midnight" : "executive"];
  const r = turn.response;
  if (turn.error)
    return (
      <p className="rounded-2xl border border-destructive/40 bg-card p-4 text-sm text-destructive-text" role="alert">
        {turn.error}
      </p>
    );
  if (!r)
    return (
      <div className="flex items-center gap-2 rounded-2xl border bg-card p-4 text-sm text-muted-foreground" role="status">
        <Loader2 className="size-4 animate-spin" aria-hidden />
        Calculating from your data…
      </div>
    );

  if (r.status === "cannot_answer")
    return (
      <div className="space-y-3 rounded-2xl border bg-card p-4" data-testid="cannot-answer">
        <p className="flex items-start gap-2 text-sm">
          <CircleHelp className="mt-0.5 size-4 shrink-0 text-warning" aria-hidden />
          <span>{r.message}</span>
        </p>
        {r.notices.map((n) => (
          <p key={n} className="text-xs text-muted-foreground">
            {n}
          </p>
        ))}
        {r.alternatives.length > 0 && (
          <div className="space-y-1.5">
            <p className="text-xs font-medium text-muted-foreground">Questions I can answer about this data:</p>
            <div className="flex flex-wrap gap-2">
              {r.alternatives.map((a) => (
                <Button key={a.question} variant="outline" size="sm" className="h-auto py-1.5 whitespace-normal" onClick={() => onAlternative(a)}>
                  {a.question}
                </Button>
              ))}
            </div>
          </div>
        )}
      </div>
    );

  const a = r.answer!;
  const how = r.interpreter === "groq" ? "Question understood by AI" : r.interpreter === "local" ? "Question understood by built-in rules" : "Chosen in the guided builder";
  return (
    <article className="space-y-4 rounded-2xl border bg-card p-4 sm:p-5" data-testid="answer" data-operation={a.operation}>
      <section aria-label="Computed result" className="space-y-3">
        <div className="flex flex-wrap items-center gap-2">
          <Badge variant="secondary" className="gap-1">
            <Calculator className="size-3" aria-hidden />
            Computed result
          </Badge>
          <span className="text-xs text-muted-foreground">Calculated on the server from your full data</span>
        </div>
        <p className="text-base leading-relaxed" data-testid="answer-text">
          {a.answer}
        </p>
        {a.chart && (
          <div className="h-64 rounded-xl border p-3" style={{ background: theme.card, borderColor: theme.cardBorder }}>
            <ChartBody chart={a.chart.chart} result={a.chart.result} theme={theme} />
          </div>
        )}
        {a.table && a.table.rows.length > 0 && (
          <details className="group rounded-xl border" open={!a.chart}>
            <summary className="cursor-pointer rounded-xl px-3 py-2 text-sm font-medium outline-none focus-visible:ring-2 focus-visible:ring-ring">
              Figures ({a.table.rows.length} {a.table.rows.length === 1 ? "row" : "rows"})
            </summary>
            <div className="max-h-72 overflow-auto border-t" tabIndex={0} role="region" aria-label="Figures">
              <table className="w-full text-left text-sm" data-testid="answer-table">
                <thead className="text-xs text-muted-foreground">
                  <tr>
                    {a.table.columns.map((c) => (
                      <th key={c} className="px-3 py-2 font-medium">
                        {c}
                      </th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {a.table.rows.map((row, i) => (
                    <tr key={i} className="border-t">
                      {row.map((c, j) => (
                        <td key={j} className={j ? "px-3 py-1.5 tabular-nums" : "px-3 py-1.5"}>
                          {c}
                        </td>
                      ))}
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </details>
        )}
        {a.notes.length > 0 && (
          <ul className="space-y-0.5 text-xs text-muted-foreground" data-testid="answer-notes">
            {a.notes.map((n) => (
              <li key={n} className="flex gap-1.5">
                <Info className="mt-0.5 size-3 shrink-0" aria-hidden />
                {n}
              </li>
            ))}
          </ul>
        )}
      </section>

      {r.explanation && (
        <section aria-label="AI explanation" className="space-y-1.5 rounded-xl border border-violet/40 bg-violet/5 p-3" data-testid="ai-explanation">
          <p className="flex flex-wrap items-center gap-2 text-xs font-medium">
            <Sparkles className="size-3.5 text-violet" aria-hidden />
            AI explanation · {r.explanation.provider} · {r.explanation.model}
            <span className="inline-flex items-center gap-1 text-success-text">
              <ShieldCheck className="size-3.5" aria-hidden />
              checked against the computed result
            </span>
          </p>
          <p className="text-sm leading-relaxed">{r.explanation.text}</p>
        </section>
      )}

      {r.notices.map((n) => (
        <p key={n} className="flex gap-1.5 text-xs text-muted-foreground" data-testid="answer-notice">
          <Info className="mt-0.5 size-3 shrink-0" aria-hidden />
          {n}
        </p>
      ))}

      <footer className="border-t pt-3 text-xs text-muted-foreground" data-testid="answer-how">
        <p className="mb-1.5">
          {how}. Calculation used: <span className="font-medium text-foreground">{a.title}</span>
        </p>
        <dl className="flex flex-wrap gap-1.5">
          {describeParams(a.params).map((p) => (
            <div key={p.label} className="rounded-md border bg-muted px-2 py-0.5">
              <dt className="inline">{p.label}: </dt>
              <dd className="inline font-medium text-foreground">{p.value}</dd>
            </div>
          ))}
        </dl>
      </footer>
    </article>
  );
}

export function AnalystStudio() {
  const { session } = useAnalysisSession();
  const sid = session.id;
  const [catalogue, setCatalogue] = useState<Catalogue | null>(null);
  const [fields, setFields] = useState<Field[]>([]);
  const [suggestions, setSuggestions] = useState<Suggestion[]>([]);
  const [history, setHistory] = useState<Interaction[]>([]);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [turns, setTurns] = useState<Turn[]>([]);
  const [text, setText] = useState("");
  const [busy, setBusy] = useState(false);
  const counter = useRef(0);
  const end = useRef<HTMLDivElement>(null);

  useEffect(() => {
    let stale = false;
    Promise.all([analyst.catalogue(), analytics.fields(sid), analyst.suggestions(sid), analyst.history(sid)])
      .then(([c, f, s, h]) => {
        if (stale) return;
        setCatalogue(c);
        setFields(f.fields.filter((x) => !x.sensitive));
        setSuggestions(s.suggestions);
        setHistory(h.interactions);
      })
      .catch((e) => !stale && setLoadError(e instanceof ApiError ? e.message : "The AI Analyst could not be loaded."));
    return () => {
      stale = true;
    };
  }, [sid]);

  const send = async (asked: string, body: { question?: string; operation?: string; params?: Record<string, unknown> }) => {
    if (busy) return;
    const key = ++counter.current;
    setBusy(true);
    setTurns((t) => [...t, { key, asked, response: null, error: null }]);
    requestAnimationFrame(() => end.current?.scrollIntoView({ block: "end", behavior: "smooth" }));
    try {
      const response = await analyst.ask(sid, body);
      setTurns((t) => t.map((x) => (x.key === key ? { ...x, response } : x)));
    } catch (e) {
      const error = e instanceof ApiError ? (e.status === 429 ? "Too many questions in a short time. Please wait a moment and try again." : e.message) : "The question could not be sent.";
      setTurns((t) => t.map((x) => (x.key === key ? { ...x, error } : x)));
    } finally {
      setBusy(false);
      requestAnimationFrame(() => end.current?.scrollIntoView({ block: "end", behavior: "smooth" }));
    }
  };

  const askText = () => {
    const q = text.trim();
    if (!q) return;
    setText("");
    void send(q, { question: q });
  };
  const askSuggestion = (s: Suggestion) => void send(s.question, { operation: s.operation, params: s.params });

  if (loadError)
    return (
      <p className="rounded-2xl border border-destructive/40 bg-card p-4 text-sm text-destructive-text" role="alert">
        {loadError}
      </p>
    );
  if (!catalogue)
    return (
      <div className="grid gap-4 xl:grid-cols-[minmax(0,1fr)_22rem]" role="status" aria-label="Loading AI Analyst">
        <Skeleton className="h-96 rounded-2xl" />
        <Skeleton className="h-96 rounded-2xl" />
      </div>
    );

  const ai = catalogue.ai;
  return (
    <div className="grid items-start gap-4 xl:grid-cols-[minmax(0,1fr)_22rem]" data-testid="analyst-studio">
      <div className="min-w-0 space-y-4">
        <div className="flex flex-wrap items-center gap-2 rounded-2xl border bg-card px-4 py-3 text-sm" data-testid="analyst-mode">
          <Bot className="size-4 text-primary dark:text-link" aria-hidden />
          {ai.configured ? (
            <span>
              Questions are interpreted by <span className="font-medium">{ai.provider}</span> ({ai.model}). It only sees your question, column names and
              types, and computed summaries. Never your rows.
            </span>
          ) : (
            <span>
              Using the <span className="font-medium">built-in interpreter</span>. No AI service is connected and nothing leaves this computer.
            </span>
          )}
        </div>

        <div className="space-y-4" aria-live="polite" data-testid="thread">
          {turns.length === 0 && (
            <div className="space-y-3 rounded-2xl border border-dashed bg-card/50 p-5">
              <p className="font-medium">Ask a question about {session.original_filename}</p>
              <p className="text-sm text-muted-foreground">
                Every answer is calculated from your data by a fixed list of calculations. These questions were generated from your column types:
              </p>
              <div className="flex flex-wrap gap-2" data-testid="suggestions">
                {suggestions.map((s) => (
                  <Button key={s.question} variant="outline" size="sm" className="h-auto py-1.5 text-left whitespace-normal" disabled={busy} onClick={() => askSuggestion(s)}>
                    {s.question}
                  </Button>
                ))}
              </div>
            </div>
          )}
          {turns.map((t) => (
            <div key={t.key} className="space-y-2">
              <p className="ml-auto flex w-fit max-w-[85%] items-start gap-2 rounded-2xl rounded-br-md bg-primary px-4 py-2 text-sm text-primary-foreground" data-testid="question">
                <User className="mt-0.5 size-4 shrink-0" aria-hidden />
                <span className="break-words">{t.asked}</span>
              </p>
              <AnswerCard turn={t} onAlternative={askSuggestion} />
            </div>
          ))}
          <div ref={end} />
        </div>

        <form
          className="sticky bottom-3 flex gap-2 rounded-2xl border bg-card p-2 shadow-lg"
          onSubmit={(e) => {
            e.preventDefault();
            askText();
          }}
        >
          <label htmlFor="analyst-question" className="sr-only">
            Your question
          </label>
          <Input
            id="analyst-question"
            value={text}
            onChange={(e) => setText(e.target.value)}
            maxLength={500}
            placeholder="For example: Which region has the highest total amount?"
            className="h-11 border-0 shadow-none focus-visible:ring-0"
            autoComplete="off"
          />
          <Button type="submit" size="lg" disabled={busy || !text.trim()}>
            {busy ? <Loader2 className="animate-spin" aria-hidden /> : <CornerDownLeft aria-hidden />}
            Ask
          </Button>
        </form>
      </div>

      <aside className="space-y-4">
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2 text-base">
              <ListChecks className="size-4" aria-hidden />
              Guided builder
            </CardTitle>
          </CardHeader>
          <CardContent>
            <p className="mb-3 text-sm text-muted-foreground">Pick a calculation and its columns directly. No typing, no interpretation.</p>
            <GuidedBuilder operations={catalogue.operations} fields={fields} busy={busy} onRun={(operation, params, label) => void send(label, { operation, params })} />
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle className="text-base">What this assistant can and cannot do</CardTitle>
          </CardHeader>
          <CardContent>
            <ul className="list-disc space-y-1.5 pl-4 text-sm text-muted-foreground" data-testid="limitations">
              {catalogue.limitations.map((l) => (
                <li key={l}>{l}</li>
              ))}
            </ul>
          </CardContent>
        </Card>

        {history.length > 0 && (
          <Card>
            <CardHeader>
              <CardTitle className="text-base">Earlier questions</CardTitle>
            </CardHeader>
            <CardContent>
              <ul className="space-y-2" data-testid="history">
                {history.slice(0, 8).map((h) => (
                  <li key={h.id}>
                    <button
                      type="button"
                      disabled={busy}
                      className="w-full cursor-pointer rounded-lg border px-3 py-2 text-left text-sm outline-none transition-colors hover:bg-accent focus-visible:ring-2 focus-visible:ring-ring disabled:cursor-not-allowed disabled:opacity-60"
                      onClick={() => (h.operation ? void send(h.question, { operation: h.operation, params: h.params }) : void send(h.question, { question: h.question }))}
                    >
                      <span className="line-clamp-2 font-medium">{h.question}</span>
                      <span className="line-clamp-1 text-xs text-muted-foreground">{h.operation ? "Run again on the current data" : "Could not be answered"}</span>
                    </button>
                  </li>
                ))}
              </ul>
            </CardContent>
          </Card>
        )}
      </aside>
    </div>
  );
}
