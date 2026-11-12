import Link from "next/link";
import {
  ArrowRight, BarChart3, Bot, CalendarCheck, CopyX, FileDown, HeartPulse, History, Landmark, Lock,
  ServerCog, ShieldCheck, Stethoscope, Store, Timer, Users,
} from "lucide-react";
import { CompareSlider } from "@/components/marketing/compare-slider";
import { HeroVisual } from "@/components/marketing/hero-visual";
import { StoryFlow } from "@/components/marketing/story-flow";
import { Button } from "@/components/ui/button";
import { Reveal } from "@/components/ui/reveal";

const FEATURES = [
  { icon: HeartPulse, title: "Data Health Score", text: "A 0–100 score built from completeness, duplicates, type and format consistency. The formula is always shown." },
  { icon: CalendarCheck, title: "Dates handled honestly", text: "Is 03/04/2026 the 3rd of April or the 4th of March? You see the evidence and decide. Nothing is guessed." },
  { icon: CopyX, title: "Duplicates, your way", text: "Remove exact copies, or check repeats on the columns you choose. Repeated IDs are never assumed to be errors." },
  { icon: History, title: "Undo and audit trail", text: "Every change is previewed, counted and logged. Undo a step or reset to the original at any time." },
  { icon: Bot, title: "AI that doesn't make up numbers", text: "Answers are calculated from your data. AI only explains results that have already been verified." },
  { icon: FileDown, title: "Ready-to-share exports", text: "A cleaned Excel workbook with a quality report and audit log, or a PDF report stamped in your time zone." },
];

const PRIVACY = [
  { icon: ServerCog, text: "Your files are processed on the server you run. They are not sent to a third party." },
  { icon: Lock, text: "No spreadsheet rows are ever sent to an AI service. Only column types and calculated totals, and only if you turn AI on." },
  { icon: Timer, text: "Uploaded files are deleted automatically after 7 days by default, or immediately when you choose." },
  { icon: ShieldCheck, text: "Formulas and macros inside your files are never run." },
];

const AUDIENCES = [
  { icon: BarChart3, title: "Business analysts", text: "Turn weekly exports from different systems into one consistent table before you report on it." },
  { icon: Landmark, title: "Finance teams", text: "Catch duplicate transactions, text-formatted amounts and mixed date formats before month-end." },
  { icon: Stethoscope, title: "Healthcare analysts", text: "Quality-check claims and utilisation extracts, with identifiers flagged and kept away from AI." },
  { icon: Users, title: "HR departments", text: "Clean attendance and leave sheets: blank cells, repeated employee-days, department names spelled five ways." },
  { icon: Store, title: "Small businesses", text: "Understand your sales and expenses without advanced Excel skills or an analyst on staff." },
];

function SectionHeading({ eyebrow, title, text }: { eyebrow: string; title: string; text?: string }) {
  return (
    <Reveal className="mx-auto max-w-2xl text-center">
      <p className="text-xs font-semibold tracking-[0.2em] text-cyan-text uppercase">{eyebrow}</p>
      <h2 className="mt-3 text-3xl font-semibold tracking-tight text-white sm:text-4xl">{title}</h2>
      {text && <p className="mt-3 text-slate-300">{text}</p>}
    </Reveal>
  );
}

