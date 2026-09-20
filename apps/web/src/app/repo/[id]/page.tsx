"use client";

import { useEffect, useState, useMemo } from "react";
import { useParams } from "next/navigation";
import { api } from "@/lib/api";
import {
  Background,
  Controls,
  ReactFlow,
  type Edge,
  type Node,
} from "@xyflow/react";
import "@xyflow/react/dist/style.css";
import { GitCommit, GitGraph, File, History, Flame, Folder, AlertTriangle, ArrowRight, ArrowLeft } from "lucide-react";
import Link from "next/link";
import { cn } from "@/lib/utils";

// --- Types ---
interface Repository { id: number; url: string; status: string; }
interface FileItem { id: number; path: string; language: string; }
interface SymbolItem { id: number; name: string; type: string; signature: string; start_line: number; file_id: number; }
interface Dependency { source_file: string; target_file: string | null; imported_module: string; }
interface CommitItem { sha: string; message: string; author: string; date: string; }
interface HotspotItem { file_id: number; path: string; churn_score: number; }
interface FileChurn { commits_count: number; lines_added: number; lines_deleted: number; }

// --- Sub-Components ---
function OverviewTab({ repo }: { repo: Repository }) {
  return (
    <div className="space-y-6">
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        <div className="mer-stat">
          <div className="mer-stat-label">Repository ID</div>
          <div className="mer-stat-value">{repo.id}</div>
        </div>
        <div className="mer-stat">
          <div className="mer-stat-label">Status</div>
          <div className="mer-stat-value text-mer-cyan">{repo.status}</div>
        </div>
        <div className="mer-stat">
          <div className="mer-stat-label">URL</div>
          <div className="mer-stat-value text-xs truncate" title={repo.url}>{repo.url}</div>
        </div>
      </div>
    </div>
  );
}

function ArchitectureTab({ repoId }: { repoId: number }) {
  const [dependencies, setDependencies] = useState<Dependency[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    api.getDependencies(repoId).then(setDependencies).finally(() => setLoading(false));
  }, [repoId]);

  const graph = useMemo(() => {
    const filePaths = new Set<string>();
    const resolvedDependencies = dependencies.filter((dep) => {
      if (!dep.target_file) return false;
      filePaths.add(dep.source_file);
      filePaths.add(dep.target_file);
      return true;
    });

    const nodes: Node[] = Array.from(filePaths).map((path, index) => ({
      id: path,
      position: { x: (index % 4) * 250, y: Math.floor(index / 4) * 100 },
      data: { label: path },
      style: { background: "#0a0a0a", border: "1px solid #27272a", color: "#a1a1aa", width: 220, fontSize: "12px", fontFamily: "monospace" },
    }));
    const edges: Edge[] = resolvedDependencies.map((dep, index) => ({
      id: `${dep.source_file}-${dep.target_file}-${index}`,
      source: dep.source_file,
      target: dep.target_file as string,
      animated: true,
      style: { stroke: "#0ea5e9", opacity: 0.5 },
    }));

    return { nodes, edges };
  }, [dependencies]);

  if (loading) return <div className="p-4 text-xs font-mono text-white/50">Loading architecture...</div>;
  if (graph.nodes.length === 0) return <div className="p-4 text-xs font-mono text-white/50">No dependency graph available.</div>;

  return (
    <div className="h-[600px] w-full rounded border border-white/10 bg-graphite-950 overflow-hidden relative">
      <ReactFlow nodes={graph.nodes} edges={graph.edges} fitView>
        <Background color="#27272a" gap={24} />
        <Controls className="bg-graphite-900 border-white/10 fill-white/50" />
      </ReactFlow>
    </div>
  );
}

