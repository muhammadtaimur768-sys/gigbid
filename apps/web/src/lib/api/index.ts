import { call, setToken } from "./client";
import type {
  AnalyseResult, Analytics, Budgets, Filters, Health, InboxResponse, JobDetail, MemoryItem,
  MemoryResponse, PipelineResponse, Proposal, Rates, RegenerateResult, ResumeResult, RunDetail, RunSummary,
  SavedSearch, SettingsResponse, Thread, ThreadDetail, Trace, User, Autonomy,
} from "./types";

export * from "./types";
export { ApiError, getToken, setToken, newTraceId } from "./client";

export interface JobFilters {
  q?: string;
  category?: string;
  action?: string;
  min_fit?: number;
  risk?: string;
  include_skipped?: boolean;
}

export interface OnboardingPayload {
  persona: string;
  rates?: Rates;
  filters?: Filters;
  budgets?: Partial<Budgets>;
  autonomy?: Autonomy;
}

export interface SettingsPatch {
  autonomy?: Autonomy;
  rates?: Rates;
  filters?: Filters;
  budgets?: Budgets;
  persona?: string;
  marketplace_mode?: "gigsim" | "upwork";
}

type AuthOut = { user: User; access_token: string };

export const api = {
  health: () => call<Health>("GET", "/api/health"),

  // auth + onboarding
  async login(email: string, password: string) {
    const r = await call<AuthOut>("POST", "/api/auth/login", { body: { email, password } });
    setToken(r.access_token);
    return r.user;
  },
  async register(email: string, password: string, name = "") {
    const r = await call<AuthOut>("POST", "/api/auth/register", { body: { email, password, name } });
    setToken(r.access_token);
    return r.user;
  },
  async logout() {
    try {
      await call("POST", "/api/auth/logout");
    } finally {
      setToken(null);
    }
  },
  me: () => call<User>("GET", "/api/auth/me"),
  saveOnboarding: (body: OnboardingPayload) => call<User>("PUT", "/api/auth/onboarding", { body }),
  connectMarketplace: (mode: "gigsim" | "upwork", token?: string) =>
    call<{ mode: string; connected: boolean; detail?: string; authorize_url?: string | null }>(
      "POST",
      "/api/auth/marketplace",
      { body: { mode, token: token || null } },
    ),
  upworkStart: () =>
    call<{ configured: boolean; authorize_url?: string | null; detail?: string }>("GET", "/api/oauth/upwork/start"),
  uploadPortfolio: (file: File) => {
    const fd = new FormData();
    fd.append("file", file);
    return call<{ filename: string; bytes: number; indexed: boolean; detail?: string }>("POST", "/api/auth/portfolio", {
      formData: fd,
    });
  },

  // jobs
  listJobs: (f: JobFilters = {}) => call<InboxResponse>("GET", "/api/jobs", { query: clean(f) }),
  job: (id: string) => call<JobDetail>("GET", "/api/jobs/{job_id}", { path: { job_id: id } }),
  skipJob: (id: string, reason?: string) =>
    call<unknown>("POST", "/api/jobs/{job_id}/skip", { path: { job_id: id }, body: { reason: reason ?? null } }),
  analyseJob: (id: string) => call<AnalyseResult>("POST", "/api/jobs/{job_id}/analyse", { path: { job_id: id } }),

  // proposals (keyed by graph thread id)
  pipeline: () => call<PipelineResponse>("GET", "/api/pipeline"),
  proposal: (threadId: string) =>
    call<Proposal>("GET", "/api/proposals/{thread_id}", { path: { thread_id: threadId } }),
  regenerateParagraph: (threadId: string, paragraph_index: number, instruction?: string) =>
    call<RegenerateResult>("POST", "/api/proposals/{thread_id}/regenerate", {
      path: { thread_id: threadId },
      body: { paragraph_index, instruction: instruction || null },
    }),
  approve: (threadId: string, note?: string) =>
    call<ResumeResult>("POST", "/api/proposals/{thread_id}/approve", {
      path: { thread_id: threadId },
      body: { note: note ?? null },
    }),
  edit: (threadId: string, edited_text: string) =>
    call<ResumeResult>("POST", "/api/proposals/{thread_id}/edit", {
      path: { thread_id: threadId },
      body: { edited_text },
    }),
  reject: (threadId: string, reason: string, category?: string) =>
    call<ResumeResult>("POST", "/api/proposals/{thread_id}/reject", {
      path: { thread_id: threadId },
      body: { reason, category: category ?? null },
    }),

  // messages
  threads: () => call<{ threads: Thread[]; marketplace: string }>("GET", "/api/messages/threads"),
  thread: (threadId: string) =>
    call<ThreadDetail>("GET", "/api/messages/threads/{mp_thread_id}", { path: { mp_thread_id: threadId } }),
  suggestReply: (threadId: string) =>
    call<RunSummary>("POST", "/api/messages/threads/{mp_thread_id}/suggest", { path: { mp_thread_id: threadId } }),
  decideReply: (
    threadId: string,
    action: "approve" | "edit" | "reject",
    extra: { edited_text?: string; reason?: string; slot?: { start: string; end: string } | null } = {},
  ) =>
    call<ResumeResult>("POST", "/api/messages/threads/{mp_thread_id}/decision", {
      path: { mp_thread_id: threadId },
      body: { action, edited_text: extra.edited_text ?? null, reason: extra.reason ?? null, slot: extra.slot ?? null },
    }),

  // runs
  runs: () => call<RunSummary[]>("GET", "/api/runs"),
  run: (threadId: string) => call<RunDetail>("GET", "/api/runs/{thread_id}", { path: { thread_id: threadId } }),
  trace: (threadId: string) => call<Trace>("GET", "/api/runs/{thread_id}/trace", { path: { thread_id: threadId } }),
  runStreamUrl: (threadId: string) => `/api/runs/${encodeURIComponent(threadId)}/stream`,

  disconnectAccount: (provider: string) =>
    call<unknown>("DELETE", "/api/settings/accounts/{provider}", { path: { provider } }),

  analytics: () => call<Analytics>("GET", "/api/analytics"),

  // settings
  settings: () => call<SettingsResponse>("GET", "/api/settings"),
  saveSettings: (s: SettingsPatch) => call<SettingsResponse>("PUT", "/api/settings", { body: s }),
  addSavedSearch: (s: Omit<SavedSearch, "id" | "last_run_at">) =>
    call<SavedSearch>("POST", "/api/settings/searches", { body: s }),
  deleteSavedSearch: (id: number) =>
    call<unknown>("DELETE", "/api/settings/searches/{sid}", { path: { sid: id } }),
  memory: () => call<MemoryResponse>("GET", "/api/settings/memory"),
  deleteMemory: (m: MemoryItem) =>
    call<unknown>("DELETE", "/api/settings/memory", { body: { namespace: m.namespace, key: m.key } }),
};

function clean(o: object): Record<string, unknown> {
  const out: Record<string, unknown> = {};
  for (const [k, v] of Object.entries(o)) if (v !== undefined && v !== "" && v !== null && v !== false) out[k] = v;
  return out;
}
