import type { Metadata } from "next";
import { HealthView } from "@/components/health/health-view";
import { PageHeader } from "@/components/layout/page-header";

export const metadata: Metadata = { title: "Data Health" };

export default function HealthPage() {
  return (
    <>
      <PageHeader title="Data Health Center" description="What is in each column, computed from every row of your data." />
      <HealthView />
    </>
  );
}
