import * as React from "react";
import { cn } from "@/lib/utils";

export interface MerSectionProps extends React.HTMLAttributes<HTMLElement> {
  label?: string;
  actions?: React.ReactNode;
}

export function MerSection({ label, actions, className, children, ...props }: MerSectionProps) {
  return (
    <section className={cn("flex flex-col", className)} {...props}>
      {(label || actions) && (
        <div className="flex items-center justify-between px-3 py-1.5 border-b border-white/5">
          {label ? <span className="mer-label">{label}</span> : <span />}
          {actions && <div className="flex items-center gap-2">{actions}</div>}
        </div>
      )}
      <div className="flex-1 min-h-0">{children}</div>
    </section>
  );
}