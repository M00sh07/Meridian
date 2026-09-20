import * as React from "react";
import { cn } from "@/lib/utils";

export interface MerShellProps extends React.HTMLAttributes<HTMLDivElement> {
  sidebar?: React.ReactNode;
  header?: React.ReactNode;
}

export function MerShell({ sidebar, header, className, children, ...props }: MerShellProps) {
  return (
    <div
      className={cn(
        "flex flex-col h-screen w-screen overflow-hidden mer-bg text-white/90",
        className
      )}
      {...props}
    >
      {header && (
        <header className="flex-shrink-0 border-b border-white/5 bg-graphite-950/60">
          {header}
        </header>
      )}
      <div className="flex flex-1 min-h-0">
        {sidebar && (
          <aside className="flex-shrink-0">
            {sidebar}
          </aside>
        )}
        <main className="flex-1 min-w-0 overflow-auto mer-scroll">
          {children}
        </main>
      </div>
    </div>
  );
}