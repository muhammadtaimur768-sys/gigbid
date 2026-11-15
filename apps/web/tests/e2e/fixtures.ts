import { test as base, type Page, type Route } from "@playwright/test";

/** Mocked GigBid API so the UI tests run without a backend. */

export const settings = {
  autonomy: "manual",
  rates: { hourly_floor: 45, hourly_target: 70, fixed_min: null },
  filters: { categories: [], skills: [], min_budget: null, exclude_keywords: [] },
  budgets: { weekly_connects: 80, max_connects_per_proposal: 16, max_cost_usd_per_proposal: 0.05 },
  marketplace_mode: "gigsim",
};

export const reviewer = {
  id: "u1",
  email: "reviewer@gigbid.app",
  name: "Reviewer",
  persona: "aiml",
  onboarded: true,
  settings,
};

export const inbox = {
  items: [
    {
      job_id: "job-low",
      title: "Build a Shopify theme",
      category: "Web Development",
      skills_required: ["liquid"],
      budget_type: "fixed",
      budget_min: 300,
      budget_max: 500,
      posted_at: new Date().toISOString(),
      proposals_count: 25,
      connects_cost: 8,
      fit_score: 0.31,
      recommended_action: "skip",
      risk_level: "low",
      risk_flags: [],
      price: null,
      status: "new",
      thread_id: null,
      analysed: true,
    },
    {
      job_id: "job-rag",
      title: "RAG chatbot over internal PDFs",
      category: "AI/ML",
      skills_required: ["python", "langchain", "rag"],
      budget_type: "fixed",
      budget_min: 1500,
      budget_max: 3000,
      posted_at: new Date().toISOString(),
      proposals_count: 7,
      connects_cost: 12,
      fit_score: 0.86,
      recommended_action: "bid",
      risk_level: "low",
      risk_flags: [],
      price: 2400,
      status: "drafted",
      thread_id: "t-rag",
      analysed: true,
    },
    {
      job_id: "job-scam",
      title: "Quick test task, pay via Telegram",
      category: "AI/ML",
      skills_required: ["python"],
      budget_type: "fixed",
      budget_min: 50,
      budget_max: 50,
      posted_at: new Date().toISOString(),
      proposals_count: 2,
      connects_cost: 4,
      fit_score: 0.52,
      recommended_action: "skip",
      risk_level: "high",
      risk_flags: [{ code: "off_platform_payment", severity: "high", evidence: "pay via Telegram" }],
      price: null,
      status: "new",
      thread_id: null,
      analysed: true,
    },
  ],
  total: 3,
  marketplace: "ok",
  refreshed: true,
};

export const COVER =
  "Hi, I build retrieval systems that answer from messy documents.\n\n" +
  "I shipped a RAG assistant over 40k insurance PDFs that cut lookup time by 60%.\n\n" +
  "I have led a team of 50 engineers at a large bank.\n\n" +
  "Happy to start with a short call this week.";

export const proposal = {
  thread_id: "t-rag",
  job_id: "job-rag",
  run_status: "interrupted",
  trace_id: "trace-1",
  history: [],
  pending_approval: {
    interrupt_id: "i1",
    payload: {
      draft: {
        job_id: "job-rag",
        version: 2,
        cover_letter: COVER,
        screening_answers: [{ question: "Which vector DB?", answer: "pgvector for this size." }],
      },
      type: "proposal_approval",
      claims: [
        {
          id: "c1",
          text: "I shipped a RAG assistant over 40k insurance PDFs",
          status: "supported",
          evidence_ids: ["aiml-case-03#c1"],
          action: "kept",
        },
        {
          id: "c2",
          text: "I have led a team of 50 engineers",
          status: "unsupported",
          evidence_ids: [],
          action: "kept",
        },
      ],
      unsupported_before: 2,
      unsupported_after: 1,
      // the requirement-to-evidence matrix, as the approval node sends it
      evidence: [
        {
          requirement_id: "r1",
          requirement: "RAG over PDFs",
          strength: "strong",
          evidence: [
            {
              item_id: "aiml-case-03",
              chunk_id: "aiml-case-03#c1",
              type: "case_study",
              snippet: "Retrieval assistant indexing 40,000 policy PDFs for an insurer.",
              score: 0.91,
            },
          ],
        },
      ],
      price: {
        job_id: "job-rag",
        amount: 2400,
        budget_type: "fixed",
        connects_cost: 12,
        worth_connects: true,
        rationale: "Near market p50.",
        market_p25: 1500,
        market_p50: 2300,
        market_p75: 3200,
      },
      dry_run: {
        would_send: { job_id: "job-rag", bid_amount: 2400 },
        connects_cost: 12,
        balance_after: 68,
      },
    },
  },
  view: {
    job: { id: "job-rag", title: "RAG chatbot over internal PDFs", category: "AI/ML" },
    critiques: [{ verdict: "revise", score: 6.5, reasons: ["Opening is generic"], round: 0 }],
    compliance: { allowed: true, violations: [], redactions: [], reason: "" },
    risk: { job_id: "job-rag", client_score: 0.8, is_scam: false, injection_detected: false, flags: [] },
  },
};

