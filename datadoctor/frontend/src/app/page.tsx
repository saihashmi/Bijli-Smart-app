import { BackendStatus } from "@/components/backend-status";
import { Button } from "@/components/ui/button";

// Milestone 1 development page: proves the toolchain, theme tokens, font and API proxy work.
// The real landing page is built in Milestone 2.
export default function Home() {
  return (
    <main className="mx-auto flex min-h-screen max-w-2xl flex-col justify-center gap-6 px-4 py-16">
      <div className="space-y-2">
        <p className="text-sm font-medium text-teal">Development build · Milestone 1</p>
        <h1 className="text-4xl font-bold tracking-tight text-navy dark:text-foreground">DataDoctor AI</h1>
        <p className="text-lg text-muted-foreground">From Messy Data to Meaningful Decisions.</p>
      </div>
      <div className="rounded-xl border bg-card p-5 shadow-sm">
        <h2 className="mb-2 font-semibold">Environment check</h2>
        <BackendStatus />
      </div>
      <div>
        <Button asChild>
          <a href="/api/docs">Open API documentation</a>
        </Button>
      </div>
    </main>
  );
}
