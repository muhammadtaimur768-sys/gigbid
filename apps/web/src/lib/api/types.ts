// Domain shapes used by the UI. They mirror agent/handoffs.py and the API
// responses; fields are optional where the backend may omit them.

export type Persona = "aiml" | "fullstack" | "data";
export type Action = "bid" | "watch" | "skip";
export type Severity = "low" | "medium" | "high";

export interface User {
  id: string;
  email: string;
  name?: string | null;
  persona?: string | null;
  onboarded: boolean;
  settings?: UserSettings;
}

export interface Requirement {
  id: string;
  text: string;
  kind?: string;
  must_have?: boolean;
}

export interface JobSpec {
  job_id: string;
  title: string;
  category: string;
  deliverables?: string[];
  skills?: string[];
  requirements?: Requirement[];
  budget_type?: "fixed" | "hourly";
  budget_min?: number | null;
  budget_max?: number | null;
  timeline?: string | null;
  screening_questions?: string[];
  hidden_needs?: string[];
}

export interface RiskFlag {
  code: string;
  severity: Severity;
  evidence: string;
}

export interface RiskReport {
  job_id: string;
  client_score: number;
  is_scam: boolean;
  injection_detected: boolean;
  flags: RiskFlag[];
  summary?: string;
}

export interface EvidenceRef {
  item_id: string;
  chunk_id: string;
  type: string;
  snippet: string;
  score?: number;
  outcome?: string | null;
}

export interface RequirementMatch {
  requirement_id: string;
  requirement: string;
  evidence: EvidenceRef[];
  strength: "strong" | "partial" | "none";
}

export interface FitReport {
  job_id: string;
  fit_score: number;
  matches: RequirementMatch[];
  reasons?: string[];
  gaps?: string[];
}

export interface BidDecision {
  job_id: string;
  action: Action;
  confidence: number;
  reasons: string[];
}

export interface PriceQuote {
  job_id: string;
  amount: number;
  budget_type: "fixed" | "hourly";
  connects_cost: number;
  worth_connects: boolean;
  rationale: string;
  market_p25?: number | null;
  market_p50?: number | null;
  market_p75?: number | null;
}

export interface Job {
  id: string;
  title: string;
  description?: string;
  category?: string;
  skills_required?: string[];
  budget_type?: "fixed" | "hourly";
  budget_min?: number | null;
  budget_max?: number | null;
  duration?: string | null;
  posted_at?: string | null;
  client_id?: string;
  connects_cost?: number;
  proposals_count?: number;
  screening_questions?: string[];
  experience_level?: string;
}

/** A job as shown in the inbox (InboxItemOut). */
export interface InboxJob {
  job_id: string;
  title: string;
  category?: string;
  skills_required?: string[];
  budget_type?: string;
  budget_min?: number | null;
  budget_max?: number | null;
  posted_at?: string | null;
  proposals_count?: number | null;
  connects_cost?: number | null;
  fit_score: number;
  recommended_action: Action;
  risk_level: Severity;
  risk_flags: RiskFlag[];
  price?: number | null;
  status: string;
  thread_id?: string | null;
  analysed?: boolean;
}

export interface InboxResponse {
  items: InboxJob[];
  total: number;
  marketplace: "ok" | "unavailable";
  refreshed?: boolean;
}

/** Checkpointed graph state projected for the UI (StateViewOut). */
export interface StateView {
  job?: Job | null;
  job_spec?: JobSpec | null;
  risk?: RiskReport | null;
  fit?: FitReport | null;
  decision?: BidDecision | null;
  price?: PriceQuote | null;
  draft?: ProposalDraft | null;
  critiques?: Critique[];
  compliance?: ComplianceVerdict | null;
  submission?: Record<string, unknown> | null;
  status?: unknown;
  approval?: Record<string, unknown> | null;
  dry_run?: DryRunPreview | null;
  errors?: unknown[];
  reply?: Record<string, unknown> | null;
  intent?: Record<string, unknown> | null;
}

export interface JobDetail {
  job: Job;
  inbox?: InboxJob | null;
  client?: Record<string, unknown> | null;
  analysis?: StateView | null;
  run_status?: string | null;
  thread_id?: string | null;
}

export interface AnalyseResult {
  thread_id?: string | null;
  status: string;
  created?: boolean;
  queued_degraded?: boolean;
  stream_url?: string | null;
  trace_id?: string;
}

export interface Claim {
  id: string;
  text: string;
  status: "supported" | "partly_supported" | "unsupported";
  evidence_ids: string[];
  action?: "kept" | "rewritten" | "removed";
}

export interface ProposalDraft {
  job_id: string;
  version: number;
  cover_letter: string;
  screening_answers?: { question: string; answer: string }[];
  claims?: Claim[];
  unsupported_before?: number;
  unsupported_after?: number;
}

export interface Critique {
  job_id?: string;
  verdict: "pass" | "revise";
  score: number;
  reasons: string[];
  round?: number;
}

export interface ComplianceVerdict {
  job_id?: string;
  allowed: boolean;
  violations: string[];
  redactions?: string[];
  cleaned_text?: string | null;
  reason?: string;
}

export interface DryRunPreview {
  would_send?: Record<string, unknown> | null;
  connects_cost?: number | null;
  balance_after?: number | null;
}

export interface PendingApproval {
  interrupt_id?: string | null;
  payload?: unknown;
}

