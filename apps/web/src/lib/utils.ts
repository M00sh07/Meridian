import { clsx, type ClassValue } from "clsx";
import { twMerge } from "tailwind-merge";

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs));
}

export function formatBytes(bytes: number): string {
  if (bytes === 0) return "0 B";
  const k = 1024;
  const sizes = ["B", "KB", "MB", "GB"];
  const i = Math.floor(Math.log(bytes) / Math.log(k));
  return `${(bytes / Math.pow(k, i)).toFixed(i === 0 ? 0 : 1)} ${sizes[i]}`;
}

export function shortSha(sha: string): string {
  return sha.length > 10 ? sha.slice(0, 7) : sha;
}

export function timeAgo(date: Date | string): string {
  const d = new Date(date);
  const now = new Date();
  const s = Math.floor((now.getTime() - d.getTime()) / 1000);
  if (s < 60) return `${s}s`;
  const m = Math.floor(s / 60);
  if (m < 60) return `${m}m`;
  const h = Math.floor(m / 60);
  if (h < 24) return `${h}h`;
  const day = Math.floor(h / 24);
  if (day < 30) return `${day}d`;
  const mo = Math.floor(day / 30);
  if (mo < 12) return `${mo}mo`;
  return `${Math.floor(mo / 12)}y`;
}

export function formatDate(date: Date | string): string {
  return new Date(date).toLocaleDateString("en-US", {
    month: "short", day: "numeric", year: "numeric",
  });
}

export function languageColor(lang: string | null): string {
  const map: Record<string, string> = {
    typescript: "text-mer-cyan",
    javascript: "text-mer-amber",
    python: "text-mer-amber",
    java: "text-mer-amber",
    go: "text-mer-cyan",
    rust: "text-mer-magenta",
    ruby: "text-mer-amber",
    c: "text-mer-cyan",
    cpp: "text-mer-cyan",
    csharp: "text-mer-cyan",
  };
  return map[(lang || "").toLowerCase()] || "text-white/50";
}