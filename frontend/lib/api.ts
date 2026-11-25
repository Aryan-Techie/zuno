const BACKEND_URL = process.env.NEXT_PUBLIC_BACKEND_URL || "http://localhost:8000";

/**
 * The dashboard-only endpoints (routes/admin.py::require_dashboard_session)
 * check a signed HttpOnly cookie the browser attaches on its own once
 * dashboardLogin() succeeds - the raw password is sent exactly once, to
 * /api/dashboard/login, and never stored or replayed by this client at all.
 * `credentials: "include"` is what makes the browser send/accept that
 * cookie cross-origin in local dev (frontend :3000, backend :8000); on the
 * VPS they're the same origin via Caddy, so it's a no-op there.
 */
export async function dashboardLogin(password: string): Promise<void> {
  const res = await fetch(`${BACKEND_URL}/api/dashboard/login`, {
    method: "POST",
    credentials: "include",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ password }),
  });
  if (!res.ok) throw new Error(`Login failed: ${res.status}`);
}

/** True for the specific 401 the dashboard session gate returns, so the
 * dashboard page can tell "not logged in" apart from every other failure
 * mode and re-prompt instead of just showing an error banner. */
export function isDashboardAuthError(err: unknown): boolean {
  return err instanceof Error && err.message.includes("401");
}

/** True for the login endpoint's rate-limit response, so the dashboard can
 * show "wait a few minutes" instead of "wrong password". */
export function isRateLimitError(err: unknown): boolean {
  return err instanceof Error && err.message.includes("429");
}

/**
 * Which shop Zuno is working in. "apple" sells Apple devices; "perfume" is a
 * beauty advisor for a boutique carrying Dior beauty (a demo, not affiliated
 * with Dior). The caller can switch by voice mid-call, so the console treats
 * the backend's answer as the truth rather than its own toggle.
 */
export type Mode = "apple" | "perfume";

export const MODES: Mode[] = ["apple", "perfume"];

export function isMode(value: unknown): value is Mode {
  return value === "apple" || value === "perfume";
}

/**
 * A failed request that carries its HTTP status, so a page can tell "this
 * endpoint is not there yet" (404) apart from a real failure and show a calm
 * empty state for the first instead of an error.
 */
export class ApiError extends Error {
  constructor(
    message: string,
    readonly status: number
  ) {
    super(message);
    this.name = "ApiError";
  }
}

/** True for a 404, or for a request that never reached the backend at all. */
export function isMissing(err: unknown): boolean {
  if (err instanceof ApiError) return err.status === 404;
  return err instanceof TypeError;
}

export interface StartCallResponse {
  session_id: string;
  channel_name: string;
  app_id: string;
  uid: number;
  rtc_token: string;
  rtm_token: string;
  agent_id: string | null;
  /** Absent on a backend that predates modes; the console keeps its pick. */
  mode?: Mode;
}

export interface EndCallResponse {
  session_id: string;
  status: string;
  outcome: string;
}

export async function startCall(mode?: Mode): Promise<StartCallResponse> {
  const res = await fetch(`${BACKEND_URL}/api/call/start`, {
    method: "POST",
    headers: mode ? { "Content-Type": "application/json" } : undefined,
    body: mode ? JSON.stringify({ mode }) : undefined,
  });
  if (!res.ok) throw new Error(`Failed to start call: ${res.status}`);
  return res.json();
}

/**
 * The console's own switch, mid-call. The backend changes persona, catalog,
 * knowledge base and CRM tagging on Zuno's next turn and also emits a
 * mode_changed event (by: "console"), so the event stream stays the record
 * of who switched what.
 */
export async function setSessionMode(sessionId: string, mode: Mode): Promise<{ mode: Mode }> {
  const res = await fetch(`${BACKEND_URL}/api/session/${sessionId}/mode`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ mode }),
  });
  if (!res.ok) throw new ApiError(`Failed to switch mode: ${res.status}`, res.status);
  return res.json();
}

export async function endCall(sessionId: string): Promise<EndCallResponse> {
  const res = await fetch(`${BACKEND_URL}/api/call/${sessionId}/end`, { method: "POST" });
  if (!res.ok) throw new Error(`Failed to end call: ${res.status}`);
  return res.json();
}

