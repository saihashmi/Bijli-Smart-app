import type { Metadata } from "next";
import { Suspense } from "react";
import { PageHeader } from "@/components/layout/page-header";
import { UploadStudio } from "@/components/upload/upload-studio";

export const metadata: Metadata = { title: "Upload Studio" };

export default function UploadPage() {
  return (
    <>
      <PageHeader
        title="Upload Studio"
        description="Bring in an Excel or CSV file, choose the worksheet and tell us which row holds the column names."
      />
      <Suspense>
        <UploadStudio />
      </Suspense>
    </>
  );
}
