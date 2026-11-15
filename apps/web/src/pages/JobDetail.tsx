import { useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";
import { PageHead } from "../components/Layout";
import { ActionBadge, FitScore, RiskBadges } from "../components/RiskBadge";
import { AsyncView } from "../components/States";
import { api, type JobDetail as JD } from "../lib/api";
import { fmtMoney, timeAgo, useAsync } from "../lib/useAsync";

function Section({ title, children, id }: { title: string; children: React.ReactNode; id: string }) {
  return (
    <section className="card" aria-labelledby={id}>
      <h2 id={id}>{title}</h2>
      {children}
    </section>
  );
}

function NotYet({ what }: { what: string }) {
  return <p className="muted small">{what} appears after the job is analysed.</p>;
}

export default function JobDetail() {
  const { id = "" } = useParams();
  const nav = useNavigate();
  const state = useAsync(() => api.job(id), [id]);
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState<string | null>(null);

  async function analyse() {
    setBusy(true);
    setErr(null);
    try {
      const r = await api.analyseJob(id);
      if (r.thread_id) nav(`/runs/${encodeURIComponent(r.thread_id)}`);
      else state.reload();
    } catch (e) {
      setErr(e instanceof Error ? e.message : String(e));
    } finally {
      setBusy(false);
    }
  }

  async function skip() {
    setBusy(true);
    try {
      await api.skipJob(id, "Skipped from job detail");
      nav("/inbox");
    } catch (e) {
      setErr(e instanceof Error ? e.message : String(e));
      setBusy(false);
    }
  }

  return (
    <AsyncView state={state} rows={8} isEmpty={() => false}>
      {(d: JD) => {
        const a = d.analysis ?? {};
        const job = d.job ?? a.job ?? ({} as JD["job"]);
        const spec = a.job_spec;
        const risk = a.risk;
        const fit = a.fit;
        const decision = a.decision;
        const price = a.price;
        const hourly = (job.budget_type ?? spec?.budget_type) === "hourly";
        const awaiting = d.run_status === "interrupted" || ["drafted", "awaiting_approval"].includes(d.inbox?.status ?? "");
        return (
          <>
            <PageHead
              title={job.title ?? spec?.title ?? id}
              sub={[job.category, job.posted_at && `posted ${timeAgo(job.posted_at)}`, job.experience_level].filter(Boolean).join(" · ")}
              actions={
                <>
                  {d.thread_id && awaiting && (
                    <Link className="btn primary" to={`/studio/${encodeURIComponent(d.thread_id)}`}>
                      Open proposal studio
                    </Link>
                  )}
                  {d.thread_id && (
                    <Link className="btn" to={`/runs/${encodeURIComponent(d.thread_id)}`}>
                      View run
                    </Link>
                  )}
                  <button className="btn primary" onClick={analyse} disabled={busy}>
                    {d.thread_id ? "Re-analyse" : "Analyse"}
                  </button>
                  <button className="btn" onClick={skip} disabled={busy}>
                    Skip
                  </button>
                </>
              }
            />
            {err && (
              <div className="alert bad" role="alert" style={{ marginBottom: 12 }}>
                {err}
              </div>
            )}
            <div className="grid grid-4" style={{ marginBottom: 14 }}>
              <div className="card row">
                <FitScore score={fit?.fit_score ?? d.inbox?.fit_score} />
                <div className="stat">
                  <span className="l">Fit</span>
                  <ActionBadge action={decision?.action ?? d.inbox?.recommended_action} />
                </div>
              </div>
              <div className="card stat">
                <span className="l">Client budget</span>
                <span className="v">
                  {fmtMoney(job.budget_min, hourly)}
                  {job.budget_max != null && job.budget_max !== job.budget_min ? ` to ${fmtMoney(job.budget_max, hourly)}` : ""}
                </span>
              </div>
              <div className="card stat">
                <span className="l">Our price</span>
                <span className="v">{fmtMoney(price?.amount ?? d.inbox?.price, hourly)}</span>
              </div>
              <div className="card stat">
                <span className="l">Connects cost</span>
                <span className="v">{price?.connects_cost ?? job.connects_cost ?? "n/a"}</span>
              </div>
            </div>

            <div className="split">
              <div>
                <Section title="Job spec" id="spec-h">
                  {spec ? (
                    <div className="stack">
                      {spec.deliverables && spec.deliverables.length > 0 && (
                        <div>
                          <div className="label">Deliverables</div>
                          <ul className="bullets">
                            {spec.deliverables.map((x) => (
                              <li key={x}>{x}</li>
                            ))}
                          </ul>
                        </div>
                      )}
                      <div>
                        <div className="label">Skills</div>
                        {(spec.skills ?? []).map((s) => (
                          <span className="chip" key={s}>
                            {s}
                          </span>
                        ))}
                      </div>
                      <dl className="kv">
                        <dt>Budget type</dt>
                        <dd>{spec.budget_type}</dd>
                        {spec.timeline && (
                          <>
                            <dt>Timeline</dt>
                            <dd>{spec.timeline}</dd>
                          </>
                        )}
                      </dl>
                      {spec.hidden_needs && spec.hidden_needs.length > 0 && (
                        <div>
                          <div className="label">Hidden needs</div>
                          <ul className="bullets">
                            {spec.hidden_needs.map((x) => (
                              <li key={x}>{x}</li>
                            ))}
                          </ul>
                        </div>
                      )}
                      {spec.screening_questions && spec.screening_questions.length > 0 && (
                        <div>
                          <div className="label">Screening questions</div>
                          <ol style={{ margin: 0, paddingLeft: "1.2rem" }}>
                            {spec.screening_questions.map((x) => (
                              <li key={x}>{x}</li>
                            ))}
                          </ol>
                        </div>
                      )}
                    </div>
                  ) : (
                    <NotYet what="The structured job spec" />
                  )}
                  {job.description && (
                    <details style={{ marginTop: 10 }}>
                      <summary>Original post (untrusted text)</summary>
                      <pre style={{ marginTop: 8 }}>{job.description}</pre>
                    </details>
                  )}
                </Section>

                <Section title="Requirement to evidence matrix" id="matrix-h">
                  {fit && fit.matches.length > 0 ? (
                    <div className="table-wrap">
                      <table data-testid="evidence-matrix">
                        <thead>
                          <tr>
                            <th scope="col">Requirement</th>
                            <th scope="col">Strength</th>
                            <th scope="col">Portfolio evidence</th>
                          </tr>
                        </thead>
                        <tbody>
                          {fit.matches.map((m) => (
                            <tr key={m.requirement_id}>
                              <td>{m.requirement}</td>
                              <td className={`strength-${m.strength}`}>
                                <strong>{m.strength}</strong>
                              </td>
                              <td>
                                {m.evidence.length === 0 ? (
                                  <span className="muted">No evidence</span>
                                ) : (
                                  <ul className="clean stack" style={{ gap: 6 }}>
                                    {m.evidence.map((e) => (
                                      <li key={e.chunk_id}>
                                        <span className="badge info">{e.type}</span> <span className="mono">{e.item_id}</span>
                                        <div className="small muted">{e.snippet.slice(0, 180)}</div>
                                      </li>
                                    ))}
                                  </ul>
                                )}
                              </td>
                            </tr>
                          ))}
                        </tbody>
                      </table>
                    </div>
                  ) : (
                    <NotYet what="The requirement to evidence matrix" />
                  )}
                  {fit?.gaps && fit.gaps.length > 0 && (
                    <div className="alert warn" style={{ marginTop: 10 }}>
                      <strong>Gaps:</strong> {fit.gaps.join("; ")}
                    </div>
                  )}
                </Section>
              </div>

              <div>
                <Section title="Bid or skip" id="decision-h">
                  {decision ? (
                    <>
                      <div className="row" style={{ marginBottom: 8 }}>
                        <ActionBadge action={decision.action} />
                        <span className="small muted">confidence {Math.round(decision.confidence * 100)}%</span>
                      </div>
                      <ul className="bullets">
                        {decision.reasons.map((r, i) => (
                          <li key={i}>{r}</li>
                        ))}
                      </ul>
                    </>
                  ) : (
                    <NotYet what="The recommendation" />
                  )}
                </Section>
                <Section title="Risk report" id="risk-h">
                  {risk ? (
                    <div className="stack">
                      <RiskBadges flags={risk.flags} isScam={risk.is_scam} injection={risk.injection_detected} />
                      <dl className="kv">
                        <dt>Client score</dt>
                        <dd>{Math.round(risk.client_score * 100)} / 100</dd>
                      </dl>
                      {risk.summary && <p className="small">{risk.summary}</p>}
                      {risk.flags.map((f, i) => (
                        <div key={i} className="small">
                          <strong>{f.code.replace(/_/g, " ")}</strong>: <q>{f.evidence}</q>
                        </div>
                      ))}
                    </div>
                  ) : d.inbox ? (
                    <RiskBadges flags={d.inbox.risk_flags} />
                  ) : (
                    <NotYet what="The risk report" />
                  )}
                </Section>
                <Section title="Price rationale" id="price-h">
                  {price ? (
                    <div className="stack">
                      <dl className="kv">
                        <dt>Bid</dt>
                        <dd>{fmtMoney(price.amount, price.budget_type === "hourly")}</dd>
                        <dt>Market p25 / p50 / p75</dt>
                        <dd>
                          {fmtMoney(price.market_p25)} / {fmtMoney(price.market_p50)} / {fmtMoney(price.market_p75)}
                        </dd>
                        <dt>Connects</dt>
                        <dd>
                          {price.connects_cost}{" "}
                          <span className={`badge ${price.worth_connects ? "ok" : "warn"}`}>
                            {price.worth_connects ? "worth it" : "not worth it"}
                          </span>
                        </dd>
                      </dl>
                      <p className="small">{price.rationale}</p>
                    </div>
                  ) : (
                    <NotYet what="The price rationale" />
                  )}
                </Section>
                {d.client && (
                  <Section title="Client" id="client-h">
                    <dl className="kv small">
                      {["name", "country", "total_spent", "hires", "avg_rating", "payment_verified", "member_since"].map((k) =>
                        d.client && d.client[k] !== undefined ? (
                          <div key={k} style={{ display: "contents" }}>
                            <dt>{k.replace(/_/g, " ")}</dt>
                            <dd>{String(d.client[k])}</dd>
                          </div>
                        ) : null,
                      )}
                    </dl>
                  </Section>
                )}
              </div>
            </div>
          </>
        );
      }}
    </AsyncView>
  );
}
