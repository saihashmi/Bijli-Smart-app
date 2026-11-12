import type { Metadata } from "next";
import Link from "next/link";
import { Upload } from "lucide-react";
import { ComingSoon } from "@/components/layout/coming-soon";
import { PageHeader } from "@/components/layout/page-header";
import { Button } from "@/components/ui/button";

export const metadata: Metadata = { title: "Workspace" };

export default function WorkspacePage() {
  return (
    <>
      <PageHeader
        title="Workspace"
        description="Your analysis sessions: one per uploaded worksheet."
        actions={
          <Button asChild>
            <Link href="/upload">
              <Upload /> New upload
            </Link>
          </Button>
        }
      />
      <ComingSoon
        milestone={4}
        title="Session list"
        points={[
          "Every uploaded file and worksheet you are analysing, with its row count and Data Health Score",
          "Last activity and the date each dataset is automatically deleted (7 days by default)",
          "Open a session to continue, or delete it immediately",
        ]}
      />
    </>
  );
}
