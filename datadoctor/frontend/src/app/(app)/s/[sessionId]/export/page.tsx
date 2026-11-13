import type { Metadata } from "next";
import { ExportCenter } from "@/components/export/export-center";
import { PageHeader } from "@/components/layout/page-header";

export const metadata: Metadata = { title: "Export Center" };

export default function Page() {
  return (
    <>
      <PageHeader title="Export Center" description="Take your cleaned data and a report with you. Files are built from the same figures you see in the app." />
      <ExportCenter />
    </>
  );
}
