"use client";

import { useEffect, useState } from "react";
import Link from "next/link";

interface Repository {
  id: number;
  url: string;
  status: string;
  created_at: string;
  updated_at: string;
}

export default function Home() {
  const [url, setUrl] = useState("");
  const [status, setStatus] = useState("");
  const [loading, setLoading] = useState(false);
  const [repos, setRepos] = useState<Repository[]>([]);

  // We could add an endpoint to get all repos in the future, 
  // but for now we just rely on local state to show recently submitted.

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setLoading(true);
    setStatus("");
    try {
      const apiUrl = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";
      const res = await fetch(`${apiUrl}/repositories/`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ url })
      });
      if (!res.ok) {
        const err = await res.json();
        throw new Error(err.detail || "Failed to submit");
      }
      const data = await res.json();
      setRepos((prev) => [...prev, data]);
      setUrl("");
      setStatus("Repository submitted successfully!");
    } catch (err: any) {
      setStatus(`Error: ${err.message}`);
    }
    setLoading(false);
  };

  return (
    <main className="flex min-h-screen flex-col items-center justify-start p-12 bg-zinc-950 text-white">
      <h1 className="text-4xl font-bold mb-8 tracking-tighter">Meredian Explorer</h1>
      
      <form onSubmit={handleSubmit} className="w-full max-w-lg mb-8 bg-zinc-900 p-6 rounded-lg shadow-xl border border-zinc-800">
        <label className="block mb-2 text-sm font-medium text-zinc-300">Submit GitHub URL</label>
        <div className="flex gap-4">
          <input 
            type="text" 
            required 
            placeholder="https://github.com/owner/repo" 
            value={url}
            onChange={(e) => setUrl(e.target.value)}
            className="flex-1 bg-zinc-800 border border-zinc-700 text-white text-sm rounded-lg focus:ring-emerald-500 focus:border-emerald-500 block w-full p-2.5"
          />
          <button 
            type="submit" 
            disabled={loading}
            className="text-white bg-emerald-600 hover:bg-emerald-700 font-medium rounded-lg text-sm px-5 py-2.5"
          >
            {loading ? "Submitting..." : "Ingest"}
          </button>
        </div>
        {status && <p className="mt-4 text-sm text-amber-400">{status}</p>}
      </form>

      {repos.length > 0 && (
        <div className="w-full max-w-lg">
          <h2 className="text-xl font-bold mb-4">Recent Repositories</h2>
          <div className="flex flex-col gap-3">
            {repos.map(repo => (
              <Link href={`/repo/${repo.id}`} key={repo.id} className="p-4 bg-zinc-900 border border-zinc-800 rounded-lg hover:border-emerald-500 transition-colors">
                <p className="font-semibold">{repo.url}</p>
                <p className="text-sm text-zinc-400 mt-1">Status: <span className="text-zinc-200">{repo.status}</span></p>
              </Link>
            ))}
          </div>
        </div>
      )}
    </main>
  );
}
