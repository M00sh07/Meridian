import * as React from "react";
import { cn } from "@/lib/utils";

export interface MerLabelProps extends React.HTMLAttributes<HTMLDivElement> {
  tone?: "neutral" | "amber" | "cyan" | "magenta";
}

const toneMap: Record<NonNullable<MerLabelProps["tone"]>, string> = {
  neutral: "text-white/42",
  amber: "text-mer-amber/80",
  cyan: "text-mer-cyan/80",
  magenta: "text-mer-magenta/80",
};

export function MerLabel({ className, tone = "neutral", ...props }: MerLabelProps) {
  return (
    <div
      className={cn(
        "mer-label inline-flex items-center gap-1.5",
        toneMap[tone],
        className
      )}
      {...props}
    />
  );
}