// lib/api.ts — API client for the FastAPI backend bridge

import type {
  ChatRequest,
  ChatResponse,
  HealthResponse,
  LawDocument,
} from "@/types/chat";

const API_BASE = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

/**
 * Send a user query through the full RAG pipeline.
 * Calls POST /api/chat on the FastAPI backend.
 */
export async function sendChat(request: ChatRequest): Promise<ChatResponse> {
  const res = await fetch(`${API_BASE}/api/chat`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(request),
  });

  if (!res.ok) {
    const detail = await res.json().catch(() => ({ detail: "Unknown error" }));
    throw new Error(detail?.detail ?? `HTTP ${res.status}`);
  }

  return res.json() as Promise<ChatResponse>;
}

/**
 * Fetch backend health (Qdrant status, model info).
 * Used by the sidebar status panel.
 */
export async function fetchHealth(): Promise<HealthResponse> {
  const res = await fetch(`${API_BASE}/api/health`, {
    // Short cache — refresh every 30s on the client
    next: { revalidate: 30 },
  });
  if (!res.ok) throw new Error(`Health check failed: ${res.status}`);
  return res.json() as Promise<HealthResponse>;
}

/**
 * Fetch list of legal corpus documents for the sidebar.
 */
export async function fetchLaws(): Promise<LawDocument[]> {
  const res = await fetch(`${API_BASE}/api/laws`, {
    next: { revalidate: 3600 },
  });
  if (!res.ok) throw new Error(`Laws fetch failed: ${res.status}`);
  const data = await res.json();
  return data.documents as LawDocument[];
}
