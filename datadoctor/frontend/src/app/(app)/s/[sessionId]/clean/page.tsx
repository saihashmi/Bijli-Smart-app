import type { Metadata } from "next";
import { ComingSoon } from "@/components/layout/coming-soon";
import { PageHeader } from "@/components/layout/page-header";

export const metadata: Metadata = { title: "Cleaning Studio" };

export default function Page() {
  return (
    <>
      <PageHeader title="Cleaning Studio" />
      <ComingSoon milestone={7} title="Cleaning Studio" points={["Preview each fix on your full data before applying it", "Undo any step, or reset to the original file at any time", "A complete history of every change for your audit trail"]} />
    </>
  );
}
