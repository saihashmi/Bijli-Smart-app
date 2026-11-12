import type { Metadata } from "next";
import { ComingSoon } from "@/components/layout/coming-soon";
import { PageHeader } from "@/components/layout/page-header";

export const metadata: Metadata = { title: "AI Analyst" };

export default function Page() {
  return (
    <>
      <PageHeader title="AI Analyst" />
      <ComingSoon milestone={11} title="AI Analyst" points={["Ask questions such as \u201cWhich month has the highest sales?\u201d", "Answers are calculated on the server, never guessed by AI", "Works without an AI key; AI explanations are optional"]} />
    </>
  );
}
