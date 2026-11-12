"use client";

import { useEffect, useState } from "react";
import dynamic from "next/dynamic";
import { cn } from "@/lib/utils";
import { HeroFallback } from "./hero-fallback";

// The 3D scene is a separate chunk, loaded only here and only after the page has painted.
const HeroScene = dynamic(() => import("./hero-scene"), { ssr: false });

type Mode = "static" | "3d";

function canRender3D(): boolean {
  try {
    if (window.matchMedia("(prefers-reduced-motion: reduce)").matches) return false;
    const nav = navigator as Navigator & { connection?: { saveData?: boolean }; deviceMemory?: number };
    if (nav.connection?.saveData) return false;
    if ((nav.hardwareConcurrency ?? 4) <= 2) return false;
    const canvas = document.createElement("canvas");
    return Boolean(canvas.getContext("webgl2") || canvas.getContext("webgl"));
  } catch {
    return false;
  }
}

/**
 * Hero visual: the static illustration paints immediately; if the device is capable and the user has not
 * asked for reduced motion, the interactive 3D scene loads and cross-fades in. Decorative: described in text.
 */
export function HeroVisual({ className }: { className?: string }) {
  const [mode, setMode] = useState<Mode>("static");
  const [ready, setReady] = useState(false);
  const [compact, setCompact] = useState(false);

  useEffect(() => {
    setCompact(window.innerWidth < 768);
    if (!canRender3D()) return;
    // Wait until the browser is idle so the headline and buttons are interactive first.
    const start = () => setMode("3d");
    const w = window as Window & { requestIdleCallback?: (cb: () => void, o?: { timeout: number }) => number };
    if (w.requestIdleCallback) w.requestIdleCallback(start, { timeout: 1500 });
    else setTimeout(start, 300);
  }, []);

  return (
    <div
      className={cn("relative aspect-[16/11] w-full lg:aspect-[16/12]", className)}
      data-testid="hero-visual"
      data-hero-mode={mode === "3d" && ready ? "3d" : "static"}
    >
      <p className="sr-only">
        Illustration: scattered, mis-formatted spreadsheet cells travel through a glowing processing core and arrive as a
        clean, aligned table, from which a bar chart and a trend line rise.
      </p>
      <HeroFallback
        className={cn("absolute inset-0 size-full transition-opacity duration-700", mode === "3d" && ready ? "opacity-0" : "opacity-100")}
      />
      {mode === "3d" && (
        <div className={cn("absolute inset-0 transition-opacity duration-700", ready ? "opacity-100" : "opacity-0")} aria-hidden>
          <HeroScene compact={compact} onReady={() => setReady(true)} />
        </div>
      )}
    </div>
  );
}
