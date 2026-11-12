import { SessionProvider } from "@/components/session/session-context";

export default async function SessionLayout({
  children,
  params,
}: {
  children: React.ReactNode;
  params: Promise<{ sessionId: string }>;
}) {
  const { sessionId } = await params;
  return <SessionProvider sessionId={sessionId}>{children}</SessionProvider>;
}
