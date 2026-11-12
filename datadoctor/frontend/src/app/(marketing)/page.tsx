import Link from "next/link";
import {
  ArrowRight,
  BarChart3,
  Bot,
  CalendarCheck,
  CopyX,
  FileDown,
  FileSpreadsheet,
  HeartPulse,
  History,
  Lock,
  ServerCog,
  ShieldCheck,
  Timer,
  Upload,
  Wand2,
} from "lucide-react";
import { Button } from "@/components/ui/button";

const STEPS = [
  { icon: Upload, title: "Upload", text: "Excel (.xlsx, .xls) or CSV. Pick the worksheet and header row." },
  { icon: HeartPulse, title: "Profile", text: "Every column checked for missing values, duplicates, wrong types and messy formats." },
  { icon: Wand2, title: "Clean", text: "Apply safe, previewed fixes. Undo anything. The original file is never changed." },
  { icon: BarChart3, title: "Analyze", text: "Ask questions in plain English. Answers are calculated from your data, not guessed." },
  { icon: FileSpreadsheet, title: "Visualize", text: "An automatic first dashboard, then adjust charts, filters and groupings." },
  { icon: FileDown, title: "Export", text: "A cleaned Excel workbook with quality report and audit log, or a PDF report." },
];

const FEATURES = [
  { icon: HeartPulse, title: "Data Health Score", text: "A 0–100 score from completeness, duplicates, type and format consistency, with the formula always shown." },
  { icon: CalendarCheck, title: "Dates handled honestly", text: "Is 03/04/2026 the 3rd of April or the 4th of March? DataDoctor asks you instead of guessing." },
  { icon: CopyX, title: "Duplicates, your way", text: "Remove exact copies, or check repeats on the columns you choose. Repeated IDs are never assumed to be errors." },
  { icon: History, title: "Undo and audit trail", text: "Every change is previewed, counted, logged and reversible. Reset to the original at any time." },
  { icon: Bot, title: "AI that doesn't make up numbers", text: "AI only explains results that DataDoctor has already calculated. It works without any AI at all." },
  { icon: FileDown, title: "Ready-to-share exports", text: "Excel with cleaned data, quality report, audit log and statistics. PDF reports in Pakistan time." },
];

const PRIVACY = [
  { icon: ServerCog, text: "Your files are processed on the server you run, never sent to a third party." },
  { icon: Lock, text: "No spreadsheet rows are ever sent to an AI service. Only column types and calculated totals, and only if you enable AI." },
  { icon: Timer, text: "Uploaded files are deleted automatically after 7 days by default, or immediately when you choose." },
  { icon: ShieldCheck, text: "Formulas and macros in your files are never executed." },
];

