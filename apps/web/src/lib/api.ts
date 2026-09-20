/* eslint-disable @typescript-eslint/no-explicit-any */
const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${API_BASE}${path}`, {
    headers: { "Content-Type": "application/json", ...(init?.headers || {}) },
    ...init,
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error(err.detail || `Request failed: ${res.status}`);
  }
  return res.json();
}

export const api = {
  listRepositories: () => request<any[]>("/repositories/"),
  createRepository: (url: string) =>
    request<any>("/repositories/", { method: "POST", body: JSON.stringify({ url }) }),
  getRepository: (id: number) => request<any>(`/repositories/${id}`),
  getFiles: (id: number, page = 1, size = 50) =>
    request<any>(`/repositories/${id}/files?page=${page}&size=${size}`),
  getSymbols: (id: number, page = 1, size = 50) =>
    request<any>(`/repositories/${id}/symbols?page=${page}&size=${size}`),
  getDependencies: (id: number) =>
    request<any[]>(`/repositories/${id}/dependencies`),
  getCommits: (id: number, page = 1, limit = 50) =>
    request<any>(`/repositories/${id}/commits?page=${page}&limit=${limit}`),
  getCommitChanges: (id: number, sha: string) =>
    request<any[]>(`/repositories/${id}/commits/${sha}/changes`),
  getFileCommits: (id: number, fileId: number, page = 1, limit = 50) =>
    request<any>(`/repositories/${id}/files/${fileId}/commits?page=${page}&limit=${limit}`),
  getFileChurn: (id: number, fileId: number) =>
    request<any>(`/repositories/${id}/files/${fileId}/churn`),
  getHotspots: (id: number, limit = 20) =>
    request<any[]>(`/repositories/${id}/hotspots?limit=${limit}`),
};

export default API_BASE;