export interface SessionEventEnvelope {
  type: string;
  payload: Record<string, unknown>;
  ts: string;
}

/** app/memory/schema.py::LeftBrain - the CRM-shaped facts. */
export interface LeftBrain {
  name?: string | null;
  title?: string | null;
  company?: string | null;
  industry?: string | null;
  email?: string | null;
  phone?: string | null;
  user_count?: number | null;
  budget_range?: string | null;
  timeline?: string | null;
  pain_points?: string[];
  decision_stage?: string | null;
  status?: string | null;
}

export type Sentiment = "positive" | "neutral" | "skeptical" | "frustrated";

export interface Objection {
  topic: "pricing" | "trust" | "product";
  raised_text: string;
  resolution_text?: string | null;
  resolved: boolean;
  attempts: number;
}

/** app/memory/schema.py::RightBrain - the softer signals that drive the
 * escalation guardrails. Only reachable through the poll; nothing publishes
 * sentiment as an event of its own. */
export interface RightBrain {
  objections: Objection[];
  sentiment: Sentiment;
  sentiment_history: Sentiment[];
  competitor_mentions: string[];
}

export interface SessionEventsResponse {
  events: SessionEventEnvelope[];
  cursor: number;
  status: string | null;
  outcome: string | null;
  left_brain?: LeftBrain;
  right_brain?: RightBrain;
  /** The session's current mode - the truth after a voice switch. */
  mode?: Mode;
  /** The product most recently put on screen, or null. */
  spotlight?: CatalogProduct | null;
}

/* ---------------- catalog (both modes share one product shape) ---------------- */

export interface CatalogSize {
  label: string;
  price_hkd?: number | null;
  price_usd?: number | null;
}

export interface FragranceNotes {
  top: string[];
  heart: string[];
  base: string[];
}

/**
 * One product in either catalog (backend/app/catalogs/{mode}.json). Dior
 * beauty prices are in HKD; Apple prices are in USD, carried on the
 * matching _usd fields instead.
 */
export interface CatalogProduct {
  id: string;
  brand: string;
  name: string;
  line: string | null;
  /** fragrance | makeup | skincare for beauty; mac | iphone | ipad | accessory | service for Apple. */
  category: string;
  subcategory: string | null;
  gender: "women" | "men" | "unisex" | null;
  family: string | null;
  notes: FragranceNotes | null;
  key_ingredients: string[];
  description: string | null;
  sizes: CatalogSize[];
  price_hkd_from?: number | null;
  price_usd_from?: number | null;
  image_url: string | null;
  url: string | null;
  color_hex: string | null;
  aliases: string[];
  stock: number | null;
}

export interface CatalogResponse {
  mode: Mode;
  products: CatalogProduct[];
}

export async function fetchCatalog(
  mode: Mode,
  filters: { category?: string; q?: string } = {}
): Promise<CatalogResponse> {
  const params = new URLSearchParams({ mode });
  if (filters.category) params.set("category", filters.category);
  if (filters.q) params.set("q", filters.q);
  const res = await fetch(`${BACKEND_URL}/api/catalog?${params.toString()}`);
  if (!res.ok) throw new ApiError(`Failed to fetch the catalog: ${res.status}`, res.status);
  return res.json();
}

/** null when the product is unknown (404). */
export async function fetchProduct(id: string): Promise<CatalogProduct | null> {
  const res = await fetch(`${BACKEND_URL}/api/catalog/${encodeURIComponent(id)}`);
  if (res.status === 404) return null;
  if (!res.ok) throw new ApiError(`Failed to fetch the product: ${res.status}`, res.status);
  return res.json();
}

/**
 * Always the backend's copy, never the brand CDN's URL: the backend fetches
 * each image once and serves it with a long cache header, so the page never
 * hotlinks a third-party CDN and WebGL can read the pixels (same origin in
 * production, CORS-allowed in local dev).
 */
export function catalogImageUrl(id: string): string {
  return `${BACKEND_URL}/api/catalog/${encodeURIComponent(id)}/image`;
}

/* ---------------- Graphify knowledge graphs ---------------- */

export interface KnowledgeGraphStats {
  nodes: number;
  links: number;
  /** Links stated outright in our documents. */
  extracted: number;
  /** Links Graphify resolved on its own. */
  inferred: number;
  communities: number;
}

