import type { Metadata } from "next";
import { AnalystStudio } from "@/components/analyst/analyst-studio";
import { PageHeader } from "@/components/layout/page-header";

export const metadata: Metadata = { title: "AI Analyst" };

export default function Page() {
  return (
    <>
      <PageHeader title="AI Analyst" description="Ask questions in plain language. Answers are calculated from your data, never guessed." />
      <AnalystStudio />
    </>
  );
}
