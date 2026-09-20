import * as React from "react";
import { Command } from "cmdk";
import { Dialog, DialogContent } from "@/components/ui/dialog";
import { Search, File, GitCommit, GitGraph, History, Flame, Home, Folder, Hash } from "lucide-react";
import { cn } from "@/lib/utils";

interface CommandPaletteProps {
  open: boolean;
  onOpenChange: (v: boolean) => void;
  onNavigate: (href: string) => void;
}

const groups = [
  {
    label: "Navigation",
    items: [
      { label: "Home", href: "/", icon: Home },
      { label: "Repository Overview", href: "/repo", icon: Folder },
      { label: "Architecture", href: "/repo/arch", icon: GitGraph },
      { label: "Files", href: "/repo/files", icon: File },
      { label: "History", href: "/repo/history", icon: History },
      { label: "Hotspots", href: "/repo/hotspots", icon: Flame },
    ],
  },
  {
    label: "Actions",
    items: [
      { label: "Search Files", href: "/repo/files", icon: File },
      { label: "Find Symbol", href: "/repo/symbols", icon: Hash },
      { label: "Open Recent Commit", href: "/repo/history", icon: GitCommit },
      { label: "Go to Repository Overview", href: "/repo", icon: Folder },
    ],
  },
];

export function CommandPalette({ open, onOpenChange, onNavigate }: CommandPaletteProps) {
  const [query, setQuery] = React.useState("");

  const run = (href: string) => {
    onNavigate(href);
    onOpenChange(false);
    setQuery("");
  };

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent
        className="p-0 overflow-hidden border border-white/10 bg-graphite-950/95 backdrop-blur-xl max-w-xl"
        style={{ borderRadius: 4 }}
      >
        <Command
          filter={(value, search) => {
            if (!search) return 1;
            return value.toLowerCase().includes(search.toLowerCase()) ? 1 : 0;
          }}
          className="h-full"
        >
          <div className="flex items-center gap-2 px-3 py-2 border-b border-white/5">
            <Search size={14} className="text-white/40" />
            <Command.Input
              value={query}
              onValueChange={setQuery}
              placeholder="Type a command or search..."
              className="flex-1 bg-transparent text-sm text-white/90 outline-none placeholder:text-white/25 font-mono"
            />
            <kbd className="text-[10px] font-mono text-white/30 border border-white/10 rounded px-1.5 py-0.5">esc</kbd>
          </div>
          <Command.List className="max-h-[320px] overflow-y-auto mer-scroll p-1.5">
            <Command.Empty className="py-6 text-center text-xs text-white/30 font-mono">
              No results found.
            </Command.Empty>
            {groups.map((g) => (
              <Command.Group key={g.label} heading={g.label} className="py-1.5">
                <div className="px-2 py-1 mer-label">{g.label}</div>
                {g.items.map((item) => (
                  <Command.Item
                    key={item.label}
                    value={item.label}
                    onSelect={() => run(item.href)}
                    className={cn(
                      "flex items-center gap-2.5 px-2 py-1.5 rounded text-sm text-white/80 cursor-pointer",
                      "data-[selected=true]:bg-mer-amber/10 data-[selected=true]:text-white"
                    )}
                  >
                    <item.icon size={14} className="text-white/40" />
                    <span className="flex-1">{item.label}</span>
                  </Command.Item>
                ))}
              </Command.Group>
            ))}
          </Command.List>
        </Command>
      </DialogContent>
    </Dialog>
  );
}