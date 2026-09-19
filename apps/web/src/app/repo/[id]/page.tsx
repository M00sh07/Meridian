"use client";

import { useEffect, useMemo, useState } from "react";
import Link from "next/link";
import { useParams } from "next/navigation";
import {
  Background,
  Controls,
  ReactFlow,
  type Edge,
  type Node,
} from "@xyflow/react";

interface Repository {
  id: number;
  url: string;
  status: string;
}

interface File {
  id: number;
  path: string;
  language: string;
}

interface Symbol {
  id: number;
  name: string;
  type: string;
  signature: string;
  start_line: number;
  file_id: number;
}

interface Dependency {
  source_file: string;
  target_file: string | null;
  imported_module: string;
}

export default function RepoExplorer() {
  const params = useParams();
  const id = params.id as string;
  const apiUrl = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

  const [repo, setRepo] = useState<Repository | null>(null);
  const [files, setFiles] = useState<File[]>([]);
  const [symbols, setSymbols] = useState<Symbol[]>([]);
  const [dependencies, setDependencies] = useState<Dependency[]>([]);
  const [activeTab, setActiveTab] = useState<"files" | "symbols" | "graph">("files");

  useEffect(() => {
    const fetchData = async () => {
      try {
        const repoRes = await fetch(`${apiUrl}/repositories/${id}`);
        if (repoRes.ok) setRepo(await repoRes.json());
        
        const filesRes = await fetch(`${apiUrl}/repositories/${id}/files`);
        if (filesRes.ok) {
          const fData = await filesRes.json();
          setFiles(fData.items);
        }
        
        const symRes = await fetch(`${apiUrl}/repositories/${id}/symbols`);
        if (symRes.ok) {
          const sData = await symRes.json();
          setSymbols(sData.items);
        }

        const dependencyRes = await fetch(`${apiUrl}/repositories/${id}/dependencies`);
        if (dependencyRes.ok) {
          setDependencies(await dependencyRes.json());
        }
      } catch (err) {}
    };
    fetchData();
    // In a real app we'd poll if status is pending/cloning/parsing
    const interval = setInterval(fetchData, 5000);
    return () => clearInterval(interval);
  }, [id, apiUrl]);

  const graph = useMemo(() => {
    const filePaths = new Set<string>();
    const resolvedDependencies = dependencies.filter((dependency) => {
      if (!dependency.target_file) return false;
      filePaths.add(dependency.source_file);
      filePaths.add(dependency.target_file);
      return true;
    });

    const nodes: Node[] = Array.from(filePaths).map((path, index) => ({
      id: path,
      position: { x: (index % 4) * 240, y: Math.floor(index / 4) * 120 },
      data: { label: path },
      style: { background: "#18181b", border: "1px solid #3f3f46", color: "#fff", width: 210 },
    }));
    const edges: Edge[] = resolvedDependencies.map((dependency, index) => ({
      id: `${dependency.source_file}-${dependency.target_file}-${index}`,
      source: dependency.source_file,
      target: dependency.target_file as string,
      animated: false,
    }));

    return { nodes, edges };
  }, [dependencies]);

  if (!repo) {
    return <div className="p-12 text-white">Loading...</div>;
  }

  return (
    <main className="flex min-h-screen flex-col items-center justify-start p-12 bg-zinc-950 text-white">
      <div className="w-full max-w-4xl">
        <Link href="/" className="text-zinc-400 hover:text-white mb-4 inline-block">&larr; Back to Home</Link>
        <div className="bg-zinc-900 p-6 rounded-lg shadow-xl border border-zinc-800 mb-8">
          <h1 className="text-3xl font-bold mb-2">{repo.url}</h1>
          <div className="flex gap-4">
            <span className="bg-zinc-800 px-3 py-1 rounded text-sm text-zinc-300">ID: {repo.id}</span>
            <span className={`px-3 py-1 rounded text-sm font-medium ${
              repo.status === 'completed' ? 'bg-emerald-900/50 text-emerald-400' :
              repo.status === 'failed' ? 'bg-red-900/50 text-red-400' : 'bg-blue-900/50 text-blue-400'
            }`}>
              {repo.status.toUpperCase()}
            </span>
          </div>
        </div>

        <div className="flex gap-4 mb-6 border-b border-zinc-800 pb-2">
          <button 
            className={`font-medium ${activeTab === 'files' ? 'text-emerald-400' : 'text-zinc-500 hover:text-zinc-300'}`}
            onClick={() => setActiveTab('files')}
          >
            Files ({files.length})
          </button>
          <button 
            className={`font-medium ${activeTab === 'symbols' ? 'text-emerald-400' : 'text-zinc-500 hover:text-zinc-300'}`}
            onClick={() => setActiveTab('symbols')}
          >
            Symbols ({symbols.length})
          </button>
          <button
            className={`font-medium ${activeTab === 'graph' ? 'text-emerald-400' : 'text-zinc-500 hover:text-zinc-300'}`}
            onClick={() => setActiveTab('graph')}
          >
            Graph
          </button>
        </div>

        {activeTab === 'files' && (
          <div className="flex flex-col gap-2">
            {files.map(f => (
              <div key={f.id} className="p-3 bg-zinc-900 border border-zinc-800 rounded flex justify-between items-center">
                <span className="font-mono text-sm">{f.path}</span>
                <span className="text-xs bg-zinc-800 px-2 py-1 rounded text-zinc-400">{f.language || 'unknown'}</span>
              </div>
            ))}
            {files.length === 0 && <p className="text-zinc-500">No files found.</p>}
          </div>
        )}

        {activeTab === 'symbols' && (
          <div className="flex flex-col gap-2">
            {symbols.map(s => (
              <div key={s.id} className="p-4 bg-zinc-900 border border-zinc-800 rounded">
                <div className="flex items-center gap-3 mb-2">
                  <span className={`text-xs px-2 py-1 rounded uppercase font-bold ${
                    s.type === 'class' ? 'bg-purple-900/50 text-purple-400' :
                    s.type === 'method' ? 'bg-amber-900/50 text-amber-400' : 'bg-blue-900/50 text-blue-400'
                  }`}>{s.type}</span>
                  <span className="font-bold">{s.name}</span>
                </div>
                <div className="text-sm font-mono text-zinc-400 bg-zinc-950 p-2 rounded overflow-x-auto whitespace-pre">
                  {s.signature}
                </div>
              </div>
            ))}
            {symbols.length === 0 && <p className="text-zinc-500">No symbols found.</p>}
          </div>
        )}

        {activeTab === 'graph' && (
          <div className="h-[600px] w-full rounded border border-zinc-800 bg-zinc-900">
            <ReactFlow nodes={graph.nodes} edges={graph.edges} fitView>
              <Background color="#3f3f46" gap={24} />
              <Controls />
            </ReactFlow>
            {graph.nodes.length === 0 && (
              <p className="p-4 text-zinc-500">No resolved dependencies found.</p>
            )}
          </div>
        )}
      </div>
    </main>
  );
}
