const API_URL = "";

export class ApiError extends Error {
  status: number;
  constructor(status: number, message: string) {
    super(message);
    this.status = status;
  }
}

export function isAccessError(error: unknown): boolean {
  return error instanceof ApiError && (error.status === 401 || error.status === 403);
}

export function friendlyErrorMessage(status: number, body: string): string {
  if (status === 401 || status === 403) {
    return "Operator access is required for this page.";
  }
  if (!body) {
    return status === 404 ? "Not found." : `Request failed (${status}).`;
  }
  try {
    const parsed = JSON.parse(body) as { error?: string; detail?: string; message?: string };
    if (parsed.error === "operator_session_required") {
      return "Operator access is required for this page.";
    }
    if (parsed.error === "upstream_unavailable") {
      return parsed.detail || "The catalog service is temporarily unavailable.";
    }
    if (typeof parsed.detail === "string") return parsed.detail;
    if (typeof parsed.message === "string") return parsed.message;
  } catch {
    if (!body.trim().startsWith("{") && !body.trim().startsWith("<")) return body;
  }
  if (status === 404) return "Not found.";
  return `Request failed (${status}).`;
}

async function request<T>(path: string, init: RequestInit = {}): Promise<T> {
  const headers = new Headers(init.headers);
  if (init.body && !(init.body instanceof FormData)) {
    headers.set("Content-Type", "application/json");
  }
  const res = await fetch(`${API_URL}${path}`, { ...init, headers, cache: "no-store", credentials: "same-origin" });
  if (!res.ok) {
    const text = await res.text();
    throw new ApiError(res.status, friendlyErrorMessage(res.status, text));
  }
  if (res.status === 204) return undefined as T;
  return res.json() as Promise<T>;
}

export type ModeInfo = {
  agent_mode: string;
  lookup_mode: string;
  label: string;
  is_replay: boolean;
  is_live: boolean;
  lookup_is_replay: boolean;
};

export type Batch = {
  id: string;
  name: string;
  supplier_name: string;
  status: string;
  batch_kind?: string;
  column_mapping: Record<string, string | null>;
  source_filename?: string | null;
  counts: Record<string, number>;
  created_at: string;
};

export type Product = {
  id: string;
  sku: string;
  supplier_sku?: string | null;
  title?: string | null;
  price?: string | null;
  currency?: string | null;
  status: string;
  readiness?: string | null;
  verification_passed: boolean;
  current_version_id?: string | null;
  approved_version_id?: string | null;
  store_product_id?: string | null;
  store_slug?: string | null;
  thumbnail?: string | null;
  issue_count?: number;
  enrichment_summary?: string | null;
  next_action?: string | null;
  is_publishable?: boolean;
};

export type FieldEvidence = {
  id: string;
  field_name: string;
  original_supplier_value?: unknown;
  proposed_value?: unknown;
  source_provider: string;
  source_url?: string | null;
  lookup_identifier?: string | null;
  match_outcome: string;
  match_explanation: string;
  acceptance_status: string;
  is_cached: boolean;
  is_replay: boolean;
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
    source_kind?: string;
    usage_permission?: string;
    suitability?: string;
    source_url?: string | null;
    match_rationale?: string | null;
  }>;
  is_publishable: boolean;
  import_row_number?: number | null;
  field_evidence?: FieldEvidence[];
  decisions?: Decision[];
};

