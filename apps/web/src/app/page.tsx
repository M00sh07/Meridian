"use client";
import * as React from "react";
import { motion } from "motion/react";
import Link from "next/link";
import { api } from "@/lib/api";
import { cn } from "@/lib/utils";
import { MerLabel } from "@/components/meredian/label";
import { MerStat } from "@/components/meredian/stat";
import { Search, GitBranch, Folder, Clock, Hash, FileText } from "lucide-react";

interface Repo {
  id: number;
  url: string;
  status: string;
  created_at: string;
  updated_at: string;
}

function RepoRow({ repo, index }: { repo: Repo; index: number }) {
  const statusTone = repo.status === "completed" ? "cyan" : repo.status === "failed" ? "magenta" : "amber";
  return (
    <motion.div
      initial={{ opacity: 0, y: 6 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.35, delay: index * 0.04 }}
    >
      <Link
        href={`/repo/${repo.id}`}
        className={cn(
          "group flex items-center gap-4 px-4 py-3 border-b border-white/5 hover:bg-white/[0.02] transition-colors",
          "hover:border-mer-amber/20"
        )}
      >
        <div className="flex items-center justify-center w-9 h-9 rounded-sm bg-graphite-800 border border-white/5 group-hover:border-mer-amber/30">
          <GitBranch size={16} className="text-white/40 group-hover:text-mer-amber" />
        </div>
        <div className="flex-1 min-w-0">
          <div className="font-mono text-sm text-white/90 truncate group-hover:text-white">
            {repo.url.replace("https://github.com/", "")}
          </div>
          <div className="text-[11px] text-white/30 font-mono mt-0.5">
            {repo.url}
          </div>
        </div>
        <div className="flex items-center gap-4 text-[11px] font-mono text-white/40">
          <span className={cn("px-1.5 py-0.5 rounded text-[10px] uppercase tracking-wider", statusTone === "cyan" && "text-mer-cyan", statusTone === "amber" && "text-mer-amber", statusTone === "magenta" && "text-mer-magenta")}>
            {repo.status}
          </span>
          <span className="hidden sm:inline">{new Date(repo.created_at).toLocaleDateString()}</span>
        </div>
      </Link>
    </motion.div>
  );
}

export default function Home() {
  const [url, setUrl] = React.useState("");
  const [status, setStatus] = React.useState("");
  const [loading, setLoading] = React.useState(false);
  const [repos, setRepos] = React.useState<Repo[]>([]);

  React.useEffect(() => {
    const load = async () => {
      try {
        const data = await api.listRepositories();
        setRepos(data);
      } catch {
        setStatus("Error: Failed to load repositories");
      }
    };
    load();
  }, []);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setLoading(true);
    setStatus("");
    try {
      const data = await api.createRepository(url);
      setRepos((prev) => [data, ...prev]);
      setUrl("");
      setStatus("Repository submitted for analysis.");
    } catch (err) {
      setStatus(err instanceof Error ? err.message : "Failed to submit");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="min-h-screen mer-bg">
      <nav className="border-b border-white/5 bg-graphite-950/40">
        <div className="max-w-6xl mx-auto px-6 py-3 flex items-center justify-between">
          <Link href="/" className="flex items-center gap-2.5">
            <div className="w-7 h-7 rounded-sm bg-mer-amber/10 border border-mer-amber/30 flex items-center justify-center">
              <span className="text-mer-amber font-mono text-xs font-bold">M</span>
            </div>
            <span className="text-sm font-semibold tracking-tight text-white/90">Meredian</span>
          </Link>
          <div className="flex items-center gap-4 text-[11px] font-mono text-white/40">
            <span>Repository Intelligence</span>
          </div>
        </div>
      </nav>

      <main className="max-w-6xl mx-auto px-6 py-16">
        <div className="mb-12">
          <MerLabel tone="amber" className="mb-3">Entry Point</MerLabel>
          <h1 className="text-4xl font-bold tracking-tight text-white mb-3">
            Repository Intelligence
          </h1>
          <p className="text-white/50 text-sm max-w-xl">
            Understand an unfamiliar codebase before you change it.
          </p>
        </div>

        <div className="mb-12">
          <form onSubmit={handleSubmit} className="flex gap-3">
            <input
              type="text"
              required
              placeholder="https://github.com/owner/repo"
              value={url}
              onChange={(e) => setUrl(e.target.value)}
              className="flex-1 bg-graphite-900/60 border border-white/10 text-white text-sm px-4 py-2.5 rounded-sm focus:outline-none focus:border-mer-amber/40 font-mono placeholder:text-white/25"
            />
            <button
              type="submit"
              disabled={loading}
              className="px-5 py-2.5 bg-mer-amber/90 hover:bg-mer-amber text-black text-sm font-medium rounded-sm disabled:opacity-50"
            >
              {loading ? "Analyzing…" : "Ingest"}
            </button>
          </form>
          {status && <p className="mt-3 text-xs text-mer-amber font-mono">{status}</p>}
        </div>

        {repos.length > 0 && (
          <div>
            <div className="flex items-center justify-between mb-3">
              <MerLabel>Recent Repositories</MerLabel>
              <span className="text-[10px] font-mono text-white/25">{repos.length} analyzed</span>
            </div>
            <div className="border border-white/5 bg-graphite-950/40">
              {repos.map((repo, i) => (
                <RepoRow key={repo.id} repo={repo} index={i} />
              ))}
            </div>
          </div>
        )}
      </main>
    </div>
  );
}