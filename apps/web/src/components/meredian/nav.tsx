"use client";

import * as React from "react";
import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { cn } from "@/lib/utils";
import { MerLabel } from "@/components/meredian/label";
import { CommandPalette } from "@/components/meredian/command-palette";
import { Search, Layout, Home, Menu, X } from "lucide-react";

interface NavItem {
  label: string;
  href: string;
  icon: React.ComponentType<{ size?: number; className?: string }>;
}

const NAV: NavItem[] = [
  { label: "Dashboard", href: "/", icon: Home },
  { label: "Observatory", href: "/repo", icon: Layout },
];

export function MerNav({ repoId }: { repoId?: string }) {
  const pathname = usePathname();
  const router = useRouter();
  const [collapsed, setCollapsed] = React.useState(false);
  const [cmdOpen, setCmdOpen] = React.useState(false);

  React.useEffect(() => {
    const down = (e: KeyboardEvent) => {
      if ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === "k") {
        e.preventDefault();
        setCmdOpen((o) => !o);
      }
      if (e.key === "Escape") setCmdOpen(false);
    };
    window.addEventListener("keydown", down);
    return () => window.removeEventListener("keydown", down);
  }, []);

  return (
    <>
      <CommandPalette
        open={cmdOpen}
        onOpenChange={setCmdOpen}
        onNavigate={(href) => {
          if (repoId) {
            if (href === "/repo") router.push(`/repo/${repoId}`);
            else if (href.startsWith("/repo/")) router.push(`/repo/${repoId}${href.slice(5)}`);
            else router.push(href);
          } else {
            router.push(href);
          }
        }}
      />
      <nav
        className={cn(
          "flex flex-col h-full bg-graphite-950/80 border-r border-white/5 transition-all duration-300",
          collapsed ? "w-14" : "w-56"
        )}
      >
        <div className="flex items-center justify-between px-3 py-3 border-b border-white/5">
          <Link href="/" className="flex items-center gap-2.5 min-w-0">
            <div className="w-7 h-7 rounded-sm bg-mer-amber/10 border border-mer-amber/30 flex items-center justify-center">
              <span className="text-mer-amber font-mono text-xs font-bold">M</span>
            </div>
            {!collapsed && (
              <span className="text-sm font-semibold tracking-tight text-white/90 truncate">
                Meredian
              </span>
            )}
          </Link>
          <button
            onClick={() => setCollapsed((c) => !c)}
            className="p-1 rounded text-white/40 hover:text-white/80 hover:bg-white/5"
            aria-label="Toggle navigation"
          >
            {collapsed ? <Menu size={14} /> : <X size={14} />}
          </button>
        </div>

        <div className="px-3 py-2">
          <button
            onClick={() => setCmdOpen(true)}
            className="w-full flex items-center gap-2 px-2 py-1.5 rounded text-xs text-white/50 hover:text-white/80 hover:bg-white/5 border border-white/5"
          >
            <Search size={12} />
            {!collapsed && <span className="flex-1 text-left">Command…</span>}
            {!collapsed && <kbd className="text-[9px] font-mono text-white/30">⌘K</kbd>}
          </button>
        </div>

        <div className="flex-1 overflow-y-auto mer-scroll px-1.5 py-2">
          <div className="space-y-0.5">
            {NAV.map((item) => {
              const active = pathname === item.href || pathname?.startsWith(item.href + "/");
              return (
                <Link
                  key={item.href}
                  href={repoId ? `/repo/${repoId}${item.href.slice(5)}` : item.href}
                  className={cn(
                    "flex items-center gap-2.5 px-2 py-1.5 rounded text-sm transition-colors",
                    active
                      ? "text-white bg-mer-amber/10 border border-mer-amber/20"
                      : "text-white/50 hover:text-white/90 hover:bg-white/5"
                  )}
                >
                  <item.icon size={15} className={cn(active ? "text-mer-amber" : "text-white/40")} />
                  {!collapsed && <span>{item.label}</span>}
                </Link>
              );
            })}
          </div>
        </div>

        <div className="mt-auto px-3 py-3 border-t border-white/5">
          <MerLabel tone="cyan">Instrument</MerLabel>
          {!collapsed && (
            <p className="text-[10px] text-white/30 mt-1 font-mono leading-relaxed">
              Repository telemetry engine
            </p>
          )}
        </div>
      </nav>
    </>
  );
}
