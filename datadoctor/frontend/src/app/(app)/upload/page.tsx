import type { Metadata } from "next";
import { ComingSoon } from "@/components/layout/coming-soon";
import { PageHeader } from "@/components/layout/page-header";

export const metadata: Metadata = { title: "Upload Studio" };

export default function UploadPage() {
  return (
    <>
      <PageHeader title="Upload Studio" description="Bring in an Excel (.xlsx, .xls) or CSV file, up to 20 MB." />
      <ComingSoon
        milestone={4}
        title="File upload"
        points={[
          "Drag and drop or browse for a file, with a real upload progress bar",
          "Checks the file's actual content, size, encoding and password protection before accepting it",
          "Lists every worksheet, including hidden ones, so you can pick the right table and header row",
          "Previews rows, columns and detected data types (preview arrives in Milestone 5)",
        ]}
      />
    </>
  );
}
