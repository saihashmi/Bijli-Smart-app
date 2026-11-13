"use client";

import { useTheme } from "next-themes";
import { Toaster as Sonner, type ToasterProps } from "sonner";

function Toaster(props: ToasterProps) {
  const { resolvedTheme } = useTheme();
  return (
    <Sonner
      theme={(resolvedTheme as ToasterProps["theme"]) ?? "system"}
      position="bottom-right"
      richColors
      closeButton
      style={
        {
          "--normal-bg": "var(--popover)",
          "--normal-text": "var(--popover-foreground)",
          "--normal-border": "var(--border)",
          // Sonner's default green and red text miss WCAG AA on their tinted backgrounds in the light theme.
          ...(resolvedTheme === "dark" ? {} : { "--success-text": "#166534", "--error-text": "#b91c1c", "--warning-text": "#92400e", "--info-text": "#1d4ed8" }),
        } as React.CSSProperties
      }
      {...props}
    />
  );
}

export { Toaster };
