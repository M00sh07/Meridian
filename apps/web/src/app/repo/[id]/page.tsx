/* eslint-disable @typescript-eslint/no-explicit-any */
"use client";

import { useEffect, useState, useMemo } from "react";
import { useParams } from "next/navigation";
import { motion, AnimatePresence } from "motion/react";
import { api } from "@/lib/api";
import {
  Background,
  Controls,
  ReactFlow,
  type Edge,
  type Node,
} from "@xyflow/react";
import "@xyflow/react/dist/style.css";
import { GitCommit, GitGraph, File, History, Flame, Folder, ArrowLeft, Search, Zap, ShieldAlert, Box } from "lucide-react";
import Link from "next/link";
import { cn } from "@/lib/utils";

// --- Types ---
interface Repository { id: number; url: string; status: string; }
interface FileItem { id: number; path: string; language: string; }
interface SymbolItem { id: number; name: string; type: string; signature: string; start_line: number; file_id: number; }
interface Dependency { source_file: string; target_file: string | null; imported_module: string; }
interface CommitItem { sha: string; message: string; author: string; date: string; }
interface HotspotItem { file_id: number; path: string; total_changes: number; recent_changes: number; }
interface FileChurn { commits_count: number; lines_added: number; lines_deleted: number; }

// --- Sub-Components ---
function OverviewTab({ repo }: { repo: Repository }) {
  return (
    <div className="space-y-8">
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        <motion.div initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: 0.1 }} className="mer-stat bg-white/[0.02]">
          <div className="mer-stat-label">System.ID</div>
          <div className="mer-stat-value font-mono">{repo.id.toString().padStart(6, '0')}</div>
        </motion.div>
        <motion.div initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: 0.2 }} className="mer-stat bg-white/[0.02]">
          <div className="mer-stat-label">Lifecycle.State</div>
          <div className={cn("mer-stat-value uppercase tracking-widest text-sm", repo.status === 'completed' ? "text-mer-cyan" : repo.status === 'failed' ? "text-mer-magenta" : "text-mer-amber")}>{repo.status}</div>
        </motion.div>
        <motion.div initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: 0.3 }} className="mer-stat bg-white/[0.02] md:col-span-2">
          <div className="mer-stat-label">Source.Coordinate</div>
          <div className="mer-stat-value text-xs font-mono text-white/70 truncate flex items-center gap-2" title={repo.url}>
            <Folder size={12} className="text-white/30" />
            {repo.url}
          </div>
        </motion.div>
      </div>

      <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }} transition={{ delay: 0.4 }} className="mer-frame-thick p-8 rounded-sm relative overflow-hidden">
        <div className="absolute inset-0 mer-topology opacity-20 pointer-events-none" />
        <div className="relative z-10 max-w-2xl">
          <h2 className="text-2xl font-bold tracking-tight text-white mb-4">Structural Overview Active</h2>
          <p className="text-sm font-mono text-white/50 leading-relaxed mb-6">
            &gt; SYSTEM HAS INGESTED TARGET REPOSITORY. USE DIAGNOSTIC TABS TO EXPLORE ARCHITECTURE, FILES, CHURN METRICS, AND RISK TOPOLOGY.
          </p>
          <div className="flex gap-4">
            <div className="flex items-center gap-2 text-xs font-mono text-mer-amber bg-mer-amber/10 px-3 py-1.5 rounded-sm border border-mer-amber/20">
              <Zap size={14} /> Telemetry Online
            </div>
            <div className="flex items-center gap-2 text-xs font-mono text-mer-cyan bg-mer-cyan/10 px-3 py-1.5 rounded-sm border border-mer-cyan/20">
              <ShieldAlert size={14} /> Shields Nominal
            </div>
          </div>
        </div>
      </motion.div>
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
  const [churn, setChurn] = useState<FileChurn | null>(null);
  const [symbols, setSymbols] = useState<SymbolItem[]>([]);

  useEffect(() => {
    api.getFileChurn(repoId, file.id).then(setChurn);
    api.getSymbols(repoId).then(res => {
      setSymbols((res.items || []).filter((s: SymbolItem) => s.file_id === file.id));
    });
  }, [repoId, file.id]);

  return (
    <motion.div
      initial={{ opacity: 0, y: 10 }}
      animate={{ opacity: 1, y: 0 }}
      className="mt-6 p-5 bg-graphite-950/50 border border-white/5 rounded-sm space-y-6 shadow-inner relative overflow-hidden"
    >
      <div className="absolute top-0 right-0 p-2 opacity-10"><File size={60} /></div>
      <div className="relative z-10">
        <h3 className="text-xs font-mono tracking-widest text-mer-amber border-b border-white/10 pb-2 mb-4 uppercase">Intelligence.Report</h3>

        <div className="grid grid-cols-3 gap-4 mb-6">
          <div className="mer-stat bg-white/[0.02]">
            <div className="mer-stat-label">Commits</div>
            <div className="mer-stat-value">{churn?.commits_count ?? 0}</div>
          </div>
          <div className="mer-stat bg-white/[0.02]">
            <div className="mer-stat-label text-mer-cyan">L.Added</div>
            <div className="mer-stat-value text-mer-cyan">{churn?.lines_added ?? 0}</div>
          </div>
          <div className="mer-stat bg-white/[0.02]">
            <div className="mer-stat-label text-mer-magenta">L.Deleted</div>
            <div className="mer-stat-value text-mer-magenta">{churn?.lines_deleted ?? 0}</div>
          </div>
        </div>

        {symbols.length > 0 && (
          <div className="space-y-3">
            <h4 className="text-[10px] font-mono tracking-widest text-white/40 uppercase">Detected Symbols</h4>
            <div className="space-y-1.5 max-h-[300px] overflow-y-auto mer-scroll pr-2">
              {symbols.map((s, i) => (
                <motion.div
                  initial={{ opacity: 0, x: -10 }}
                  animate={{ opacity: 1, x: 0 }}
                  transition={{ delay: i * 0.05 }}
                  key={s.id}
                  className="text-xs font-mono bg-graphite-900 border border-white/5 px-3 py-2 rounded-sm flex justify-between items-center group hover:border-mer-cyan/30 transition-colors"
                >
                  <span className="text-mer-cyan truncate group-hover:text-mer-cyan">{s.name}</span>
                  <span className="text-[10px] text-white/30 uppercase tracking-widest bg-white/5 px-1.5 py-0.5 rounded">{s.type}</span>
                </motion.div>
              ))}
            </div>
          </div>
        )}
      </div>
    </motion.div>
  );
}

