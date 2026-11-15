import { useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { PageHead } from "../components/Layout";
import { ActionBadge, FitScore, RiskBadges } from "../components/RiskBadge";
import { Icon } from "../components/Icon";
import { AsyncView, Empty } from "../components/States";
import { api, type InboxJob, type JobFilters } from "../lib/api";
import { useAuth } from "../lib/auth";
import { fmtMoney, timeAgo, useAsync } from "../lib/useAsync";

function budget(j: InboxJob): string {
  const hourly = j.budget_type === "hourly";
  if (j.budget_min != null && j.budget_max != null && j.budget_min !== j.budget_max)
    return `${fmtMoney(j.budget_min, hourly)} to ${fmtMoney(j.budget_max, hourly)}`;
  return fmtMoney(j.budget_max ?? j.budget_min, hourly);
}

const PENDING = ["drafted", "awaiting_approval"];
const DASH = "—";

function Kpi({ label, value, meta, accent }: { label: string; value: string; meta?: string; accent?: boolean }) {
  return (
    <div className="kpi">
      <span className="l">{label}</span>
      <span className={`v ${accent ? "accent" : ""}`}>{value}</span>
      {meta && <span className="m">{meta}</span>}
    </div>
  );
}

type UIFilters = JobFilters & { hide_risky?: boolean };

export default function Inbox() {
  const nav = useNavigate();
  const { user } = useAuth();
  const [draft, setDraft] = useState<UIFilters>({ action: "", category: "", q: "" });
  const [filters, setFilters] = useState<UIFilters>({});
  const [busyId, setBusyId] = useState<string | null>(null);
  const [notice, setNotice] = useState<{ tone: "ok" | "bad"; text: string } | null>(null);
  const { hide_risky: _hide, ...serverFilters } = filters;
  const state = useAsync(() => api.listJobs(serverFilters), [JSON.stringify(serverFilters)]);

  const items = state.data?.items ?? [];
  const sorted = [...items].sort((a, b) => b.fit_score - a.fit_score);
  const categories = Array.from(new Set(items.map((i) => i.category).filter(Boolean))) as string[];

  // KPIs come only from the jobs list and the signed-in user; unknown values show a dash
  const loaded = !!state.data && !state.error;
  const weekly = user?.settings?.budgets?.weekly_connects;
  const bids = items.filter((j) => j.recommended_action === "bid");
  const bidConnects = bids.reduce((n, j) => n + (j.connects_cost ?? 0), 0);
  const pending = items.filter((j) => j.thread_id && PENDING.includes(j.status)).length;
  const kpis = (
    <section className="kpis" aria-label="Inbox summary" data-testid="kpi-strip">
      <Kpi label="Jobs in inbox" value={loaded ? String(items.length) : DASH} meta={loaded && state.data?.total != null && state.data.total !== items.length ? `${state.data.total} in total` : undefined} />
      <Kpi label="Recommended bids" value={loaded ? String(bids.length) : DASH} meta={loaded && bids.length ? `${bidConnects} Connects to bid on all` : undefined} accent={loaded && bids.length > 0} />
      <Kpi label="Connects left" value={DASH} meta={weekly != null ? `Weekly budget ${weekly}` : "Budget not set"} />
      <Kpi label="Pending approvals" value={loaded ? String(pending) : DASH} meta={loaded ? (pending ? "Drafts waiting for review" : "Nothing waiting") : undefined} />
    </section>
  );

  async function skip(j: InboxJob) {
    setBusyId(j.job_id);
    try {
      await api.skipJob(j.job_id, "Skipped from inbox");
      state.setData(state.data && { ...state.data, items: state.data.items.filter((x) => x.job_id !== j.job_id) });
      setNotice({ tone: "ok", text: `Skipped "${j.title}".` });
    } catch (e) {
      setNotice({ tone: "bad", text: e instanceof Error ? e.message : "Skip failed" });
    } finally {
      setBusyId(null);
    }
  }

  async function analyse(j: InboxJob) {
    setBusyId(j.job_id);
    try {
      const r = await api.analyseJob(j.job_id);
      if (r.thread_id) nav(`/runs/${encodeURIComponent(r.thread_id)}`);
      else setNotice({ tone: "ok", text: r.queued_degraded ? "Queued: the marketplace is unavailable, the run will retry." : `Analysis ${r.status}.` });
    } catch (e) {
      setNotice({ tone: "bad", text: e instanceof Error ? e.message : "Could not start analysis" });
    } finally {
      setBusyId(null);
    }
  }

  return (
    <>
      <PageHead
        title="Job inbox"
        sub="New jobs ranked by fit with your portfolio. Risky posts are flagged before you spend Connects."
        actions={
          <button className="btn" onClick={state.reload} disabled={state.loading}>
            <Icon name="refresh" size="sm" />
            Refresh
          </button>
        }
      />
      {kpis}
      <form
        className="card filters"
        onSubmit={(e) => {
          e.preventDefault();
          setFilters({ ...draft });
        }}
        aria-label="Filter jobs"
      >
        <label className="field">
          <span>Search</span>
          <input type="search" value={draft.q ?? ""} onChange={(e) => setDraft({ ...draft, q: e.target.value })} placeholder="Title or skill" />
        </label>
        <label className="field">
          <span>Category</span>
          <select value={draft.category ?? ""} onChange={(e) => setDraft({ ...draft, category: e.target.value })}>
            <option value="">All</option>
            {categories.map((c) => (
              <option key={c}>{c}</option>
            ))}
          </select>
        </label>
        <label className="field">
          <span>Recommendation</span>
          <select value={draft.action ?? ""} onChange={(e) => setDraft({ ...draft, action: e.target.value })} data-testid="filter-action">
            <option value="">All</option>
            <option value="bid">Bid</option>
            <option value="watch">Watch</option>
            <option value="skip">Skip</option>
          </select>
        </label>
        <label className="check" style={{ alignSelf: "center" }}>
          <input type="checkbox" checked={!!draft.hide_risky} onChange={(e) => setDraft({ ...draft, hide_risky: e.target.checked })} />
          Hide high risk
        </label>
        <button className="btn primary" type="submit">
          <Icon name="search" size="sm" />
          Apply
        </button>
      </form>

      {state.data?.marketplace === "unavailable" && (
        <div className="alert warn" style={{ marginBottom: 12 }}>
          Marketplace unavailable: showing cached jobs only.
        </div>
      )}
      {notice && (
        <div className={`alert ${notice.tone}`} role="status" style={{ marginBottom: 12 }}>
          {notice.text}
        </div>
      )}

      <AsyncView
        state={state}
        rows={6}
        isEmpty={() => sorted.filter((j) => !(filters.hide_risky && j.risk_level === "high")).length === 0}
        empty={
          <Empty title="No jobs match" action={<button className="btn" onClick={() => { setDraft({}); setFilters({}); }}>Clear filters</button>}>
            New jobs arrive from your saved searches. Try clearing filters or check back after the next scout run.
          </Empty>
        }
      >
        {() => (
          <ul className="job-list clean" data-testid="job-list">
            {sorted
              .filter((j) => !(filters.hide_risky && j.risk_level === "high"))
              .map((j) => (
                <li key={j.job_id} className="card job-row" data-testid="job-row">
                  <FitScore score={j.fit_score} />
                  <div style={{ minWidth: 0 }}>
                    <h3>
                      <Link to={`/jobs/${encodeURIComponent(j.job_id)}`}>{j.title}</Link>
                    </h3>
                    <div className="job-tags">
                      <ActionBadge action={j.recommended_action} />
                      <RiskBadges flags={j.risk_flags} />
                    </div>
                    <div className="job-meta">
                      {j.category && (
                        <span>
                          <Icon name="tag" size="sm" />
                          {j.category}
                        </span>
                      )}
                      <span>Budget {budget(j)}</span>
                      {j.proposals_count != null && (
                        <span>
                          <Icon name="users" size="sm" />
                          {j.proposals_count} proposals
                        </span>
                      )}
                      {j.posted_at && (
                        <span>
                          <Icon name="clock" size="sm" />
                          {timeAgo(j.posted_at)}
                        </span>
                      )}
                    </div>
                  </div>
                  <div className="job-side">
                    <div className="job-figures">
                      <div>
                        <span className="l">Our price</span>
                        <span className="v">{j.price != null ? fmtMoney(j.price, j.budget_type === "hourly") : DASH}</span>
                      </div>
                      <div>
                        <span className="l">Connects</span>
                        <span className="v">{j.connects_cost ?? DASH}</span>
                      </div>
                    </div>
                    <div className="job-actions">
                      {j.thread_id && PENDING.includes(j.status) ? (
                        <Link className="btn primary sm" to={`/studio/${encodeURIComponent(j.thread_id)}`}>
                          Review draft
                        </Link>
                      ) : (
                        <button className="btn primary sm" onClick={() => analyse(j)} disabled={busyId === j.job_id}>
                          {j.analysed ? "Re-run" : "Analyse"}
                        </button>
                      )}
                      <Link className="btn sm" to={`/jobs/${encodeURIComponent(j.job_id)}`}>
                        Open
                      </Link>
                      <button className="btn ghost sm" onClick={() => skip(j)} disabled={busyId === j.job_id} aria-label={`Skip ${j.title}`}>
                        Skip
                      </button>
                    </div>
                  </div>
                </li>
              ))}
          </ul>
        )}
      </AsyncView>
    </>
  );
}
