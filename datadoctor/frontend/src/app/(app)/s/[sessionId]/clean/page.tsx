import type { Metadata } from "next";
import { Suspense } from "react";
import { CleaningStudio } from "@/components/cleaning/cleaning-studio";
import { PageHeader } from "@/components/layout/page-header";

export const metadata: Metadata = { title: "Cleaning Studio" };

export default function CleanPage() {
  return (
    <>
      <PageHeader
        title="Cleaning Studio"
        description="Preview each fix on your full data, then apply it. Your original file is never changed."
      />
      <Suspense>
        <CleaningStudio />
      </Suspense>
    </>
  );
}
