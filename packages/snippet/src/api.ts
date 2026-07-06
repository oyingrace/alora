import type { MemoraConfig } from "./config";

export interface ChatResponse {
  reply: string;
  degraded: boolean;
}

export interface RecItem {
  name: string;
  category: string;
  price: number;
  currency: string;
}

export interface RecsResponse {
  recommendations: RecItem[];
  degraded: boolean;
}

export interface BeliefItem {
  id: string;
  statement: string;
  category: string;
  confidence: number;
  status: string;
  last_reinforced_at: string;
}

export interface AuditItem {
  id: string;
  belief_id: string;
  action: string;
  reason: string;
  created_at: string;
}

export interface MemoryResponse {
  beliefs: BeliefItem[];
  audit: AuditItem[];
}

async function apiFetch<T>(
  config: MemoraConfig,
  path: string,
  init?: RequestInit
): Promise<T> {
  const response = await fetch(`${config.apiBaseUrl}${path}`, {
    headers: { "Content-Type": "application/json" },
    ...init,
  });
  if (!response.ok) {
    throw new Error(`memora api ${path} failed: ${response.status}`);
  }
  return response.json() as Promise<T>;
}

export function sendChat(
  config: MemoraConfig,
  shopperId: string,
  sessionId: string,
  message: string,
  persist: boolean
): Promise<ChatResponse> {
  return apiFetch(config, "/chat", {
    method: "POST",
    body: JSON.stringify({
      store_id: config.storeId,
      shopper_id: shopperId,
      session_id: sessionId,
      message,
      persist,
    }),
  });
}

export function getRecs(
  config: MemoraConfig,
  shopperId: string,
  query = ""
): Promise<RecsResponse> {
  const params = new URLSearchParams({ store_id: config.storeId, shopper_id: shopperId, query });
  return apiFetch(config, `/recs?${params.toString()}`);
}

export function getMemory(config: MemoraConfig, shopperId: string): Promise<MemoryResponse> {
  const params = new URLSearchParams({ store_id: config.storeId, shopper_id: shopperId });
  return apiFetch(config, `/memory?${params.toString()}`);
}

export function deleteBelief(
  config: MemoraConfig,
  beliefId: string,
  reason: string
): Promise<void> {
  const params = new URLSearchParams({ reason });
  return apiFetch(config, `/memory/${beliefId}?${params.toString()}`, { method: "DELETE" });
}
