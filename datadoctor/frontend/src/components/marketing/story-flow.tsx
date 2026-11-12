"use client";

import { motion, useReducedMotion } from "motion/react";
import { BarChart3, FileDown, HeartPulse, Upload, Wand2 } from "lucide-react";

const STEPS = [
  { icon: Upload, title: "Upload", text: "Drop in an Excel or CSV file. Pick the worksheet and the header row." },
  { icon: HeartPulse, title: "Diagnose", text: "Every column is checked. You get a health score and a list of exact problems." },
  { icon: Wand2, title: "Clean", text: "Preview each fix on your full data, apply it, undo it. The original is never changed." },
  { icon: BarChart3, title: "Analyze", text: "Ask questions and build charts. Every number is calculated from your data." },
  { icon: FileDown, title: "Export", text: "Download a cleaned workbook with an audit log, or a ready-to-share PDF report." },
];

/** Upload → Diagnose → Clean → Analyze → Export, joined by a line that draws itself as the section scrolls into view. */
export function StoryFlow() {
  const reduce = useReducedMotion();
  return (
    <div className="relative">
      <svg className="pointer-events-none absolute top-9 right-[10%] left-[10%] hidden h-2 lg:block" viewBox="0 0 100 2" preserveAspectRatio="none" aria-hidden>
        <motion.line
          x1="0"
          y1="1"
          x2="100"
          y2="1"
          stroke="url(#story-grad)"
          strokeWidth="1.5"
          vectorEffect="non-scaling-stroke"
          initial={reduce ? false : { pathLength: 0 }}
          whileInView={{ pathLength: 1 }}
          viewport={{ once: true, margin: "-80px" }}
          transition={{ duration: 1.4, ease: "easeInOut" }}
        />
        <defs>
          <linearGradient id="story-grad" x1="0" x2="1" y1="0" y2="0">
            <stop offset="0" stopColor="#3B82F6" />
            <stop offset="0.5" stopColor="#22D3EE" />
            <stop offset="1" stopColor="#14B8A6" />
          </linearGradient>
        </defs>
      </svg>
      <ol className="relative grid gap-4 sm:grid-cols-2 lg:grid-cols-5">
        {STEPS.map((s, i) => (
          <motion.li
            key={s.title}
            initial={reduce ? false : { opacity: 0, y: 18 }}
            whileInView={{ opacity: 1, y: 0 }}
            viewport={{ once: true, margin: "-60px" }}
            transition={{ duration: 0.45, delay: i * 0.12, ease: [0.22, 1, 0.36, 1] }}
            className="group"
          >
            <div className="hairline glass h-full rounded-2xl p-5 transition-transform duration-200 group-hover:-translate-y-1">
              <div className="flex items-center gap-3">
                <span className="grid size-10 place-items-center rounded-xl bg-brand-gradient text-white shadow-glow">
                  <s.icon className="size-5" aria-hidden />
                </span>
                <span className="text-xs font-semibold tracking-wider text-slate-400">STEP {i + 1}</span>
              </div>
              <h3 className="mt-4 text-lg font-semibold text-white">{s.title}</h3>
              <p className="mt-1.5 text-sm leading-relaxed text-slate-300">{s.text}</p>
            </div>
          </motion.li>
        ))}
      </ol>
    </div>
  );
}
