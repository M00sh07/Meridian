"use client";
import * as React from "react";
import { motion } from "motion/react";
import Link from "next/link";
import { api } from "@/lib/api";
import { cn } from "@/lib/utils";
import { MerLabel } from "@/components/meredian/label";
import { GitBranch, Folder, Clock, Activity, Cpu } from "lucide-react";

interface Repo {
  id: number;
  url: string;
  status: string;
  created_at: string;
  updated_at: string;
}

const variants = {
  hidden: { opacity: 0, y: 10 },
  visible: (i: number) => ({
    opacity: 1,
    y: 0,
    transition: { delay: i * 0.05, duration: 0.4 },
  }),
};

function RepoRow({ repo, index }: { repo: Repo; index: number }) {
  const statusTone = repo.status === "completed" ? "cyan" : repo.status === "failed" ? "magenta" : "amber";
  return (
    <motion.div
      custom={index}
      initial="hidden"
      animate="visible"
      variants={variants}
      whileHover={{ scale: 1.002 }}
    >
      <Link
        href={`/repo/${repo.id}`}
        className={cn(
          "group flex flex-col sm:flex-row sm:items-center gap-4 px-5 py-4 border-b border-white/5 bg-graphite-900/20 hover:bg-white/[0.03] transition-all",
          "hover:border-mer-amber/30 hover:mer-glow-amber relative overflow-hidden"
        )}
      >
        <div className="absolute left-0 top-0 bottom-0 w-px bg-white/5 group-hover:bg-mer-amber/50 transition-colors" />
        <div className="flex items-center justify-center w-10 h-10 rounded-sm bg-graphite-850 border border-white/10 group-hover:border-mer-amber/40 shadow-inner">
          <GitBranch size={18} className="text-white/40 group-hover:text-mer-amber transition-colors" />
        </div>
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2 mb-1">
            <span className="font-mono text-sm text-white/90 truncate group-hover:text-white font-medium">
              {repo.url.replace("https://github.com/", "")}
            </span>
          </div>
          <div className="text-[11px] text-white/40 font-mono flex items-center gap-3">
            <span className="truncate">{repo.url}</span>
          </div>
        </div>
        <div className="flex items-center gap-6 text-[11px] font-mono text-white/50">
          <div className="flex items-center gap-2">
            <Activity size={12} className={cn(statusTone === "cyan" && "text-mer-cyan", statusTone === "amber" && "text-mer-amber", statusTone === "magenta" && "text-mer-magenta")} />
            <span className={cn("px-2 py-0.5 rounded-sm uppercase tracking-widest bg-white/5 border border-white/5", statusTone === "cyan" && "text-mer-cyan border-mer-cyan/20", statusTone === "amber" && "text-mer-amber border-mer-amber/20", statusTone === "magenta" && "text-mer-magenta border-mer-magenta/20")}>
              {repo.status}
            </span>
          </div>
          <div className="hidden sm:flex items-center gap-1.5">
            <Clock size={12} className="text-white/30" />
            {new Date(repo.created_at).toLocaleDateString(undefined, { month: 'short', day: 'numeric', year: 'numeric' })}
          </div>
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
        setStatus("ERR_LOAD_FAIL");
      }
    };
    load();
  }, []);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setLoading(true);
    setStatus("INITIALIZING_INGESTION...");
    try {
      const data = await api.createRepository(url);
      setRepos((prev) => [data, ...prev]);
      setUrl("");
      setStatus("SYS_INGESTION_COMPLETE");
    } catch (err) {
      setStatus(err instanceof Error ? `ERR: ${err.message}` : "ERR_UNKNOWN");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="min-h-screen mer-bg text-white selection:bg-mer-amber/30 selection:text-white">
      <nav className="border-b border-white/10 bg-graphite-950/80 backdrop-blur-md sticky top-0 z-50">
        <div className="max-w-7xl mx-auto px-6 py-4 flex items-center justify-between">
          <Link href="/" className="flex items-center gap-3 group">
            <div className="relative w-8 h-8 rounded-sm bg-graphite-900 border border-mer-amber/40 flex items-center justify-center mer-crosshair overflow-hidden">
              <div className="absolute inset-0 bg-mer-amber/10 group-hover:bg-mer-amber/20 transition-colors" />
              <span className="text-mer-amber font-mono text-sm font-bold relative z-10">M</span>
            </div>
            <div className="flex flex-col">
              <span className="text-sm font-bold tracking-widest text-white/90 uppercase">Meredian</span>
              <span className="text-[9px] text-white/40 font-mono uppercase tracking-widest">Sys.Core.01</span>
            </div>
          </Link>
          <div className="flex items-center gap-4 text-[10px] font-mono text-white/40 tracking-widest uppercase">
            <span className="flex items-center gap-1.5"><Cpu size={12} className="text-mer-cyan" /> System Active</span>
          </div>
        </div>
      </nav>

      <main className="max-w-7xl mx-auto px-6 py-16 md:py-24">
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.6 }}
          className="mb-16 grid grid-cols-1 lg:grid-cols-2 gap-12 items-end"
        >
          <div>
            <MerLabel tone="amber" className="mb-4">Target Designation</MerLabel>
            <h1 className="text-5xl font-bold tracking-tight text-white mb-4 leading-tight">
              Observatory <br />
              <span className="text-white/40 font-light">Nexus</span>
            </h1>
            <p className="text-white/50 text-sm max-w-md font-mono leading-relaxed">
              &gt; INPUT REPOSITORY COORDINATES FOR STRUCTURAL AND TEMPORAL ANALYSIS.
            </p>
          </div>

          <div className="mer-frame-thick p-6 rounded-sm relative overflow-hidden">
            <div className="absolute top-0 right-0 p-2 opacity-20"><Cpu size={100} /></div>
            <form onSubmit={handleSubmit} className="relative z-10 flex flex-col gap-4">
              <div className="flex flex-col gap-2">
                <label className="text-[10px] font-mono text-white/40 uppercase tracking-widest">Target URL</label>
                <div className="flex gap-2">
                  <input
                    type="text"
                    required
                    placeholder="https://github.com/owner/repo"
                    value={url}
                    onChange={(e) => setUrl(e.target.value)}
                    className="flex-1 bg-graphite-900 border border-white/10 text-white text-sm px-4 py-3 rounded-sm focus:outline-none focus:border-mer-amber/60 font-mono placeholder:text-white/20 transition-colors"
                  />
                  <button
                    type="submit"
                    disabled={loading}
                    className="px-6 py-3 bg-mer-amber hover:bg-mer-amber/90 text-black text-sm font-bold tracking-wider uppercase rounded-sm disabled:opacity-50 flex items-center justify-center min-w-[120px] transition-all"
                  >
                    {loading ? <motion.div animate={{ rotate: 360 }} transition={{ repeat: Infinity, duration: 1, ease: "linear" }}><Activity size={16} /></motion.div> : "Ingest"}
                  </button>
                </div>
              </div>
              <div className="h-4">
                {status && (
                  <motion.p initial={{ opacity: 0 }} animate={{ opacity: 1 }} className={cn("text-xs font-mono flex items-center gap-2", status.includes("ERR") ? "text-mer-magenta" : "text-mer-cyan")}>
                    <span className="w-1.5 h-1.5 rounded-full bg-current animate-pulse" />
                    {status}
                  </motion.p>
                )}
              </div>
            </form>
          </div>
        </motion.div>

        {repos.length > 0 && (
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            transition={{ delay: 0.3, duration: 0.6 }}
          >
            <div className="flex items-center justify-between mb-4 border-b border-white/10 pb-4">
              <div className="flex items-center gap-3">
                <Folder size={16} className="text-white/40" />
                <h2 className="text-sm font-medium tracking-widest uppercase text-white/80">Archived Targets</h2>
              </div>
              <span className="text-[10px] font-mono text-white/40 bg-white/5 px-2 py-1 rounded border border-white/5">
                COUNT: {repos.length.toString().padStart(3, '0')}
              </span>
            </div>
            <div className="mer-frame rounded-sm shadow-2xl">
              {repos.map((repo, i) => (
                <RepoRow key={repo.id} repo={repo} index={i} />
              ))}
            </div>
          </motion.div>
        )}
      </main>
    </div>
  );
}
