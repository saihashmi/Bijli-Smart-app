"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { api } from "@/lib/api";
import { Logo } from "@/components/logo";

const CONTACT = process.env.NEXT_PUBLIC_CONTACT_EMAIL;

export function SiteFooter() {
  const [version, setVersion] = useState<string | null>(null);
  useEffect(() => {
    api.health().then((h) => setVersion(h.version)).catch(() => setVersion(null));
  }, []);
  return (
    <footer className="border-t border-white/10">
      <div className="mx-auto grid max-w-7xl gap-10 px-4 py-12 sm:px-6 md:grid-cols-[1.4fr_1fr_1fr_1fr]">
        <div className="space-y-3">
          <Logo inverted />
          <p className="max-w-xs text-sm text-slate-400">From Messy Data to Meaningful Decisions.</p>
        </div>
        <nav aria-label="Product" className="space-y-2 text-sm">
          <p className="font-semibold text-white">Product</p>
          <Link className="block text-slate-400 hover:text-white" href="/upload">Upload Studio</Link>
          <Link className="block text-slate-400 hover:text-white" href="/workspace">Overview</Link>
          <Link className="block text-slate-400 hover:text-white" href="/settings">Settings</Link>
        </nav>
        <nav aria-label="Features" className="space-y-2 text-sm">
          <p className="font-semibold text-white">Features</p>
          <Link className="block text-slate-400 hover:text-white" href="#how-it-works">How it works</Link>
          <Link className="block text-slate-400 hover:text-white" href="#before-after">Before and after</Link>
          <Link className="block text-slate-400 hover:text-white" href="#features">Capabilities</Link>
        </nav>
        <div className="space-y-2 text-sm">
          <p className="font-semibold text-white">Privacy</p>
          <Link className="block text-slate-400 hover:text-white" href="#privacy">How your data is handled</Link>
          {CONTACT && (
            <a className="block text-slate-400 hover:text-white" href={`mailto:${CONTACT}`}>
              Contact: {CONTACT}
            </a>
          )}
        </div>
      </div>
      <div className="border-t border-white/10">
        <div className="mx-auto flex max-w-7xl flex-col gap-1 px-4 py-5 text-xs text-slate-500 sm:flex-row sm:justify-between sm:px-6">
          <span>© {new Date().getFullYear()} DataDoctor AI. Runs on your own machine.</span>
          <span data-testid="footer-version">{version ? `Version ${version}` : ""}</span>
        </div>
      </div>
    </footer>
  );
}
