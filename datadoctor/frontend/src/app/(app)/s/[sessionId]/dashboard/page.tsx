import type { Metadata } from "next";
import { ComingSoon } from "@/components/layout/coming-soon";
import { PageHeader } from "@/components/layout/page-header";

export const metadata: Metadata = { title: "Dashboard Studio" };

export default function Page() {
  return (
    <>
      <PageHeader title="Dashboard Studio" />
      <ComingSoon milestone={10} title="Dashboard Studio" points={["An automatic first dashboard based on your column types", "KPI cards, bar, line, pie, donut, histogram, scatter and table charts", "Filters, date ranges, grouping and sorting, all calculated from your data"]} />
    </>
  );
}
