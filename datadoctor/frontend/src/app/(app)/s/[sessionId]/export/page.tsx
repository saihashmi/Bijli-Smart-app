import type { Metadata } from "next";
import { ComingSoon } from "@/components/layout/coming-soon";
import { PageHeader } from "@/components/layout/page-header";

export const metadata: Metadata = { title: "Export Center" };

export default function Page() {
  return (
    <>
      <PageHeader title="Export Center" />
      <ComingSoon milestone={13} title="Export Center" points={["Excel workbook: cleaned data, quality report, audit log and statistics", "PDF report with charts and findings, timestamped in your time zone", "Protection against formula injection in exported text"]} />
    </>
  );
}
