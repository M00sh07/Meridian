"use client";

import * as React from "react";
import { useParams } from "next/navigation";
import { MerNav } from "@/components/meredian/nav";
import { MerShell } from "@/components/meredian/shell";

export default function RepoLayout({ children }: { children: React.ReactNode }) {
  const params = useParams();
  const repoId = params.id as string;

  return (
    <MerShell
      sidebar={<MerNav repoId={repoId} />}
      header={
        <div className="flex items-center justify-between px-4 py-2">
          <div className="flex items-center gap-3">
            <div className="w-6 h-6 rounded-sm bg-graphite-800 border border-white/10 flex items-center justify-center">
              <span className="text-[10px] font-mono text-white/50">R</span>
            </div>
            <span className="text-xs font-mono text-white/60 truncate max-w-[420px]">
              repo/{repoId}
            </span>
          </div>
          <div className="flex items-center gap-4 text-[10px] font-mono text-white/30">
            <span className="flex items-center gap-1.5">
              <span className="w-1.5 h-1.5 rounded-full bg-mer-cyan/70" />
              Instrument active
            </span>
          </div>
        </div>
      }
    >
      {children}
    </MerShell>
  );
}