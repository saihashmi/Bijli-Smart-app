import type { Metadata } from "next";
import Link from "next/link";
import { Zap } from "lucide-react";
import "./globals.css";

export const metadata: Metadata = {
  title: "Bijli Smart",
  description: "Upload electricity meter or bill data, clean it, and find where you can save.",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body className="min-h-screen font-sans">
        <header className="sticky top-0 z-30 border-b bg-background/85 backdrop-blur">
          <div className="mx-auto flex h-14 max-w-7xl items-center gap-3 px-4 sm:px-6">
            <Link href="/" className="flex items-center gap-2 font-semibold">
              <span className="grid h-8 w-8 place-items-center rounded-lg bg-primary text-primary-foreground">
                <Zap className="h-4 w-4" fill="currentColor" />
              </span>
              Bijli Smart
            </Link>
            <span className="hidden text-sm text-muted-foreground sm:inline">· electricity data, cleaned and explained</span>
          </div>
        </header>
        <main className="mx-auto max-w-7xl px-4 py-6 sm:px-6 sm:py-8">{children}</main>
        <footer className="mx-auto max-w-7xl px-4 pb-8 text-xs text-muted-foreground sm:px-6">
          Every figure is computed from the data you upload. AI, when enabled, only explains those figures.
        </footer>
      </body>
    </html>
  );
}
