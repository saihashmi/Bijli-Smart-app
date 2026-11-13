import type { Metadata } from "next";
import { DashboardStudio } from "@/components/dashboard/dashboard-studio";
import { PageHeader } from "@/components/layout/page-header";

export const metadata: Metadata = { title: "Dashboard Studio" };

export default function Page() {
  return (
    <>
      <PageHeader title="Dashboard Studio" description="Charts and KPIs calculated from your full data. Filter, edit and arrange them; nothing here changes your data." />
      <DashboardStudio />
    </>
  );
}