function BeforeAfter() {
  // An illustration of the kinds of fixes DataDoctor makes. These are example values, not results.
  const rows = [
    ["  lahore", "Lahore"],
    ["LAHORE ", "Lahore"],
    ["Rs 1,250", "1250"],
    ["03/04/2026", "Asks: 3 Apr or 4 Mar?"],
    ["N/A", "Missing (your choice)"],
  ];
  return (
    <figure className="rounded-2xl border bg-card p-5 shadow-sm">
      <figcaption className="mb-4 flex items-center justify-between text-sm">
        <span className="font-semibold">What DataDoctor fixes</span>
        <span className="rounded-md bg-muted px-2 py-0.5 text-xs text-muted-foreground">Illustration</span>
      </figcaption>
      <table className="w-full text-sm">
        <thead>
          <tr className="text-left text-xs text-muted-foreground uppercase">
            <th className="pb-2 font-medium">Before</th>
            <th className="w-6" aria-hidden />
            <th className="pb-2 font-medium">After</th>
          </tr>
        </thead>
        <tbody className="font-mono text-[13px]">
          {rows.map(([before, after]) => (
            <tr key={before} className="border-t">
              <td className="py-2 whitespace-pre text-destructive-text">&ldquo;{before}&rdquo;</td>
              <td aria-hidden>
                <ArrowRight className="size-3.5 text-muted-foreground" />
              </td>
              <td className="py-2 text-success-text">{after}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </figure>
  );
}

export default function LandingPage() {
  return (
    <>
      <section className="mx-auto grid max-w-6xl items-center gap-10 px-4 py-16 sm:px-6 lg:grid-cols-[1.15fr_1fr] lg:py-24">
        <div className="space-y-6">
          <p className="inline-flex rounded-full border bg-card px-3 py-1 text-xs font-medium text-teal-text">
            Data cleaning · analytics · reports, without code
          </p>
          <h1 className="text-4xl leading-tight font-bold tracking-tight text-navy sm:text-5xl dark:text-foreground">
            From Messy Data to <span className="text-primary dark:text-link">Meaningful Decisions.</span>
          </h1>
          <p className="max-w-xl text-lg text-muted-foreground">
            Upload an Excel or CSV file. DataDoctor AI shows you exactly what is wrong with it, helps you fix it safely,
            and turns it into dashboards and reports you can trust.
          </p>
          <div className="flex flex-wrap gap-3">
            <Button asChild size="lg">
              <Link href="/upload">
                <Upload /> Upload a spreadsheet
              </Link>
            </Button>
            <Button asChild size="lg" variant="outline">
              <a href="#how-it-works">See how it works</a>
            </Button>
          </div>
          <p className="text-sm text-muted-foreground">
            For Excel analysts, finance, HR, operations, healthcare and insurance teams, and business owners.
          </p>
        </div>
        <BeforeAfter />
      </section>

      <section id="how-it-works" className="scroll-mt-20 border-y bg-card/60">
        <div className="mx-auto max-w-6xl px-4 py-16 sm:px-6">
          <h2 className="text-3xl font-semibold tracking-tight">How it works</h2>
          <p className="mt-2 text-muted-foreground">Six steps, in the order you would do them in Excel. Only faster and with an undo button.</p>
          <ol className="mt-8 grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
            {STEPS.map((s, i) => (
              <li key={s.title} className="rounded-xl border bg-background p-5">
                <div className="flex items-center gap-3">
                  <span className="grid size-8 place-items-center rounded-full bg-primary text-sm font-semibold text-primary-foreground">
                    {i + 1}
                  </span>
                  <s.icon className="size-5 text-teal" aria-hidden />
                  <h3 className="font-semibold">{s.title}</h3>
                </div>
                <p className="mt-3 text-sm text-muted-foreground">{s.text}</p>
              </li>
            ))}
          </ol>
        </div>
      </section>

      <section id="features" className="mx-auto max-w-6xl scroll-mt-20 px-4 py-16 sm:px-6">
        <h2 className="text-3xl font-semibold tracking-tight">Built for real spreadsheets</h2>
        <p className="mt-2 text-muted-foreground">Inconsistent dates, duplicate records, numbers stored as text, categories spelled five ways.</p>
        <div className="mt-8 grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {FEATURES.map((f) => (
            <div key={f.title} className="rounded-xl border bg-card p-5 shadow-sm">
              <span className="grid size-10 place-items-center rounded-lg bg-accent text-accent-foreground">
                <f.icon className="size-5" aria-hidden />
              </span>
              <h3 className="mt-4 font-semibold">{f.title}</h3>
              <p className="mt-2 text-sm text-muted-foreground">{f.text}</p>
            </div>
          ))}
        </div>
      </section>

      <section id="privacy" className="scroll-mt-20 bg-navy text-slate-100">
        <div className="mx-auto grid max-w-6xl gap-10 px-4 py-16 sm:px-6 lg:grid-cols-2">
          <div>
            <h2 className="text-3xl font-semibold tracking-tight text-white">Your data stays yours</h2>
            <p className="mt-3 text-slate-300">
              Designed for files that contain business, financial, HR and health information. Privacy is the default,
              not a setting you have to find.
            </p>
          </div>
          <ul className="space-y-4">
            {PRIVACY.map((p) => (
              <li key={p.text} className="flex gap-3">
                <p.icon className="mt-0.5 size-5 shrink-0 text-teal" aria-hidden />
                <span>{p.text}</span>
              </li>
            ))}
          </ul>
        </div>
      </section>

      <section className="mx-auto max-w-6xl px-4 py-16 text-center sm:px-6">
        <h2 className="text-3xl font-semibold tracking-tight">Ready to check your data&rsquo;s health?</h2>
        <p className="mt-2 text-muted-foreground">No sign-up. Runs on your own computer.</p>
        <Button asChild size="lg" className="mt-6">
          <Link href="/upload">
            <Upload /> Upload a spreadsheet
          </Link>
        </Button>
      </section>
    </>
  );
}