export interface ApprovalRecord {
  id: number;
  thread_id: string;
  action: string;
  reason?: string | null;
  diff?: Record<string, unknown> | null;
  created_at: string;
}

export interface Proposal {
  thread_id: string;
  job_id?: string | null;
  run_status: string;
  pending_approval?: PendingApproval | null;
  view: StateView;
  history?: ApprovalRecord[];
  trace_id?: string;
}

export interface ResumeResult {
  thread_id: string;
  status: string;
  action: string;
  approval_id?: number;
  stream_url?: string;
  memory?: Record<string, unknown> | null;
}

export interface RegenerateResult {
  paragraph_index: number;
  paragraph: string;
  cover_letter: string;
  claims: Claim[];
  source?: string;
}

export interface PipelineCard {
  job_id: string;
  thread_id?: string | null;
  title: string;
  category?: string;
  status: string;
  bid_amount?: number | null;
  connects_spent?: number | null;
  updated_at?: string | null;
}

export interface PipelineResponse {
  columns: Record<string, PipelineCard[]>;
  marketplace: "ok" | "unavailable";
}

export interface Thread {
  thread_id: string;
  job_id?: string | null;
  client_id?: string | null;
  proposal_id?: string | null;
  last_message_at?: string | null;
  unread?: number | null;
  pending_reply?: boolean;
}

export interface Message {
  id: string;
  sender: string;
  body: string;
  created_at?: string | null;
}

export interface ThreadDetail {
  thread_id: string;
  messages: Message[];
  suggestion_run?: string | null;
  suggestion_status?: string | null;
  pending_approval?: PendingApproval | null;
  reply?: { body?: string; proposed_slots?: Slot[]; [k: string]: unknown } | null;
}

export interface Slot {
  start: string;
  end: string;
}

export interface RunSummary {
  thread_id: string;
  kind: string;
  job_id?: string | null;
  status: string;
  outcome?: string | null;
  trace_id: string;
  trace_url?: string | null;
  error?: string | null;
  attempts?: number;
  created_at?: string;
  updated_at?: string;
}

export interface StoredRunEvent {
  id: number;
  event: string;
  data: Record<string, unknown>;
  ts: string;
}

export interface RunDetail extends RunSummary {
  events: StoredRunEvent[];
  pending_approval?: PendingApproval | null;
}

/** A UI-level timeline event. */
export interface RunEvent {
  node: string;
  event: string;
  ts?: string;
  latency_ms?: number | null;
  tokens_in?: number | null;
  tokens_out?: number | null;
  cost_usd?: number | null;
  payload?: unknown;
}

export interface TraceEvent {
  node?: string | null;
  event?: string | null;
  tokens_in?: number | null;
  tokens_out?: number | null;
  cost_usd?: number | null;
  latency_ms?: number | null;
  ts?: string | null;
  payload?: unknown;
}

export interface Trace {
  trace_id: string;
  thread_id: string;
  events: TraceEvent[];
  langsmith_url?: string | null;
  available: boolean;
}

export interface CategoryStat {
  category: string;
  proposals: number;
  replied: number;
  hired: number;
  reply_rate?: number | null;
  hire_rate?: number | null;
  connects_spent: number;
}

export interface Analytics {
  by_category: CategoryStat[];
  connects_spent_total: number;
  outcomes: Record<string, number>;
  connects_per_reply?: number | null;
  cost_per_proposal_usd?: number | null;
  latency_p50_ms?: number | null;
  latency_p95_ms?: number | null;
  runs_measured: number;
  top_rejection_reasons: { reason?: string; count?: number; [k: string]: unknown }[];
  approvals: Record<string, number>;
  per_proposal?: { thread_id: string; cost_usd?: number | null; latency_ms?: number | null }[];
  note?: string;
}

export type Autonomy = "manual" | "assisted" | "autopilot";

export interface Rates {
  hourly_floor?: number | null;
  hourly_target?: number | null;
  fixed_min?: number | null;
}

export interface Filters {
  categories: string[];
  skills: string[];
  min_budget?: number | null;
  exclude_keywords?: string[];
}

export interface Budgets {
  weekly_connects: number;
  max_connects_per_proposal: number;
  max_cost_usd_per_proposal: number;
}

export interface UserSettings {
  autonomy: Autonomy;
  rates: Rates;
  filters: Filters;
  budgets: Budgets;
  marketplace_mode: "gigsim" | "upwork";
}

export interface SavedSearch {
  id: number;
  name: string;
  query: string;
  category?: string | null;
  skills: string[];
  interval_minutes: number;
  enabled: boolean;
  last_run_at?: string | null;
}

export interface ConnectedAccount {
  provider: string;
  connected: boolean;
  scope?: string;
  expires_at?: string | null;
}

export interface SettingsResponse {
  persona?: string | null;
  settings: UserSettings;
  saved_searches: SavedSearch[];
  accounts: ConnectedAccount[];
}

export interface MemoryItem {
  namespace: string[];
  key: string;
  value: unknown;
  kind: string;
  created_at?: string | null;
  updated_at?: string | null;
}

export interface MemoryResponse {
  items: MemoryItem[];
  available: boolean;
}

export interface Health {
  status: "ok" | "degraded" | string;
  marketplace: "ok" | "unavailable" | string;
  marketplace_detail?: string;
  db?: string;
  graphs?: Record<string, string>;
  features?: Record<string, boolean>;
  pending_work?: number;
  run_mode?: string;
  version?: string;
}
