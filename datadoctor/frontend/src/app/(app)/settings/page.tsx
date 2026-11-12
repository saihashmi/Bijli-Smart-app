import type { Metadata } from "next";
import { BackendStatus } from "@/components/backend-status";
import { LocalModeBadge } from "@/components/layout/local-mode-badge";
import { PageHeader } from "@/components/layout/page-header";
import { ThemeSwitcher } from "@/components/theme-switcher";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";

export const metadata: Metadata = { title: "Settings" };

function Pending({ milestone }: { milestone: number }) {
  return <Badge variant="warning">Milestone {milestone}</Badge>;
}

export default function SettingsPage() {
  return (
    <>
      <PageHeader title="Settings" description="Appearance, privacy and system information." />
      <div className="grid gap-6 lg:grid-cols-2">
        <Card>
          <CardHeader>
            <CardTitle>Appearance</CardTitle>
            <CardDescription>Choose a theme or follow your device setting. Saved in this browser.</CardDescription>
          </CardHeader>
          <CardContent>
            <ThemeSwitcher />
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle>System status</CardTitle>
            <CardDescription>Live check of the DataDoctor server and AI provider.</CardDescription>
          </CardHeader>
          <CardContent className="space-y-3 text-sm">
            <BackendStatus />
            <p className="text-muted-foreground">
              AI is optional. Without a key, every analysis still works and answers are computed locally.
            </p>
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              Access mode <LocalModeBadge />
            </CardTitle>
            <CardDescription>
              DataDoctor AI runs for a single user on this computer. There are no user accounts yet, so it must not be
              hosted publicly with private data.
            </CardDescription>
          </CardHeader>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              Data, privacy and limits <Pending milestone={3} />
            </CardTitle>
            <CardDescription>
              Display time zone (default Asia/Karachi), date display format, retention period, file limits, AI privacy
              switches and &ldquo;Delete all my data&rdquo; will appear here once the server settings API is built.
            </CardDescription>
          </CardHeader>
        </Card>
      </div>
    </>
  );
}
