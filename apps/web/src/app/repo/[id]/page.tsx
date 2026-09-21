/* eslint-disable @typescript-eslint/no-explicit-any */
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
import { GitCommit, GitGraph, File, History, Flame, Folder, AlertTriangle, ArrowRight, ArrowLeft, Search, Zap, ShieldAlert, Box } from "lucide-react";
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
    { id: "search", label: "Search", icon: Search },
    { id: "impact", label: "Impact", icon: Zap },
    { id: "risk", label: "Risk Features", icon: ShieldAlert },
    { id: "context", label: "Context", icon: Box },
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
        <nav className="flex gap-1 border-b border-white/5 pb-px overflow-x-auto mer-scroll">
          {tabs.map(t => (
            <button
              key={t.id}
              onClick={() => setActiveTab(t.id as 'overview' | 'arch' | 'files' | 'history' | 'hotspots' | 'search' | 'impact' | 'risk' | 'context')}
              className={cn(
                "flex items-center gap-2 px-4 py-2.5 text-xs font-medium uppercase tracking-wider transition-all border-b-2 whitespace-nowrap",
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
          {activeTab === "search" && <SearchTab repoId={id} />}
          {activeTab === "impact" && <ImpactTab repoId={id} />}
          {activeTab === "risk" && <RiskTab repoId={id} />}
          {activeTab === "context" && <ContextTab repoId={id} />}
          {activeTab === "hotspots" && <HotspotsTab repoId={id} />}
        </main>
      </div>
    </div>
  );
}
