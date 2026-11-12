import { redirect } from "next/navigation";

export default async function SessionIndex({ params }: { params: Promise<{ sessionId: string }> }) {
  const { sessionId } = await params;
  redirect(`/s/${sessionId}/health`);
}
