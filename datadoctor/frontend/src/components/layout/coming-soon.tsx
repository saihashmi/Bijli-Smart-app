import { Construction } from "lucide-react";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";

/** Honest placeholder: says what the screen will do and when. Contains no fake controls or data. */
export function ComingSoon({ milestone, title, points }: { milestone: number; title: string; points: string[] }) {
  return (
    <Card className="max-w-2xl" data-testid="coming-soon">
      <CardHeader>
        <div className="flex items-center gap-2">
          <Construction className="size-5 text-warning" aria-hidden />
          <CardTitle>{title}</CardTitle>
          <Badge variant="warning">Milestone {milestone}</Badge>
        </div>
        <CardDescription>This screen is not built yet. Here is what it will do once Milestone {milestone} is complete:</CardDescription>
      </CardHeader>
      <CardContent>
        <ul className="list-disc space-y-1.5 pl-5 text-sm">
          {points.map((p) => (
            <li key={p}>{p}</li>
          ))}
        </ul>
      </CardContent>
    </Card>
  );
}