export interface KnowledgeGraph {
  mode: Mode;
  nodes: Record<string, unknown>[];
  links: Record<string, unknown>[];
  stats: KnowledgeGraphStats;
}

/** null when that mode's graph has not been built yet (404). */
export async function fetchKnowledgeGraph(mode: Mode): Promise<KnowledgeGraph | null> {
  const res = await fetch(`${BACKEND_URL}/api/knowledge-graph?mode=${mode}`);
  if (res.status === 404) return null;
  if (!res.ok) throw new ApiError(`Failed to fetch the knowledge graph: ${res.status}`, res.status);
  return res.json();
}

/* ---------------- the two session events this adds ---------------- */

/** `mode_changed`: who flipped it - the caller by voice, or this console. */
export interface ModeChangedPayload {
  mode: Mode;
  previous: Mode | null;
  by: "voice" | "console";
}

/** `product_spotlight`: the caller or Zuno named a product; show it. */
export interface ProductSpotlightPayload {
  product: CatalogProduct;
}

export function parseModeChanged(payload: Record<string, unknown>): ModeChangedPayload | null {
  if (!isMode(payload.mode)) return null;
  return {
    mode: payload.mode,
    previous: isMode(payload.previous) ? payload.previous : null,
    by: payload.by === "console" ? "console" : "voice",
  };
}

export function parseSpotlight(payload: Record<string, unknown>): ProductSpotlightPayload | null {
  const product = payload.product as CatalogProduct | undefined;
  if (!product || typeof product !== "object" || typeof product.id !== "string" || !product.name) return null;
  return { product };
}

/** app/handoff/models.py::CallSummary - the wrap-up the rep is sent. */
export interface CallSummary {
  session_id: string;
  lead_id: string | null;
  company: string | null;
  contact: string | null;
  outcome: string;
  headline: string;
  recommended_action: string;
  urgency: "now" | "today" | "this_week" | "none";
  facts: string[];
  agreed: string[];
  owed: string[];
  risks: string[];
  duration_seconds: number;
  turn_count: number;
  minutes_saved: number;
}

/**
 * The wrap-up is written in the background after End Call returns (it costs
 * a model call), so it is not there the instant the call ends. 404 until it
 * is; the caller polls.
 */
export async function fetchSummary(sessionId: string): Promise<CallSummary | null> {
  const res = await fetch(`${BACKEND_URL}/api/summaries/${sessionId}`);
  if (res.status === 404) return null;
  if (!res.ok) throw new Error(`Failed to fetch summary: ${res.status}`);
  return res.json();
}

/**
 * Polled source for the live panels.
 *
 * The backend also publishes these envelopes over Agora RTM, but they were
 * not reaching the page (the REST publish returned 200 while the browser
 * never fired its message handler). These panels are cosmetic rather than
 * call-critical, so they read from our own backend over plain HTTP, which we
 * can actually observe and debug.
 */
export async function fetchSessionEvents(
  sessionId: string,
  since: number
): Promise<SessionEventsResponse> {
  const res = await fetch(`${BACKEND_URL}/api/session/${sessionId}/events?since=${since}`);
  if (!res.ok) throw new Error(`Failed to fetch session events: ${res.status}`);
  return res.json();
}

/**
 * Layer 3, in one click: a human signing off a discount while the call is
 * still running. The backend writes the figure onto the live session and
 * Zuno offers it on her next turn - see routes/admin.py::approve_discount.
 */
export async function approveDiscount(
  escalationId: string,
  approvedPct: number,
  approvedBy = "sales manager"
): Promise<{ approved_pct: number; applied_to_live_call: boolean }> {
  const res = await fetch(`${BACKEND_URL}/api/inbox/${escalationId}/approve`, {
    method: "POST",
    headers: { "Content-Type": "application/json" }, credentials: "include",
    body: JSON.stringify({ approved_pct: approvedPct, approved_by: approvedBy }),
  });
  if (!res.ok) throw new Error(`Approval failed: ${res.status}`);
  return res.json();
}

/** app/crm/models.py::Lead - one row per lead the CRM has ever seen, across
 * every call (live and past) - the dashboard's proof of "multiple calls at
 * once", not just the single lead a live call's own panel shows. */
export interface LeadRecord {
  id: string;
  name: string | null;
  company: string | null;
  status: string;
  decision_stage: string | null;
  updated_at?: string;
}

