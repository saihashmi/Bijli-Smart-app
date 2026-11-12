import type { Metadata } from "next";
import Link from "next/link";
import { Suspense } from "react";
import { Upload } from "lucide-react";
import { PageHeader } from "@/components/layout/page-header";
import { WorkspaceView } from "@/components/workspace/workspace-view";
import { Button } from "@/components/ui/button";

export const metadata: Metadata = { title: "Workspace" };

export default function WorkspacePage() {
  return (
    <>
      <PageHeader
        title="Workspace"
        description="Your uploaded files and their analysis sessions. Files are deleted automatically when they expire."
        actions={
          <Button asChild>
            <Link href="/upload">
              <Upload /> New upload
            </Link>
          </Button>
        }
      />
      <Suspense>
        <WorkspaceView />
      </Suspense>
    </>
  );
}
