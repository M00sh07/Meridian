"use client";

import { useEffect, useState } from "react";

export default function Home() {
  const [healthStatus, setHealthStatus] = useState<string>("Checking...");
  
  useEffect(() => {
    const checkHealth = async () => {
      try {
        const apiUrl = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";
        const res = await fetch(`${apiUrl}/health`);
        if (res.ok) {
          const data = await res.json();
          setHealthStatus(`API Reachable (Status: ${data.status})`);
        } else {
          setHealthStatus(`API Error (Status Code: ${res.status})`);
        }
      } catch (err) {
        setHealthStatus("API Unreachable");
      }
    };
    checkHealth();
  }, []);

  return (
    <main className="flex min-h-screen flex-col items-center justify-center p-24 bg-zinc-950 text-white">
      <h1 className="text-4xl font-bold mb-8 tracking-tighter">Meredian</h1>
      <div className="p-6 border border-zinc-800 rounded-lg bg-zinc-900 shadow-xl min-w-[300px] text-center">
        <h2 className="text-xl font-semibold mb-4 text-zinc-300">System Status</h2>
        <div className="flex items-center justify-center gap-3">
          <div className={`w-3 h-3 rounded-full ${healthStatus.includes('Reachable') ? 'bg-emerald-500 shadow-[0_0_10px_rgba(16,185,129,0.5)]' : healthStatus === 'Checking...' ? 'bg-blue-500 animate-pulse' : 'bg-red-500 shadow-[0_0_10px_rgba(239,68,68,0.5)]'}`}></div>
          <p className="text-lg font-medium text-zinc-100">
            {healthStatus}
          </p>
        </div>
      </div>
    </main>
  );
}
