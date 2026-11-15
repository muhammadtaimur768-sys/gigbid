import { useState } from "react";
import { Link, useParams } from "react-router-dom";
import { PageHead } from "../components/Layout";
import { RunTimeline } from "../components/RunTimeline";
import { AsyncView, Empty } from "../components/States";
import { api } from "../lib/api";
import { fmtDate, useAsync } from "../lib/useAsync";

function statusTone(s: string): string {
  if (["done", "completed", "submitted"].includes(s)) return "ok";
  if (["error", "dead_letter", "failed"].includes(s)) return "bad";
  if (["interrupted", "pending_retry", "needs_attention"].includes(s)) return "warn";
  return "info";
}

export function RunList() {
  const state = useAsync(() => api.runs(), []);
  return (
    <>
      <PageHead title="Agent runs" sub="Every bid and conversation run, with its trace." actions={<button className="btn" onClick={state.reload}>Refresh</button>} />
      <AsyncView state={state} rows={5} empty={<Empty title="No runs yet">Analyse a job from the inbox to start one.</Empty>}>
        {(runs) => (
          <div className="card table-wrap">
            <table>
              <thead>
                <tr>
                  <th scope="col">Run</th>
                  <th scope="col">Kind</th>
                  <th scope="col">Job</th>
                  <th scope="col">Status</th>
                  <th scope="col">Started</th>
                </tr>
              </thead>
              <tbody>
                {runs.map((r) => (
                  <tr key={r.thread_id}>
                    <td>
                      <Link className="mono" to={`/runs/${encodeURIComponent(r.thread_id)}`}>
                        {r.thread_id.slice(0, 18)}
                      </Link>
                    </td>
                    <td>{r.kind}</td>
                    <td className="mono small">{r.job_id ?? ""}</td>
                    <td>
                      <span className={`badge ${statusTone(r.status)}`}>{r.status}</span>
                    </td>
                    <td className="small muted">{fmtDate(r.created_at)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </AsyncView>
    </>
  );
}

export default function RunViewer() {
  const { id = "" } = useParams();
  const run = useAsync(() => api.run(id), [id]);
  const [traceOpen, setTraceOpen] = useState(false);
  const trace = useAsync(() => (traceOpen ? api.trace(id) : Promise.resolve(null)), [id, traceOpen]);

  return (
    <>
      <PageHead
        title="Run viewer"
        sub={id}
        actions={
          <>
            {run.data?.pending_approval && run.data.kind !== "conversation" && (
              <Link className="btn primary" to={`/studio/${encodeURIComponent(id)}`}>
                Review draft
              </Link>
            )}
            {run.data?.trace_url && (
              <a className="btn" href={run.data.trace_url} target="_blank" rel="noreferrer">
                Open full trace
              </a>
            )}
            <button className="btn" onClick={() => setTraceOpen((o) => !o)} aria-expanded={traceOpen}>
              {traceOpen ? "Hide trace events" : "Trace events"}
            </button>
          </>
        }
      />
      <div className="split">
        <section className="card" aria-labelledby="tl-h">
          <h2 id="tl-h">Live progress</h2>
          <RunTimeline threadId={id} onDone={() => run.reload()} />
        </section>
        <section className="card" aria-labelledby="meta-h">
          <h2 id="meta-h">Run</h2>
          <AsyncView state={run} rows={4} isEmpty={() => false}>
            {(r) => (
              <dl className="kv">
                <dt>Status</dt>
                <dd>
                  <span className={`badge ${statusTone(r.status)}`}>{r.status}</span>
                </dd>
                <dt>Kind</dt>
                <dd>{r.kind}</dd>
                {r.job_id && (
                  <>
                    <dt>Job</dt>
                    <dd>
                      <Link to={`/jobs/${encodeURIComponent(r.job_id)}`}>{r.job_id}</Link>
                    </dd>
                  </>
                )}
                {r.outcome && (
                  <>
                    <dt>Outcome</dt>
                    <dd>{r.outcome}</dd>
                  </>
                )}
                <dt>Trace id</dt>
                <dd className="mono small">{r.trace_id}</dd>
                <dt>Attempts</dt>
                <dd>{r.attempts ?? 1}</dd>
                {r.error && (
                  <>
                    <dt>Error</dt>
                    <dd className="strength-none small">{r.error}</dd>
                  </>
                )}
              </dl>
            )}
          </AsyncView>
        </section>
      </div>
      {traceOpen && (
        <section className="card" aria-labelledby="trace-h" style={{ marginTop: 14 }}>
          <h2 id="trace-h">Trace events</h2>
          <AsyncView state={trace} rows={4} isEmpty={(t) => !t || t.events.length === 0} empty={<Empty title="No trace events recorded" />}>
            {(t) =>
              t && (
                <div className="table-wrap">
                  {t.langsmith_url && (
                    <p>
                      <a href={t.langsmith_url} target="_blank" rel="noreferrer">
                        Open in LangSmith
                      </a>
                    </p>
                  )}
                  <table>
                    <thead>
                      <tr>
                        <th scope="col">Node</th>
                        <th scope="col">Event</th>
                        <th scope="col">Tokens in/out</th>
                        <th scope="col">Cost</th>
                        <th scope="col">Latency</th>
                      </tr>
                    </thead>
                    <tbody>
                      {t.events.map((e, i) => (
                        <tr key={i}>
                          <td className="mono">{e.node}</td>
                          <td>{e.event}</td>
                          <td>
                            {e.tokens_in ?? "-"} / {e.tokens_out ?? "-"}
                          </td>
                          <td>{e.cost_usd != null ? `$${e.cost_usd.toFixed(4)}` : "-"}</td>
                          <td>{e.latency_ms != null ? `${Math.round(e.latency_ms)} ms` : "-"}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              )
            }
          </AsyncView>
        </section>
      )}
    </>
  );
}