export type Calls = { method: string; path: string; body: unknown }[];

export interface MockOptions {
  user?: typeof reviewer | null;
  health?: Record<string, unknown> | number;
  overrides?: Record<string, (route: Route) => Promise<void> | void>;
}

function json(route: Route, data: unknown, status = 200) {
  return route.fulfill({ status, contentType: "application/json", body: JSON.stringify(data) });
}

export async function mockApi(page: Page, opts: MockOptions = {}): Promise<Calls> {
  const calls: Calls = [];
  let user = opts.user === undefined ? reviewer : opts.user;

  await page.route("**/api/**", async (route) => {
    const req = route.request();
    const url = new URL(req.url());
    const path = url.pathname;
    const method = req.method();
    let body: unknown = null;
    try {
      body = req.postDataJSON();
    } catch {
      body = req.postData();
    }
    calls.push({ method, path, body });

    const key = `${method} ${path}`;
    if (opts.overrides?.[key]) return opts.overrides[key](route);

    if (path === "/api/health") {
      if (typeof opts.health === "number") return json(route, { detail: "down" }, opts.health);
      return json(route, {
        status: "ok",
        marketplace: "ok",
        marketplace_detail: "",
        db: "ok",
        graphs: {},
        features: {},
        pending_work: 0,
        run_mode: "inline",
        version: "test",
        ...(opts.health ?? {}),
      });
    }
    if (key === "GET /api/auth/me") return user ? json(route, user) : json(route, { detail: "Not authenticated" }, 401);
    if (key === "POST /api/auth/login") {
      user = reviewer;
      return json(route, { user, access_token: "tok", token_type: "bearer" });
    }
    if (key === "POST /api/auth/register") {
      const b = body as { email: string; name: string };
      user = { ...reviewer, email: b.email, name: b.name, onboarded: false, persona: null as unknown as string };
      return json(route, { user, access_token: "tok", token_type: "bearer" }, 201);
    }
    if (key === "PUT /api/auth/onboarding") {
      const b = body as { persona: string };
      user = { ...(user ?? reviewer), persona: b.persona, onboarded: true };
      return json(route, user);
    }
    if (key === "POST /api/auth/marketplace") return json(route, { mode: "gigsim", connected: true, detail: "Connected to GigSim" });
    if (key === "POST /api/auth/portfolio") return json(route, { filename: "case.md", bytes: 42, indexed: true, detail: "" });
    if (key === "GET /api/jobs") return json(route, inbox);
    if (/^POST \/api\/jobs\/[^/]+\/skip$/.test(key)) return json(route, { ok: true, detail: "skipped" });
    if (key === "GET /api/proposals/t-rag") return json(route, proposal);
    if (/^POST \/api\/proposals\/t-rag\/(approve|edit|reject)$/.test(key)) {
      const action = path.split("/").pop();
      return json(route, { thread_id: "t-rag", status: "queued", action, approval_id: 1, stream_url: "/api/runs/t-rag/stream" });
    }
    if (key === "POST /api/proposals/t-rag/regenerate") {
      const b = body as { paragraph_index: number };
      return json(route, {
        paragraph_index: b.paragraph_index,
        paragraph: "I can start with a 30 minute scoping call on Tuesday.",
        cover_letter: COVER,
        claims: [],
        source: "heuristic",
      });
    }
    if (key === "GET /api/pipeline") return json(route, { columns: {}, marketplace: "ok" });
    if (path.endsWith("/stream")) {
      return route.fulfill({
        status: 200,
        contentType: "text/event-stream",
        body: 'event: node_start\ndata: {"node":"scout_intake"}\n\nevent: node_end\ndata: {"node":"scout_intake"}\n\nevent: done\ndata: {"status":"done"}\n\n',
      });
    }
    return json(route, { detail: `unmocked ${key}` }, 404);
  });
  return calls;
}

export const test = base;
export { expect } from "@playwright/test";
