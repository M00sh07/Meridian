import * as React from "react";
import { cn } from "@/lib/utils";

export interface MerRailProps extends React.HTMLAttributes<HTMLElement> {
  collapsed?: boolean;
}

export function MerRail({ collapsed, className, children, ...props }: MerRailProps) {
  return (
    <aside
      className={cn(
        "flex flex-col h-full bg-graphite-950 border-r border-white/5",
        collapsed ? "w-14" : "w-52",
        className
      )}
      {...props}
    >
      {children}
    </aside>
  );
}