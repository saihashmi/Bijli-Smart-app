import Link from "next/link";
import { Logo } from "@/components/logo";
import { SiteFooter } from "@/components/marketing/site-footer";
import { Button } from "@/components/ui/button";

// The landing page is always dark ("Midnight"): the .dark wrapper applies the dark tokens to this subtree.
export default function MarketingLayout({ children }: { children: React.ReactNode }) {
  return (
    <div className="dark bg-hero min-h-screen text-foreground">
      <Link href="#main" className="sr-only z-[60] rounded-md bg-primary px-3 py-2 text-white focus:not-sr-only focus:fixed focus:top-3 focus:left-3">
        Skip to content
      </Link>
      <header className="sticky top-0 z-30 border-b border-white/10 bg-[#080D1B]/70 backdrop-blur-md">
        <div className="mx-auto flex h-16 max-w-7xl items-center gap-4 px-4 sm:px-6">
          <Link href="/" className="rounded-md outline-none focus-visible:ring-2 focus-visible:ring-ring" aria-label="DataDoctor AI home">
            <Logo inverted />
          </Link>
          <nav aria-label="Page sections" className="ml-8 hidden items-center gap-7 text-sm text-slate-300 md:flex">
            <Link href="#how-it-works" className="transition-colors hover:text-white">How it works</Link>
            <Link href="#before-after" className="transition-colors hover:text-white">Before &amp; after</Link>
            <Link href="#features" className="transition-colors hover:text-white">Features</Link>
            <Link href="#privacy" className="transition-colors hover:text-white">Privacy</Link>
          </nav>
          <div className="ml-auto">
            <Button asChild size="sm" variant="glass">
              <Link href="/workspace">Open app</Link>
            </Button>
          </div>
        </div>
      </header>
      <main id="main">{children}</main>
      <SiteFooter />
    </div>
  );
}