export default function LandingPage() {
  return (
    <>
      {/* 1. Hero */}
      <section className="relative overflow-hidden">
        <div className="mx-auto grid min-h-[calc(100svh-4rem)] max-w-7xl items-center gap-8 px-4 py-14 sm:px-6 lg:grid-cols-[minmax(0,1fr)_minmax(0,1.15fr)] lg:py-10">
          <div className="space-y-7">
            <p className="hairline inline-flex items-center gap-2 rounded-full bg-white/5 px-3 py-1 text-xs font-medium text-slate-200">
              <span className="size-1.5 rounded-full bg-teal" aria-hidden /> Data cleaning · analytics · reports, without code
            </p>
            <h1 className="text-[clamp(2.5rem,5.4vw,4.25rem)] leading-[1.05] font-bold tracking-tight text-white">
              Your Data Has Potential. <span className="text-gradient">Let&rsquo;s Unlock It.</span>
            </h1>
            <p className="max-w-xl text-lg leading-relaxed text-slate-300">
              Clean messy spreadsheets, uncover insights, and create powerful dashboards with DataDoctor AI.
            </p>
            <div className="flex flex-wrap gap-3">
              <Button asChild size="xl" variant="gradient">
                <Link href="/upload">
                  Start Analyzing <ArrowRight />
                </Link>
              </Button>
              <Button asChild size="xl" variant="glass">
                <Link href="#features">Explore Features</Link>
              </Button>
            </div>
            <p className="text-sm text-slate-400">No sign-up. Runs on your own computer. Your original file is never changed.</p>
          </div>
          <HeroVisual />
        </div>
      </section>

      {/* 2. Transformation story */}
      <section id="how-it-works" className="scroll-mt-20 border-t border-white/10">
        <div className="mx-auto max-w-7xl space-y-12 px-4 py-20 sm:px-6">
          <SectionHeading eyebrow="How it works" title="From upload to answer in five steps" text="The same order you would work in Excel. Faster, and with an undo button." />
          <StoryFlow />
        </div>
      </section>

      {/* 3. Before and after */}
      <section id="before-after" className="scroll-mt-20 border-t border-white/10 bg-white/[0.02]">
        <div className="mx-auto max-w-5xl space-y-10 px-4 py-20 sm:px-6">
          <SectionHeading
            eyebrow="Before and after"
            title="See what cleaning actually changes"
            text="Drag the handle, or use the arrow keys. Highlighted cells on the left are problems DataDoctor finds and explains."
          />
          <Reveal>
            <CompareSlider />
          </Reveal>
        </div>
      </section>

      {/* Features */}
      <section id="features" className="scroll-mt-20 border-t border-white/10">
        <div className="mx-auto max-w-7xl space-y-12 px-4 py-20 sm:px-6">
          <SectionHeading eyebrow="Features" title="Built for real spreadsheets" text="Inconsistent dates, duplicate records, numbers stored as text, categories spelled five ways." />
          <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
            {FEATURES.map((f, i) => (
              <Reveal key={f.title} delay={(i % 3) * 0.08}>
                <div className="hairline glass h-full rounded-2xl p-6 transition-all duration-200 hover:-translate-y-1 hover:shadow-glow">
                  <span className="grid size-11 place-items-center rounded-xl bg-white/5 text-cyan">
                    <f.icon className="size-5" aria-hidden />
                  </span>
                  <h3 className="mt-4 font-semibold text-white">{f.title}</h3>
                  <p className="mt-2 text-sm leading-relaxed text-slate-300">{f.text}</p>
                </div>
              </Reveal>
            ))}
          </div>
        </div>
      </section>

      {/* Privacy */}
      <section id="privacy" className="scroll-mt-20 border-t border-white/10 bg-white/[0.02]">
        <div className="mx-auto grid max-w-7xl gap-10 px-4 py-20 sm:px-6 lg:grid-cols-2">
          <Reveal>
            <p className="text-xs font-semibold tracking-[0.2em] text-cyan-text uppercase">Privacy</p>
            <h2 className="mt-3 text-3xl font-semibold tracking-tight text-white sm:text-4xl">Your data stays yours</h2>
            <p className="mt-3 max-w-md text-slate-300">
              Designed for files that hold business, financial, HR and health information. Privacy is the default, not a
              setting you have to find.
            </p>
          </Reveal>
          <ul className="space-y-4">
            {PRIVACY.map((p, i) => (
              <Reveal key={p.text} delay={i * 0.06}>
                <li className="hairline flex gap-3 rounded-xl bg-white/[0.03] p-4 text-slate-200">
                  <p.icon className="mt-0.5 size-5 shrink-0 text-teal" aria-hidden />
                  <span>{p.text}</span>
                </li>
              </Reveal>
            ))}
          </ul>
        </div>
      </section>

      {/* 7. Who it's for */}
      <section id="who" className="scroll-mt-20 border-t border-white/10">
        <div className="mx-auto max-w-7xl space-y-12 px-4 py-20 sm:px-6">
          <SectionHeading eyebrow="Who it's for" title="Made for people who live in spreadsheets" />
          <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-5">
            {AUDIENCES.map((a, i) => (
              <Reveal key={a.title} delay={i * 0.06}>
                <div className="hairline h-full rounded-2xl bg-white/[0.03] p-5 transition-colors duration-200 hover:bg-white/[0.06]">
                  <a.icon className="size-6 text-cyan" aria-hidden />
                  <h3 className="mt-3 font-semibold text-white">{a.title}</h3>
                  <p className="mt-1.5 text-sm leading-relaxed text-slate-300">{a.text}</p>
                </div>
              </Reveal>
            ))}
          </div>
        </div>
      </section>

      {/* 8. Final CTA */}
      <section className="border-t border-white/10">
        <div className="mx-auto max-w-4xl px-4 py-24 text-center sm:px-6">
          <Reveal>
            <h2 className="text-4xl leading-tight font-bold tracking-tight text-white sm:text-5xl">
              Stop Cleaning Spreadsheets. <span className="text-gradient">Start Making Decisions.</span>
            </h2>
            <p className="mx-auto mt-4 max-w-xl text-slate-300">Upload a file and see exactly what needs fixing.</p>
            <Button asChild size="xl" variant="gradient" className="mt-8">
              <Link href="/upload">
                Launch DataDoctor AI <ArrowRight />
              </Link>
            </Button>
          </Reveal>
        </div>
      </section>
    </>
  );
}