/** app/escalation/models.py::EscalationRecord, minus the transcript/brains -
 * just enough for the dashboard's open-escalations list. */
export interface EscalationRecord {
  id: string;
  session_id: string;
  reason: string;
  kind: "handoff" | "deal_approval";
  resolved_at: string | null;
  brief: { issue: string; blocker: string; sentiment: string; recommended_action: string };
}

/** app/metrics/capacity.py::snapshot - the "how many calls at once" numbers. */
export interface CapacitySnapshot {
  calls_total: number;
  calls_live_now: number;
  peak_concurrent_calls: number;
  reps_needed_for_peak: number;
  meetings_booked: number;
  escalated_to_human: number;
  containment_rate: number;
}

export async function fetchCapacity(): Promise<CapacitySnapshot> {
  const res = await fetch(`${BACKEND_URL}/api/metrics/capacity`);
  if (!res.ok) throw new Error(`Failed to fetch capacity: ${res.status}`);
  return res.json();
}

export async function fetchLeads(): Promise<LeadRecord[]> {
  const res = await fetch(`${BACKEND_URL}/api/leads`, { credentials: "include" });
  if (!res.ok) throw new Error(`Failed to fetch leads: ${res.status}`);
  return res.json();
}

export async function fetchInbox(): Promise<EscalationRecord[]> {
  const res = await fetch(`${BACKEND_URL}/api/inbox`, { credentials: "include" });
  if (!res.ok) throw new Error(`Failed to fetch inbox: ${res.status}`);
  return res.json();
}

/** app/tasks/models.py::Task - a follow-up for a rep to work later, written
 * by the schedule_followup tool - not a meeting, not a transcript line. */
export interface TaskRecord {
  id: string;
  session_id: string;
  lead_id: string | null;
  note: string;
  due: string | null;
  completed: boolean;
  created_at: string;
}

export async function fetchTasks(): Promise<TaskRecord[]> {
  const res = await fetch(`${BACKEND_URL}/api/tasks`, { credentials: "include" });
  if (!res.ok) throw new Error(`Failed to fetch tasks: ${res.status}`);
  return res.json();
}

/** routes/admin.py::list_products - pricing.json's device_lineup joined
 * against live stock, plus anything added through createProduct below. */
export interface ProductListing {
  name: string;
  category: string | null;
  price_usd: number | null;
  note: string | null;
  stock_qty: number | null;
  status: string | null;
}

export interface ProductDraft {
  name: string;
  category?: string;
  price_usd: number;
  description?: string;
  stock_qty?: number;
}

export async function fetchProducts(): Promise<ProductListing[]> {
  const res = await fetch(`${BACKEND_URL}/api/products`, { credentials: "include" });
  if (!res.ok) throw new Error(`Failed to fetch products: ${res.status}`);
  return res.json();
}

/**
 * The backend-team upload path - routes/admin.py::create_product. Writes the
 * stock row, appends a section to custom_products.md, and drops the cached
 * RAG index, so the next question asked can already find it.
 */
export async function createProduct(draft: ProductDraft): Promise<{ sku: string; name: string; price_usd: number }> {
  const res = await fetch(`${BACKEND_URL}/api/products`, {
    method: "POST",
    headers: { "Content-Type": "application/json" }, credentials: "include",
    body: JSON.stringify(draft),
  });
  if (!res.ok) throw new Error(`Failed to add product: ${res.status}`);
  return res.json();
}

export interface LeadEdit {
  name?: string;
  title?: string;
  company?: string;
  industry?: string;
  email?: string;
  phone?: string;
  user_count?: number;
  budget_range?: string;
  timeline?: string;
}

/**
 * Typed in rather than said out loud - see routes/call.py::update_lead_manually.
 * Written through the same crm_upsert_lead path the voice tools use, so the
 * next qualification_updated event carries it and Zuno never asks again.
 */
export async function updateLeadManually(sessionId: string, edit: LeadEdit): Promise<{ lead: LeftBrain }> {
  const res = await fetch(`${BACKEND_URL}/api/session/${sessionId}/lead`, {
    method: "PATCH",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(edit),
  });
  if (!res.ok) throw new Error(`Lead update failed: ${res.status}`);
  return res.json();
}
