import { useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { PageHead } from "../components/Layout";
import { ActionBadge, FitScore, RiskBadges } from "../components/RiskBadge";
import { AsyncView, Empty } from "../components/States";
import { api, type InboxJob, type JobFilters } from "../lib/api";
import { fmtMoney, timeAgo, useAsync } from "../lib/useAsync";

function budget(j: InboxJob): string {
  const hourly = j.budget_type === "hourly";
  if (j.budget_min != null && j.budget_max != null && j.budget_min !== j.budget_max)
    return `${fmtMoney(j.budget_min, hourly)} to ${fmtMoney(j.budget_max, hourly)}`;
  return fmtMoney(j.budget_max ?? j.budget_min, hourly);
}

type UIFilters = JobFilters & { hide_risky?: boolean };

export default function Inbox() {
  const nav = useNavigate();
  const [draft, setDraft] = useState<UIFilters>({ action: "", category: "", q: "" });
  const [filters, setFilters] = useState<UIFilters>({});
  const [busyId, setBusyId] = useState<string | null>(null);
  const [notice, setNotice] = useState<{ tone: "ok" | "bad"; text: string } | null>(null);
  const { hide_risky: _hide, ...serverFilters } = filters;
  const state = useAsync(() => api.listJobs(serverFilters), [JSON.stringify(serverFilters)]);

  const items = state.data?.items ?? [];
  const sorted = [...items].sort((a, b) => b.fit_score - a.fit_score);
  const categories = Array.from(new Set(items.map((i) => i.category).filter(Boolean))) as string[];

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
            Refresh
          </button>
        }
      />
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
                    <h3 style={{ marginBottom: 4 }}>
                      <Link to={`/jobs/${encodeURIComponent(j.job_id)}`}>{j.title}</Link>
                    </h3>
                    <div className="row" style={{ gap: 6, marginBottom: 6 }}>
                      <ActionBadge action={j.recommended_action} />
                      <RiskBadges flags={j.risk_flags} />
                    </div>
                    <div className="job-meta">
                      {j.category && <span>{j.category}</span>}
                      <span>Budget {budget(j)}</span>
                      <span>Our price {fmtMoney(j.price, j.budget_type === "hourly")}</span>
                      <span>{j.connects_cost ?? "?"} Connects</span>
                      {j.proposals_count != null && <span>{j.proposals_count} proposals</span>}
                      {j.posted_at && <span>{timeAgo(j.posted_at)}</span>}
                    </div>
                  </div>
                  <div className="job-actions">
                    {j.thread_id && ["drafted", "awaiting_approval"].includes(j.status) ? (
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
                </li>
              ))}
          </ul>
        )}
      </AsyncView>
    </>
  );
}