function FilesTab({ repoId }: { repoId: number }) {
  const [files, setFiles] = useState<FileItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [selectedFile, setSelectedFile] = useState<FileItem | null>(null);

  useEffect(() => {
    api.getFiles(repoId).then(res => setFiles(res.items || [])).finally(() => setLoading(false));
  }, [repoId]);

  if (loading) return <div className="p-8 text-xs font-mono text-mer-cyan animate-pulse tracking-widest">LOADING_FILE_SYSTEM...</div>;

  return (
    <div className="grid grid-cols-1 md:grid-cols-12 gap-6 h-[70vh]">
      <div className="md:col-span-5 flex flex-col border border-white/10 rounded-sm bg-graphite-900/30 overflow-hidden">
        <div className="p-3 border-b border-white/10 bg-white/5">
          <h3 className="text-[10px] font-mono text-white/50 tracking-widest uppercase">File Hierarchy</h3>
        </div>
        <div className="flex-1 overflow-y-auto mer-scroll p-2 space-y-0.5">
          {files.map((f, i) => (
            <motion.button
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              transition={{ delay: Math.min(i * 0.02, 0.5) }}
              key={f.id}
              onClick={() => setSelectedFile(f)}
              className={cn(
                "w-full text-left px-3 py-2 text-xs font-mono rounded-sm flex justify-between items-center transition-all group",
                selectedFile?.id === f.id ? "bg-mer-amber/10 border border-mer-amber/20 text-mer-amber" : "text-white/60 hover:bg-white/5 hover:text-white/90 border border-transparent"
              )}
            >
              <span className="truncate flex-1 pr-4">{f.path}</span>
              <span className={cn("text-[9px] uppercase tracking-widest px-1.5 py-0.5 rounded-sm border", selectedFile?.id === f.id ? "border-mer-amber/30 text-mer-amber/80" : "border-white/10 text-white/30 group-hover:text-white/50")}>
                {f.language}
              </span>
            </motion.button>
          ))}
        </div>
      </div>
      <div className="md:col-span-7 h-full overflow-y-auto mer-scroll pr-2">
        {selectedFile ? (
          <div className="bg-graphite-900/60 border border-white/10 rounded-sm p-6 relative">
            <div className="flex items-start justify-between mb-2">
              <h3 className="text-sm font-mono text-white break-all flex-1">{selectedFile.path}</h3>
              <div className="px-2 py-1 bg-white/5 border border-white/10 rounded-sm text-[10px] font-mono text-white/50 uppercase tracking-widest ml-4">
                {selectedFile.language}
              </div>
            </div>
            <FileIntelligence repoId={repoId} file={selectedFile} />
          </div>
        ) : (
          <div className="flex flex-col items-center justify-center h-full text-xs font-mono text-white/20 border border-white/5 border-dashed rounded-sm gap-4 p-8">
            <File size={32} className="opacity-20" />
            <span>AWAITING_FILE_SELECTION</span>
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
            <span className="text-xs font-mono text-white/60 bg-red-500/10 px-2 py-0.5 rounded" title={`Total: ${h.total_changes}`}>Changes: {h.recent_changes} recent</span>
          </div>
        </div>
      ))}
      {hotspots.length === 0 && <div className="p-4 text-xs font-mono text-white/50">No hotspots found.</div>}
    </div>
  );
}