export type Decision = {
  id: string;
  product_id?: string | null;
  product_version_id?: string | null;
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

export type StoreImage = {
  path: string;
  alt?: string;
  is_primary?: boolean;
  source_kind?: string | null;
  usage_permission?: string | null;
  suitability?: string | null;
  caption?: string | null;
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
  images: StoreImage[];
  sku: string;
  image_caption?: string | null;
  image_suitability?: string | null;
  specifications?: Array<{ field: string; value: string }>;
  collection?: string | null;
};

export type ListingProvenance = {
  slug: string;
  title: string;
  preparation_label: string;
  agent_mode: string;
  lookup_mode: string;
  original_row: Record<string, unknown>;
  original_fields: Array<{ field: string; label: string; value?: unknown }>;
  corrections: Array<{ field: string; label: string; original?: unknown; accepted?: unknown }>;
  evidence: Array<{
    field_name: string;
    label: string;
    original_supplier_value?: unknown;
    proposed_value?: unknown;
    source_provider: string;
    source_url?: string | null;
    match_outcome: string;
    match_explanation: string;
    is_replay: boolean;
  }>;
  assessment?: {
    match_outcome: string;
    explanation: string;
    recommended_action?: string | null;
    agreements: Array<Record<string, unknown>>;
    conflicts: Array<Record<string, unknown>>;
  } | null;
  image_caption?: string | null;
  image_suitability?: string | null;
  outcome_summary?: string | null;
};

export type ShopperCart = {
  id: string;
  purpose: string;
  items: Array<{
    id: string;
    title?: string | null;
    slug?: string | null;
    image?: string | null;
    quantity: number;
    unit_price: string;
    currency: string;
    store_product_id: string;
    available: boolean;
    stock: number;
    line_total?: string;
  }>;
  subtotal?: string;
  currency?: string;
  item_count?: number;
};

export const api = {
  mode: () => request<ModeInfo>("/api/mode"),
  workspace: () => request<{ id: string; name: string; auto_publish_demo: boolean }>("/api/workspace"),
  batches: (batchKind?: string) =>
    request<Batch[]>(batchKind ? `/api/batches?batch_kind=${batchKind}` : "/api/batches"),
  batch: (id: string) => request<Batch>(`/api/batches/${id}`),
  loadSample: () => request<Batch>("/api/demo/load-sample", { method: "POST" }),
  loadDemo: () => request<Batch>("/api/demo/load-demo", { method: "POST" }),
  loadSeiko: () => request<Batch>("/api/demo/load-seiko", { method: "POST" }),
  createBatch: (name: string, supplier_name: string) =>
    request<Batch>("/api/batches", { method: "POST", body: JSON.stringify({ name, supplier_name }) }),
  uploadCsv: async (batchId: string, file: File) => {
    const fd = new FormData();
    fd.append("file", file);
    return request<{
      mapping: Record<string, string | null>;
      headers: string[];
      preview_rows: Record<string, string>[];
    }>(`/api/batches/${batchId}/upload`, { method: "POST", body: fd });
  },
  importBatch: (batchId: string, column_mapping: Record<string, string | null>) =>
    request<Batch>(`/api/batches/${batchId}/import`, {
      method: "POST",
      body: JSON.stringify({ column_mapping }),
    }),
  session: () => request<{ authenticated: boolean }>("/api/session"),
  unlock: (token: string) =>
    request<{ authenticated: boolean }>("/api/session", { method: "POST", body: JSON.stringify({ token }) }),
  process: (id: string) => request<Job>(`/api/batches/${id}/process`, { method: "POST" }),
  publish: (id: string, productIds: string[]) =>
    request<Job>(`/api/batches/${id}/publish`, {
      method: "POST",
      body: JSON.stringify({ product_ids: productIds, verify: true }),
    }),
  products: (batchId: string, opts?: { readiness?: string; search?: string }) => {
    const params = new URLSearchParams();
    if (opts?.readiness) params.set("readiness", opts.readiness);
    if (opts?.search) params.set("search", opts.search);
    const q = params.toString();
    return request<Product[]>(`/api/batches/${batchId}/products${q ? `?${q}` : ""}`);
  },
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
  actions: (jobId: string) => request<AgentAction[]>(`/api/jobs/${jobId}/actions`),
  storeProducts: () => request<StoreProduct[]>("/api/store/products"),
  storeProduct: (slug: string) => request<StoreProduct>(`/api/store/products/${slug}`),
  listingProvenance: (slug: string) =>
    request<ListingProvenance>(`/api/store/products/${slug}/provenance`),
  cart: () => request<ShopperCart>("/api/store/cart"),
  addToCart: (store_product_id: string, quantity = 1) =>
    request<ShopperCart>("/api/store/cart/items", {
      method: "POST",
      body: JSON.stringify({ store_product_id, quantity, purpose: "shopper" }),
    }),
  updateCartItem: (store_product_id: string, quantity: number) =>
    request<ShopperCart>(`/api/store/cart/items/${store_product_id}`, {
      method: "PATCH",
      body: JSON.stringify({ quantity }),
    }),
  removeCartItem: (store_product_id: string) =>
    request<ShopperCart>(`/api/store/cart/items/${store_product_id}`, { method: "DELETE" }),
  mediaUrl: (path: string) => `/api/media/${path}`,
};

export function statusColor(status: string): string {
  if (["published", "ready", "completed", "verified", "ready_to_publish"].includes(status))
    return "text-green bg-green-soft";
  if (["needs_review", "awaiting_decisions", "pending", "needs_information"].includes(status))
    return "text-amber bg-amber-soft";
  if (["failed", "verification_failed", "has_conflicts"].includes(status))
    return "text-red bg-red-soft";
  return "text-ink-muted bg-line";
}

export function readinessLabel(r?: string | null): string {
  const map: Record<string, string> = {
    ready_to_publish: "Ready to publish",
    needs_information: "Needs information",
    has_conflicts: "Has conflicts",
    published: "Published",
  };
  return r ? map[r] || r : "Unknown";
}
