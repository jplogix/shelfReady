const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";
const TOKEN = process.env.NEXT_PUBLIC_API_TOKEN || "dev-token-change-me";

export class ApiError extends Error {
  status: number;
  constructor(status: number, message: string) {
    super(message);
    this.status = status;
  }
}

async function request<T>(path: string, init: RequestInit = {}): Promise<T> {
  const headers = new Headers(init.headers);
  headers.set("Authorization", `Bearer ${TOKEN}`);
  if (init.body && !(init.body instanceof FormData)) {
    headers.set("Content-Type", "application/json");
  }
  const res = await fetch(`${API_URL}${path}`, { ...init, headers, cache: "no-store" });
  if (!res.ok) {
    const text = await res.text();
    throw new ApiError(res.status, text || res.statusText);
  }
  if (res.status === 204) return undefined as T;
  return res.json() as Promise<T>;
}

export type ModeInfo = {
  agent_mode: string;
  label: string;
  is_replay: boolean;
  is_live: boolean;
};

export type Batch = {
  id: string;
  name: string;
  supplier_name: string;
  status: string;
  column_mapping: Record<string, string | null>;
  source_filename?: string | null;
  counts: Record<string, number>;
  created_at: string;
};

export type Product = {
  id: string;
  sku: string;
  status: string;
  verification_passed: boolean;
  current_version_id?: string | null;
  store_product_id?: string | null;
};

export type ProductDetail = Product & {
  original?: Record<string, unknown> | null;
  proposed?: Record<string, unknown> | null;
  seo?: Record<string, unknown> | null;
  diffs: Array<{ field: string; original: unknown; proposed: unknown }>;
  blockers: Array<Record<string, unknown>>;
  provenance: Record<string, unknown>;
  images: Array<{
    id: string;
    path: string;
    class: string;
    is_primary: boolean;
    classification_source: string;
  }>;
  is_publishable: boolean;
};

export type Decision = {
  id: string;
  product_id?: string | null;
  kind: string;
  status: string;
  field_name?: string | null;
  original_value: unknown;
  proposed_value: unknown;
  evidence: Record<string, unknown>;
  reason: string;
  consequence: string;
  risk_tier: string;
  bulk_key?: string | null;
  created_at: string;
};

export type Job = {
  id: string;
  batch_id: string;
  job_type: string;
  status: string;
  agent_mode: string;
  error?: string | null;
  created_at: string;
};

export type AgentAction = {
  id: string;
  tool_name: string;
  input_payload: Record<string, unknown>;
  output_payload: Record<string, unknown>;
  success: boolean;
  evidence_summary?: string | null;
  created_at: string;
};

export type StoreProduct = {
  id: string;
  slug: string;
  title: string;
  description?: string | null;
  brand?: string | null;
  price: string;
  currency: string;
  stock: number;
  available: boolean;
  primary_image_path?: string | null;
  images: Array<{ path: string; alt?: string; is_primary?: boolean }>;
  seo: Record<string, unknown>;
  json_ld: Record<string, unknown>;
  variant_sku: string;
  external_id: string;
};

export const api = {
  mode: () => request<ModeInfo>("/api/mode"),
  workspace: () => request<{ id: string; name: string; auto_publish_demo: boolean }>("/api/workspace"),
  updateWorkspace: (body: { auto_publish_demo?: boolean }) =>
    request("/api/workspace", { method: "PATCH", body: JSON.stringify(body) }),
  batches: () => request<Batch[]>("/api/batches"),
  batch: (id: string) => request<Batch>(`/api/batches/${id}`),
  loadSample: () => request<Batch>("/api/demo/load-sample", { method: "POST" }),
  process: (id: string) => request<Job>(`/api/batches/${id}/process`, { method: "POST" }),
  publish: (id: string) => request<Job>(`/api/batches/${id}/publish`, { method: "POST" }),
  products: (batchId: string) => request<Product[]>(`/api/batches/${batchId}/products`),
  product: (id: string) => request<ProductDetail>(`/api/products/${id}`),
  decisions: (batchId: string, status = "pending") =>
    request<Decision[]>(`/api/batches/${batchId}/decisions?status=${status}`),
  resolveDecision: (
    id: string,
    body: {
      action: string;
      edited_value?: unknown;
      save_as_rule?: boolean;
      rule_type?: string;
      rule_target?: string;
    },
  ) => request<Decision>(`/api/decisions/${id}/resolve`, { method: "POST", body: JSON.stringify(body) }),
  jobs: (batchId: string) => request<Job[]>(`/api/batches/${batchId}/jobs`),
  job: (id: string) => request<Job>(`/api/jobs/${id}`),
  actions: (jobId: string) => request<AgentAction[]>(`/api/jobs/${jobId}/actions`),
  storeProducts: () => request<StoreProduct[]>("/api/store/products"),
  storeProduct: (slug: string) => request<StoreProduct>(`/api/store/products/${slug}`),
  cart: () => request<{ id: string; items: Array<{ id: string; title?: string; quantity: number; unit_price: string; currency: string; store_product_id: string }> }>("/api/store/cart"),
  addToCart: (store_product_id: string) =>
    request("/api/store/cart/items", {
      method: "POST",
      body: JSON.stringify({ store_product_id, quantity: 1, purpose: "operator" }),
    }),
  mediaUrl: (path: string) => `${API_URL}/api/media/${path}`,
};

export function statusColor(status: string): string {
  if (["published", "ready", "completed", "verified"].includes(status)) return "text-green bg-green-soft";
  if (["needs_review", "awaiting_decisions", "pending"].includes(status)) return "text-amber bg-amber-soft";
  if (["failed", "verification_failed"].includes(status)) return "text-red bg-red-soft";
  return "text-ink-muted bg-line";
}