function SearchTab({ repoId }: { repoId: number }) {
  const [query, setQuery] = useState("");
  const [mode, setMode] = useState("hybrid");
  const [results, setResults] = useState<any[]>([]);
  const [loading, setLoading] = useState(false);
  const [searched, setSearched] = useState(false);

  const doSearch = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!query) return;
    setLoading(true);
    setSearched(true);
    try {
      const res = await api.search(repoId, query, mode);
      setResults(res.results || []);
    } catch (err) {
      console.error(err);
      setResults([]);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="space-y-6">
      <form onSubmit={doSearch} className="flex gap-4">
        <input
          value={query}
          onChange={e => setQuery(e.target.value)}
          placeholder="Search semantic or lexical..."
          className="flex-1 bg-graphite-900 border border-white/10 rounded px-4 py-2 text-sm text-white focus:outline-none focus:border-mer-cyan transition-colors"
        />
        <select
          value={mode}
          onChange={e => setMode(e.target.value)}
          className="bg-graphite-900 border border-white/10 rounded px-4 py-2 text-sm text-white focus:outline-none focus:border-mer-cyan"
        >
          <option value="hybrid">Hybrid</option>
          <option value="semantic">Semantic</option>
          <option value="lexical">Lexical</option>
        </select>
        <button type="submit" disabled={loading} className="px-4 py-2 bg-white/5 border border-white/10 rounded hover:bg-white/10 transition-colors text-sm font-medium">
          {loading ? "Searching..." : "Search"}
        </button>
      </form>

      {searched && !loading && results.length === 0 && (
        <div className="p-8 text-center text-white/50 text-sm font-mono border border-white/5 border-dashed rounded bg-black/20">No results found</div>
      )}

      {results.length > 0 && (
        <div className="space-y-3">
          {results.map((r, i) => (
            <div key={i} className="p-4 bg-graphite-900 border border-white/10 rounded space-y-2">
              <div className="flex justify-between items-start">
                <div>
                  <div className="text-sm font-mono text-white/90">{r.path}</div>
                  {(r.start_line || r.end_line) && <div className="text-xs text-white/40 font-mono mt-0.5">Lines: {r.start_line}-{r.end_line}</div>}
                  {r.symbol_name && <div className="text-xs text-mer-cyan font-mono mt-0.5">{r.symbol_name} ({r.chunk_type})</div>}
                </div>
                <div className="flex gap-2 text-[10px] font-mono">
                  {r.score !== undefined && r.score !== null && <div className="px-2 py-1 bg-mer-amber/10 text-mer-amber rounded border border-mer-amber/20">Final: {r.score.toFixed(3)}</div>}
                  {r.similarity !== undefined && r.similarity !== null && <div className="px-2 py-1 bg-white/5 text-white/60 rounded border border-white/10">Semantic: {r.similarity.toFixed(3)}</div>}
                </div>
              </div>
              <pre className="text-xs font-mono text-white/70 bg-black/40 p-3 rounded overflow-x-auto whitespace-pre-wrap border border-white/5">
                {r.content}
              </pre>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

function ImpactTab({ repoId }: { repoId: number }) {
  const [path, setPath] = useState("");
  const [depth, setDepth] = useState(1);
  const [data, setData] = useState<any | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  const doAnalyze = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!path) return;
    setLoading(true);
    setError("");
    try {
      const res = await api.getImpact(repoId, path, depth);
      setData(res);
    } catch (err: unknown) {
      setError((err as Error).message || "Failed to load impact");
      setData(null);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="space-y-6">
      <form onSubmit={doAnalyze} className="flex gap-4 flex-wrap">
        <input
          value={path}
          onChange={e => setPath(e.target.value)}
          placeholder="File path (e.g., src/main.py)"
          className="flex-1 bg-graphite-900 border border-white/10 rounded px-4 py-2 text-sm text-white focus:outline-none focus:border-mer-cyan"
        />
        <input
          type="number"
          value={depth}
          onChange={e => setDepth(parseInt(e.target.value) || 1)}
          min="1" max="10"
          className="w-24 bg-graphite-900 border border-white/10 rounded px-4 py-2 text-sm text-white focus:outline-none focus:border-mer-cyan"
        />
        <button type="submit" disabled={loading} className="px-4 py-2 bg-white/5 border border-white/10 rounded hover:bg-white/10 transition-colors text-sm font-medium">
          {loading ? "Analyzing..." : "Analyze Impact"}
        </button>
      </form>

      {error && <div className="p-4 text-red-400 bg-red-950/20 border border-red-500/20 rounded text-sm">{error}</div>}

      {data && (
        <div className="space-y-6">
          <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
            <div className="mer-stat">
              <div className="mer-stat-label">Total Affected</div>
              <div className="mer-stat-value text-mer-cyan">{data.total_affected}</div>
            </div>
            <div className="mer-stat">
              <div className="mer-stat-label">Direct Dependencies</div>
              <div className="mer-stat-value">{data.direct_dependencies?.length || 0}</div>
            </div>
            <div className="mer-stat">
              <div className="mer-stat-label">Direct Dependents</div>
              <div className="mer-stat-value">{data.direct_dependents?.length || 0}</div>
            </div>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
            <div className="space-y-3">
              <h3 className="text-sm font-medium text-white/80">Direct Dependencies</h3>
              {data.direct_dependencies?.length === 0 ? (
                <div className="text-xs text-white/40 italic">None found.</div>
              ) : (
                <div className="space-y-2">
                  {data.direct_dependencies?.map((n: any, i: number) => (
                    <div key={i} className="text-xs font-mono p-2 bg-white/5 rounded border border-white/5 truncate flex justify-between">
                      <span>{n.path}</span>
                      <span className="text-white/30 text-[10px]">depth:{n.depth}</span>
                    </div>
                  ))}
                </div>
              )}
            </div>
            <div className="space-y-3">
              <h3 className="text-sm font-medium text-white/80">Direct Dependents</h3>
              {data.direct_dependents?.length === 0 ? (
                <div className="text-xs text-white/40 italic">None found.</div>
              ) : (
                <div className="space-y-2">
                  {data.direct_dependents?.map((n: any, i: number) => (
                    <div key={i} className="text-xs font-mono p-2 bg-white/5 rounded border border-white/5 truncate flex justify-between">
                      <span>{n.path}</span>
                      <span className="text-white/30 text-[10px]">depth:{n.depth}</span>
                    </div>
                  ))}
                </div>
              )}
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

function RiskTab({ repoId }: { repoId: number }) {
  const [path, setPath] = useState("");
  const [data, setData] = useState<any | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  const doAnalyze = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!path) return;
    setLoading(true);
    setError("");
    try {
      const res = await api.getRiskFeatures(repoId, path, 1);
      setData(res);
    } catch (err: unknown) {
      setError((err as Error).message || "Failed to load risk features");
      setData(null);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="space-y-6">
      <form onSubmit={doAnalyze} className="flex gap-4 flex-wrap">
        <input
          value={path}
          onChange={e => setPath(e.target.value)}
          placeholder="File path (e.g., src/main.py)"
          className="flex-1 bg-graphite-900 border border-white/10 rounded px-4 py-2 text-sm text-white focus:outline-none focus:border-mer-cyan"
        />
        <button type="submit" disabled={loading} className="px-4 py-2 bg-white/5 border border-white/10 rounded hover:bg-white/10 transition-colors text-sm font-medium">
          {loading ? "Extracting..." : "Extract Features"}
        </button>
      </form>

      {error && <div className="p-4 text-red-400 bg-red-950/20 border border-red-500/20 rounded text-sm">{error}</div>}

      {data && data.features && (
        <div className="space-y-6">
          <div className="p-4 bg-mer-cyan/5 border border-mer-cyan/20 rounded-md">
            <h3 className="text-sm font-medium text-mer-cyan flex items-center gap-2">
              <ShieldAlert size={16} /> Feature Analysis
            </h3>
            <p className="text-xs text-white/60 mt-1">
              Current computed features representing evidence for future risk prediction models. No predictive probabilities are generated in this phase.
            </p>
          </div>

          <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
            <div className="mer-stat">
              <div className="mer-stat-label">Symbols</div>
              <div className="mer-stat-value">{data.features.symbol_count}</div>
            </div>
            <div className="mer-stat">
              <div className="mer-stat-label">Functions</div>
              <div className="mer-stat-value">{data.features.function_count}</div>
            </div>
            <div className="mer-stat">
              <div className="mer-stat-label">Classes</div>
              <div className="mer-stat-value">{data.features.class_count}</div>
            </div>
            <div className="mer-stat">
              <div className="mer-stat-label">Historical Changes</div>
              <div className="mer-stat-value text-mer-amber">{data.features.historical_change_count}</div>
            </div>
            <div className="mer-stat">
              <div className="mer-stat-label">Recent Changes</div>
              <div className="mer-stat-value">{data.features.recent_change_count}</div>
            </div>
            <div className="mer-stat">
              <div className="mer-stat-label">Co-changed Files</div>
              <div className="mer-stat-value">{data.features.co_changed_file_count}</div>
            </div>
            <div className="mer-stat">
              <div className="mer-stat-label">Direct Deps</div>
              <div className="mer-stat-value">{data.features.direct_dependency_count}</div>
            </div>
            <div className="mer-stat">
              <div className="mer-stat-label">Direct Dependents</div>
              <div className="mer-stat-value">{data.features.direct_dependent_count}</div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

function ContextTab({ repoId }: { repoId: number }) {
  const [query, setQuery] = useState("");
  const [mode, setMode] = useState("hybrid");
  const [budget, setBudget] = useState<number | "">("");
  const [data, setData] = useState<any | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  const doAssemble = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!query) return;
    setLoading(true);
    setError("");
    try {
      const res = await api.getContext(repoId, query, mode, 50, budget ? Number(budget) : undefined);
      setData(res);
    } catch (err: unknown) {
      setError((err as Error).message || "Failed to assemble context");
      setData(null);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="space-y-6">
      <form onSubmit={doAssemble} className="flex gap-4 flex-wrap">
        <input
          value={query}
          onChange={e => setQuery(e.target.value)}
          placeholder="Topic or task (e.g., authentication flow)..."
          className="flex-1 bg-graphite-900 border border-white/10 rounded px-4 py-2 text-sm text-white focus:outline-none focus:border-mer-cyan transition-colors"
        />
        <select
          value={mode}
          onChange={e => setMode(e.target.value)}
          className="bg-graphite-900 border border-white/10 rounded px-4 py-2 text-sm text-white focus:outline-none focus:border-mer-cyan"
        >
          <option value="hybrid">Hybrid</option>
          <option value="semantic">Semantic</option>
          <option value="lexical">Lexical</option>
        </select>
        <input
          type="number"
          value={budget}
          onChange={e => setBudget(e.target.value ? Number(e.target.value) : "")}
          placeholder="Budget (chars)"
          className="w-32 bg-graphite-900 border border-white/10 rounded px-4 py-2 text-sm text-white focus:outline-none focus:border-mer-cyan"
        />
        <button type="submit" disabled={loading} className="px-4 py-2 bg-white/5 border border-white/10 rounded hover:bg-white/10 transition-colors text-sm font-medium">
          {loading ? "Assembling..." : "Assemble Context"}
        </button>
      </form>

      {error && <div className="p-4 text-red-400 bg-red-950/20 border border-red-500/20 rounded text-sm">{error}</div>}

      {data && (
        <div className="space-y-6">
          <div className="flex flex-wrap gap-4 p-4 border border-white/10 rounded bg-white/5 items-center justify-between">
            <div className="space-y-1">
              <h3 className="text-sm font-medium text-white/90">Context Assembly</h3>
              <p className="text-xs text-white/50">Retrieved repository context (not generated truth). Bound by character budget.</p>
            </div>
            <div className="flex gap-4 text-xs font-mono text-white/40 bg-black/20 p-2 rounded">
              <div>Chunks: <span className="text-white/80">{data.total_chunks}</span></div>
              <div>Chars: <span className="text-white/80">{data.total_characters}</span></div>
            </div>
          </div>

          <div className="space-y-4">
            {data.files?.map((f: any, i: number) => (
              <div key={i} className="border border-white/10 rounded bg-graphite-900 overflow-hidden">
                <div className="px-4 py-2 bg-white/5 border-b border-white/10 flex items-center justify-between">
                  <span className="text-sm font-mono text-white/90">{f.path}</span>
                  <span className="text-xs font-mono text-white/40">{f.chunks.length} chunks</span>
                </div>
                <div className="p-4 space-y-4">
                  {f.chunks.map((c: any, j: number) => (
                    <div key={j} className="space-y-2">
                      <div className="flex justify-between items-center text-xs font-mono text-white/50">
                        <span>{c.symbol_name || c.chunk_type}</span>
                        <div className="flex gap-2 text-[10px]">
                          {c.score !== undefined && c.score !== null && <span className="text-mer-cyan border border-mer-cyan/20 px-1 rounded">score:{c.score.toFixed(3)}</span>}
                          {c.semantic_score !== undefined && c.semantic_score !== null && <span className="text-white/40 border border-white/10 px-1 rounded">sem:{c.semantic_score.toFixed(3)}</span>}
                          {c.lexical_score !== undefined && c.lexical_score !== null && <span className="text-white/40 border border-white/10 px-1 rounded">lex:{c.lexical_score.toFixed(3)}</span>}
                        </div>
                      </div>
                      <pre className="text-xs font-mono text-white/70 bg-black/40 p-3 rounded overflow-x-auto whitespace-pre-wrap border border-white/5">
                        {c.content}
                      </pre>
                    </div>
                  ))}
                </div>
              </div>
            ))}

            {data.files?.length === 0 && (
              <div className="p-8 text-center text-white/50 text-sm font-mono border border-white/5 border-dashed rounded bg-black/20">No relevant context found within budget.</div>
            )}
          </div>
        </div>
      )}
    </div>
  );
}

export default function RepoExplorer() {
  const params = useParams();
  const id = parseInt(params.id as string, 10);

  const [repo, setRepo] = useState<Repository | null>(null);
  const [activeTab, setActiveTab] = useState<"overview" | "arch" | "files" | "history" | "hotspots" | "search" | "impact" | "risk" | "context">("overview");

  useEffect(() => {
    api.getRepository(id).then(setRepo);
  }, [id]);

  if (!repo) {
    return (
      <div className="min-h-screen mer-bg flex items-center justify-center p-8">
        <div className="flex flex-col items-center gap-4">
          <Zap className="text-mer-amber animate-pulse" size={24} />
          <div className="text-[10px] font-mono text-white/40 tracking-widest uppercase">Initializing Observatory Nexus...</div>
        </div>
      </div>
    );
  }

  const tabs = [
    { id: "overview", label: "Overview", icon: Folder },
    { id: "arch", label: "Architecture", icon: GitGraph },
    { id: "files", label: "Files", icon: File },
    { id: "history", label: "History", icon: GitCommit },
    { id: "search", label: "Search", icon: Search },
    { id: "impact", label: "Impact", icon: Zap },
    { id: "risk", label: "Risk Features", icon: ShieldAlert },
    { id: "context", label: "Context", icon: Box },
    { id: "hotspots", label: "Hotspots", icon: Flame },
  ] as const;

  return (
    <div className="min-h-screen mer-bg text-white font-sans selection:bg-mer-cyan/30">
      <header className="border-b border-white/10 bg-graphite-950/80 backdrop-blur-md sticky top-0 z-20 px-6 py-4 flex items-center justify-between">
        <div className="flex items-center gap-4">
          <Link href="/" className="text-white/40 hover:text-white/90 transition-colors">
            <ArrowLeft size={16} />
          </Link>
          <div className="h-4 w-px bg-white/10" />
          <h1 className="text-sm font-mono tracking-tight flex items-center gap-2">
            <span className="text-white/40 uppercase">Target_</span>
            <span className="text-mer-amber font-medium">{repo.url.split('/').pop()}</span>
          </h1>
        </div>
        <div className="flex items-center gap-3">
          <div className="flex items-center gap-2 text-[10px] uppercase tracking-widest text-white/30 border border-white/5 bg-white/5 px-2.5 py-1.5 rounded-sm">
            <div className={cn("w-1.5 h-1.5 rounded-full animate-pulse", repo.status === 'completed' ? "bg-mer-cyan" : repo.status === 'failed' ? "bg-mer-magenta" : "bg-mer-amber")} />
            {repo.status}
          </div>
        </div>
      </header>

      <div className="max-w-7xl mx-auto p-6 md:p-8 space-y-8">
        <nav className="flex gap-1 border-b border-white/5 pb-px overflow-x-auto mer-scroll relative">
          {tabs.map(t => (
            <button
              key={t.id}
              onClick={() => setActiveTab(t.id as any)}
              className={cn(
                "relative flex items-center gap-2 px-5 py-3 text-[11px] font-mono uppercase tracking-widest transition-colors whitespace-nowrap",
                activeTab === t.id
                  ? "text-mer-amber"
                  : "text-white/40 hover:text-white/80"
              )}
            >
              <t.icon size={14} className={activeTab === t.id ? "text-mer-amber" : "opacity-50"} />
              {t.label}
              {activeTab === t.id && (
                <motion.div
                  layoutId="activeTabIndicator"
                  className="absolute bottom-0 left-0 right-0 h-0.5 bg-mer-amber"
                  initial={false}
                  transition={{ type: "spring", stiffness: 300, damping: 30 }}
                />
              )}
            </button>
          ))}
        </nav>

        <div className="relative">
          <AnimatePresence mode="wait">
            <motion.main
              key={activeTab}
              initial={{ opacity: 0, y: 10 }}
              animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0, y: -10 }}
              transition={{ duration: 0.2 }}
              className="mer-frame p-6 rounded-sm min-h-[400px]"
            >
              {activeTab === "overview" && <OverviewTab repo={repo} />}
              {activeTab === "arch" && <ArchitectureTab repoId={id} />}
              {activeTab === "files" && <FilesTab repoId={id} />}
              {activeTab === "history" && <HistoryTab repoId={id} />}
              {activeTab === "search" && <SearchTab repoId={id} />}
              {activeTab === "impact" && <ImpactTab repoId={id} />}
              {activeTab === "risk" && <RiskTab repoId={id} />}
              {activeTab === "context" && <ContextTab repoId={id} />}
              {activeTab === "hotspots" && <HotspotsTab repoId={id} />}
            </motion.main>
          </AnimatePresence>
        </div>
      </div>
    </div>
  );
}
