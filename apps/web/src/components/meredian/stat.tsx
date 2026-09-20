import * as React from "react";
import { cn } from "@/lib/utils";

export interface MerStatProps extends React.HTMLAttributes<HTMLDivElement> {
  label: string;
  value: string | number;
  hint?: string;
  tone?: "neutral" | "amber" | "cyan" | "magenta";
}

export function MerStat({ label, value, hint, tone = "neutral", className, ...props }: MerStatProps) {
  const toneMap = {
    neutral: "text-white/80",
    amber: "text-mer-amber",
    cyan: "text-mer-cyan",
    magenta: "text-mer-magenta",
  };
  return (
    <div className={cn("flex flex-col", className)} {...props}>
      <span className="mer-label">{label}</span>
      <div className="flex items-baseline gap-2">
        <span className={cn("text-lg font-semibold tabular-nums", toneMap[tone])}>{value}</span>
        {hint && <span className="text-[10px] text-white/30 font-mono">{hint}</span>}
      </div>
    </div>
  );
}