function FileIntelligence({ repoId, file }: { repoId: number; file: FileItem }) {
  const [commits, setCommits] = useState<CommitItem[]>([]);
  const [churn, setChurn] = useState<FileChurn | null>(null);
  const [symbols, setSymbols] = useState<SymbolItem[]>([]);

  useEffect(() => {
    api.getFileCommits(repoId, file.id).then(res => setCommits(res.items || []));
    api.getFileChurn(repoId, file.id).then(setChurn);
    api.getSymbols(repoId).then(res => {
      setSymbols((res.items || []).filter((s: SymbolItem) => s.file_id === file.id));
    });
  }, [repoId, file.id]);

  return (
    <div className="mt-4 p-4 bg-black/40 border border-white/5 rounded-md space-y-4">
      <h3 className="text-sm font-medium text-white/90 border-b border-white/10 pb-2 mb-2">File Intelligence</h3>

      <div className="grid grid-cols-3 gap-4">
        <div className="mer-stat">
          <div className="mer-stat-label">Commits</div>
          <div className="mer-stat-value">{churn?.commits_count ?? 0}</div>
        </div>
        <div className="mer-stat">
          <div className="mer-stat-label">Lines Added</div>
          <div className="mer-stat-value text-emerald-500">{churn?.lines_added ?? 0}</div>
        </div>
        <div className="mer-stat">
          <div className="mer-stat-label">Lines Deleted</div>
          <div className="mer-stat-value text-red-500">{churn?.lines_deleted ?? 0}</div>
        </div>
      </div>

      {symbols.length > 0 && (
        <div className="space-y-2">
          <h4 className="text-xs font-medium text-white/70">Symbols</h4>
          <div className="space-y-1">
            {symbols.map(s => (
              <div key={s.id} className="text-xs font-mono bg-white/5 px-2 py-1 rounded flex justify-between">
                <span className="text-mer-cyan">{s.name}</span>
                <span className="text-white/40">{s.type}</span>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}

function FilesTab({ repoId }: { repoId: number }) {
  const [files, setFiles] = useState<FileItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [selectedFile, setSelectedFile] = useState<FileItem | null>(null);

  useEffect(() => {
    api.getFiles(repoId).then(res => setFiles(res.items || [])).finally(() => setLoading(false));
  }, [repoId]);

  if (loading) return <div className="p-4 text-xs font-mono text-white/50">Loading files...</div>;

  return (
    <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
      <div className="space-y-1">
        {files.map(f => (
          <button
            key={f.id}
            onClick={() => setSelectedFile(f)}
            className={cn(
              "w-full text-left px-3 py-2 text-xs font-mono rounded flex justify-between items-center transition-colors",
              selectedFile?.id === f.id ? "bg-white/10 text-white" : "text-white/60 hover:bg-white/5 hover:text-white/90"
            )}
          >
            <span className="truncate">{f.path}</span>
            <span className="text-[10px] uppercase text-white/40 border border-white/10 px-1 rounded">{f.language}</span>
          </button>
        ))}
      </div>
      <div>
        {selectedFile ? (
          <div className="bg-graphite-900 border border-white/10 rounded p-4 sticky top-4">
            <h3 className="text-sm font-mono text-white mb-2 break-all">{selectedFile.path}</h3>
            <div className="text-xs text-white/50 mb-4 uppercase">{selectedFile.language}</div>
            <FileIntelligence repoId={repoId} file={selectedFile} />
          </div>
        ) : (
          <div className="flex items-center justify-center h-full min-h-[200px] text-xs font-mono text-white/30 border border-white/5 border-dashed rounded">
            Select a file to inspect
          </div>
        )}
      </div>
    </div>
  );
}

function HistoryTab({ repoId }: { repoId: number }) {
  const [commits, setCommits] = useState<CommitItem[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    api.getCommits(repoId).then(res => setCommits(res.items || [])).finally(() => setLoading(false));
  }, [repoId]);

  if (loading) return <div className="p-4 text-xs font-mono text-white/50">Loading history...</div>;

  return (
    <div className="space-y-3">
      {commits.map(c => (
        <div key={c.sha} className="p-4 border border-white/10 rounded-md bg-graphite-900 flex flex-col gap-2">
          <div className="flex justify-between items-start">
            <h4 className="text-sm text-white/90 font-medium">{c.message}</h4>
            <span className="text-xs font-mono text-mer-amber bg-mer-amber/10 px-2 py-0.5 rounded">{c.sha.slice(0, 7)}</span>
          </div>
          <div className="flex justify-between items-center text-xs text-white/50">
            <span className="flex items-center gap-1.5"><History size={12} /> {c.author}</span>
            <span>{new Date(c.date).toLocaleString()}</span>
          </div>
        </div>
      ))}
    </div>
  );
}

function HotspotsTab({ repoId }: { repoId: number }) {
  const [hotspots, setHotspots] = useState<HotspotItem[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    api.getHotspots(repoId).then(setHotspots).finally(() => setLoading(false));
  }, [repoId]);

  if (loading) return <div className="p-4 text-xs font-mono text-white/50">Loading hotspots...</div>;

  return (
    <div className="space-y-2">
      {hotspots.map((h, i) => (
        <div key={h.file_id} className="flex items-center justify-between p-3 border border-white/10 rounded bg-gradient-to-r from-red-950/20 to-transparent">
          <div className="flex items-center gap-3">
            <span className="text-xs font-mono text-red-500/50 w-4">{i + 1}</span>
            <span className="text-sm font-mono text-white/80">{h.path}</span>
          </div>
          <div className="flex items-center gap-2">
            <Flame size={14} className="text-red-500" />
            <span className="text-xs font-mono text-white/60 bg-red-500/10 px-2 py-0.5 rounded">Score: {h.churn_score.toFixed(2)}</span>
          </div>
        </div>
      ))}
      {hotspots.length === 0 && <div className="p-4 text-xs font-mono text-white/50">No hotspots found.</div>}
    </div>
  );
}

export default function RepoExplorer() {
  const params = useParams();
  const id = parseInt(params.id as string, 10);

  const [repo, setRepo] = useState<Repository | null>(null);
  const [activeTab, setActiveTab] = useState<"overview" | "arch" | "files" | "history" | "hotspots">("overview");

  useEffect(() => {
    api.getRepository(id).then(setRepo);
  }, [id]);

  if (!repo) {
    return (
      <div className="min-h-screen bg-graphite-950 flex items-center justify-center p-8">
        <div className="mer-stat animate-pulse">Loading Observatory...</div>
      </div>
    );
  }

  const tabs = [
    { id: "overview", label: "Overview", icon: Folder },
    { id: "arch", label: "Architecture", icon: GitGraph },
    { id: "files", label: "Files", icon: File },
    { id: "history", label: "History", icon: GitCommit },
    { id: "hotspots", label: "Hotspots", icon: Flame },
  ] as const;

  return (
    <div className="min-h-screen bg-graphite-950 text-white font-sans selection:bg-mer-cyan/30">
      <header className="border-b border-white/10 bg-graphite-900/50 backdrop-blur-md sticky top-0 z-10 px-6 py-4 flex items-center justify-between">
        <div className="flex items-center gap-4">
          <Link href="/" className="text-white/40 hover:text-white/90 transition-colors">
            <ArrowLeft size={16} />
          </Link>
          <div className="h-4 w-px bg-white/10" />
          <h1 className="text-sm font-mono tracking-tight flex items-center gap-2">
            <span className="text-white/50">REPOSITORY</span>
            <span className="text-mer-cyan">{repo.url.split('/').pop()}</span>
          </h1>
        </div>
        <div className="text-[10px] uppercase tracking-widest text-white/30 border border-white/10 px-2 py-1 rounded-sm">
          {repo.status}
        </div>
      </header>

      <div className="max-w-6xl mx-auto p-6 md:p-8 space-y-8">
        <nav className="flex gap-1 border-b border-white/5 pb-px">
          {tabs.map(t => (
            <button
              key={t.id}
              onClick={() => setActiveTab(t.id as "overview" | "arch" | "files" | "history" | "hotspots")}
              className={cn(
                "flex items-center gap-2 px-4 py-2.5 text-xs font-medium uppercase tracking-wider transition-all border-b-2",
                activeTab === t.id
                  ? "border-mer-cyan text-mer-cyan bg-mer-cyan/5"
                  : "border-transparent text-white/50 hover:text-white/90 hover:bg-white/5"
              )}
            >
              <t.icon size={14} />
              {t.label}
            </button>
          ))}
        </nav>

        <main className="animate-in fade-in slide-in-from-bottom-2 duration-300">
          {activeTab === "overview" && <OverviewTab repo={repo} />}
          {activeTab === "arch" && <ArchitectureTab repoId={id} />}
          {activeTab === "files" && <FilesTab repoId={id} />}
          {activeTab === "history" && <HistoryTab repoId={id} />}
          {activeTab === "hotspots" && <HotspotsTab repoId={id} />}
        </main>
      </div>
    </div>
  );
}
