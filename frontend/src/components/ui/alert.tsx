import * as React from "react";
import { cva, type VariantProps } from "class-variance-authority";
import { cn } from "@/lib/utils";

const alertVariants = cva("relative w-full rounded-lg border px-4 py-3 text-sm flex gap-3 [&>svg]:size-4 [&>svg]:mt-0.5 [&>svg]:shrink-0", {
  variants: {
    variant: {
      default: "bg-card",
      info: "border-primary/30 bg-secondary/60 text-secondary-foreground",
      warning: "border-warning/40 bg-warning/10",
      destructive: "border-destructive/40 bg-destructive/10 text-destructive",
    },
  },
  defaultVariants: { variant: "default" },
});

export function Alert({ className, variant, ...props }: React.HTMLAttributes<HTMLDivElement> & VariantProps<typeof alertVariants>) {
  return <div role="alert" className={cn(alertVariants({ variant }), className)} {...props} />;
}
