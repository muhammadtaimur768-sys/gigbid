import { useEffect, useMemo, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { ApprovalPanel } from "../components/ApprovalPanel";
import { annotate } from "../components/EvidenceHover";
import { PageHead } from "../components/Layout";
import { RiskBadges } from "../components/RiskBadge";
import { AsyncView, Empty } from "../components/States";
import {
  api, type Claim, type ComplianceVerdict, type Critique, type DryRunPreview, type EvidenceRef, type PriceQuote,
  type Proposal, type ProposalDraft, type RiskReport,
} from "../lib/api";
import { fmtMoney, useAsync } from "../lib/useAsync";

export function paragraphs(text: string): string[] {
  return (text || "").split(/\n\s*\n/).filter((p) => p.trim());
}

type Payload = {
  draft?: ProposalDraft | string;
  claims?: (Claim & { evidence?: EvidenceRef[] })[];
  evidence?: (EvidenceRef | { evidence?: EvidenceRef[] })[] | Record<string, EvidenceRef>;
  unsupported_before?: number;
  unsupported_after?: number;
  risk?: RiskReport;
  price?: PriceQuote;
  dry_run?: DryRunPreview & { unavailable?: boolean; error?: string };
  critiques?: Critique[];
  compliance?: ComplianceVerdict;
};

/** Pulls the pieces the studio needs out of the interrupt payload and checkpointed state. */
function extract(p: Proposal) {
  const payload = (p.pending_approval?.payload ?? {}) as Payload;
  const v = p.view ?? {};
  const pd = payload.draft;
  const draft: ProposalDraft | null =
    typeof pd === "string" ? { job_id: p.job_id ?? "", version: 1, cover_letter: pd } : pd ?? v.draft ?? null;
  const claims: Claim[] = payload.claims ?? draft?.claims ?? [];
  const ev = new Map<string, EvidenceRef>();
  const add = (e?: EvidenceRef) => e && e.chunk_id && ev.set(e.chunk_id, e);
  // payload.evidence is the requirement matrix (matches with nested evidence) or a flat list
  if (Array.isArray(payload.evidence))
    payload.evidence.forEach((m) => ("chunk_id" in m ? add(m as EvidenceRef) : (m as { evidence?: EvidenceRef[] }).evidence?.forEach(add)));
  else if (payload.evidence) Object.values(payload.evidence).forEach(add);
  (payload.claims ?? []).forEach((c) => c.evidence?.forEach(add));
  v.fit?.matches?.forEach((m) => m.evidence.forEach(add));
  return {
    draft,
    claims,
    evidence: ev,
    risk: payload.risk ?? v.risk ?? null,
    price: payload.price ?? v.price ?? null,
    dryRun: payload.dry_run ?? v.dry_run ?? null,
    critiques: payload.critiques ?? v.critiques ?? [],
    compliance: payload.compliance ?? v.compliance ?? null,
    title: v.job?.title ?? v.job_spec?.title ?? p.job_id ?? "Proposal",
    unsupportedBefore: payload.unsupported_before ?? draft?.unsupported_before ?? null,
    unsupportedAfter: payload.unsupported_after ?? draft?.unsupported_after ?? null,
  };
}

const LS = (id: string) => `gigbid.draft.${id}`;

export default function Studio() {
  const { id = "" } = useParams();
  const state = useAsync(() => api.proposal(id), [id]);
  return (
    <AsyncView state={state} rows={8} isEmpty={() => false}>
      {(p) => <StudioBody key={p.thread_id} p={p} reload={state.reload} />}
    </AsyncView>
  );
}

function StudioBody({ p, reload }: { p: Proposal; reload: () => void }) {
  const x = useMemo(() => extract(p), [p]);
  const original = x.draft?.cover_letter ?? "";
  const [text, setText] = useState<string>(() => {
    try {
      return localStorage.getItem(LS(p.thread_id)) ?? original;
    } catch {
      return original;
    }
  });
  const [editing, setEditing] = useState(false);
  const [busy, setBusy] = useState(false);
  const [regenIdx, setRegenIdx] = useState<number | null>(null);
  const [claims, setClaims] = useState<Claim[]>(x.claims);
  const [showPreview, setShowPreview] = useState(false);
  const [msg, setMsg] = useState<{ tone: "ok" | "bad" | "warn"; text: string } | null>(null);
  const [done, setDone] = useState<string | null>(null);
  const dirty = text.trim() !== original.trim();
  const pending = !!p.pending_approval;

  useEffect(() => {
    try {
      if (dirty) localStorage.setItem(LS(p.thread_id), text);
      else localStorage.removeItem(LS(p.thread_id));
    } catch {
      /* storage unavailable */
    }
  }, [text, dirty, p.thread_id]);

  const paras = paragraphs(text);
  const unsupported = claims.filter((c) => c.status === "unsupported");
  const blocked = x.compliance && !x.compliance.allowed;

  async function regenerate(i: number) {
    setRegenIdx(i);
    setMsg(null);
    try {
      const r = await api.regenerateParagraph(p.thread_id, i);
      const next = [...paras];
      next[i] = r.paragraph;
      setText(next.join("\n\n"));
      if (r.claims?.length) setClaims((c) => [...c, ...r.claims]);
      setMsg({ tone: "ok", text: `Paragraph ${i + 1} regenerated. Review it, then save your edits.` });
    } catch (e) {
      setMsg({ tone: "bad", text: e instanceof Error ? e.message : "Regeneration failed" });
    } finally {
      setRegenIdx(null);
    }
  }

  async function decide(kind: "approve" | "edit" | "reject", reason?: string) {
    setBusy(true);
    setMsg(null);
    try {
      if (kind === "approve") await api.approve(p.thread_id);
      else if (kind === "edit") await api.edit(p.thread_id, text);
      else await api.reject(p.thread_id, reason ?? "");
      try {
        localStorage.removeItem(LS(p.thread_id));
      } catch {
        /* ignore */
      }
      setDone(kind);
      setEditing(false);
    } catch (e) {
      setMsg({ tone: "bad", text: e instanceof Error ? e.message : "Decision failed" });
    } finally {
      setBusy(false);
    }
  }

  const lookup = (cid: string) => x.evidence.get(cid);

  return (
    <>
      <PageHead
        title={`Proposal: ${x.title}`}
        sub={`Draft v${x.draft?.version ?? 1} · run ${p.run_status}`}
        actions={
          <>
            {p.job_id && (
              <Link className="btn" to={`/jobs/${encodeURIComponent(p.job_id)}`}>
                Job detail
              </Link>
            )}
            <Link className="btn" to={`/runs/${encodeURIComponent(p.thread_id)}`}>
              Run timeline
            </Link>
          </>
        }
      />
      {done && (
        <div className="alert ok" role="status" style={{ marginBottom: 12 }} data-testid="decision-result">
          {done === "approve" && "Approved. The run resumed and is submitting the proposal."}
          {done === "edit" && "Edits saved and approved. The run resumed with your text."}
          {done === "reject" && "Rejected. Your reason was recorded and the job moved out of the inbox."}{" "}
          <Link to={`/runs/${encodeURIComponent(p.thread_id)}`}>Watch the run</Link>
        </div>
      )}
      {!pending && !done && (
        <div className="alert info" style={{ marginBottom: 12 }}>
          This run is not waiting for approval (status: {p.run_status}). The draft is read-only.
          <button className="btn sm" style={{ marginLeft: 8 }} onClick={reload}>
            Refresh
          </button>
        </div>
      )}
      {msg && (
        <div className={`alert ${msg.tone}`} role={msg.tone === "bad" ? "alert" : "status"} style={{ marginBottom: 12 }}>
          {msg.text}
        </div>
      )}

      <div className="split">
        <div>
          <section className="card" aria-labelledby="draft-h">
            <div className="card-title">
              <h2 id="draft-h">Cover letter</h2>
              <div className="row">
                <span className="small muted">{text.length} chars</span>
                <button
                  className="btn sm"
                  onClick={() => setEditing((e) => !e)}
                  disabled={!pending || !!done}
                  aria-pressed={editing}
                  data-testid="toggle-edit"
                >
                  {editing ? "Show evidence" : "Edit text"}
                </button>
                {dirty && (
                  <button className="btn ghost sm" onClick={() => setText(original)}>
                    Discard edits
                  </button>
                )}
              </div>
            </div>

            {x.critiques.length > 0 && (
              <div className="stack" style={{ gap: 4, marginBottom: 10 }}>
                {x.critiques.map((c, i) => (
                  <div key={i} className={`comment ${c.verdict === "pass" ? "ok" : ""}`} data-testid="critic-comment">
                    <strong>
                      Critic round {(c.round ?? i) + 1}: {c.verdict} ({c.score}/10)
                    </strong>
                    {c.reasons.length > 0 && <div>{c.reasons.join(" · ")}</div>}
                  </div>
                ))}
              </div>
            )}

            {!x.draft ? (
              <Empty title="No draft yet">The writer has not produced a draft for this run.</Empty>
            ) : editing ? (
              <label className="field">
                <span className="sr-only">Edit cover letter</span>
                <textarea
                  value={text}
                  onChange={(e) => setText(e.target.value)}
                  rows={Math.max(12, paras.length * 4)}
                  data-testid="draft-editor"
                />
                <span className="hint">Separate paragraphs with a blank line. Unsupported claims you add will be re-verified.</span>
              </label>
            ) : (
              <div data-testid="draft-view">
                {paras.map((para, i) => {
                  const inPara = claims.filter((c) => c.text && para.includes(c.text));
                  const bad = inPara.filter((c) => c.status === "unsupported");
                  const flagged = (x.compliance?.redactions ?? []).filter((r) => r && para.includes(r));
                  return (
                    <div key={i} className="para" data-testid="paragraph">
                      <p style={{ margin: 0, whiteSpace: "pre-wrap" }}>{annotate(para, claims, lookup)}</p>
                      {bad.map((c) => (
                        <div key={c.id} className="comment">
                          Verifier: &ldquo;{c.text.slice(0, 80)}&rdquo; has no supporting evidence.
                        </div>
                      ))}
                      {flagged.map((r) => (
                        <div key={r} className="comment compliance">
                          Compliance: &ldquo;{r}&rdquo; must be redacted.
                        </div>
                      ))}
                      <div className="para-tools">
                        <button
                          className="btn sm"
                          onClick={() => regenerate(i)}
                          disabled={!pending || regenIdx !== null || !!done}
                          aria-label={`Regenerate paragraph ${i + 1}`}
                        >
                          {regenIdx === i ? "Regenerating…" : "Regenerate"}
                        </button>
                      </div>
                    </div>
                  );
                })}
              </div>
            )}

            {x.compliance && (
              <div className={`comment ${x.compliance.allowed ? "ok" : "compliance"}`} data-testid="compliance-comment">
                <strong>Compliance: {x.compliance.allowed ? "passes the policy pack" : "blocked"}</strong>
                {x.compliance.violations.length > 0 && <div>Rules: {x.compliance.violations.join(", ")}</div>}
                {x.compliance.reason && <div>{x.compliance.reason}</div>}
              </div>
            )}

            {(x.draft?.screening_answers ?? []).length > 0 && (
              <div style={{ marginTop: 14 }}>
                <h3>Screening answers</h3>
                <dl className="stack">
                  {x.draft!.screening_answers!.map((qa, i) => (
                    <div key={i}>
                      <dt className="label">{qa.question}</dt>
                      <dd style={{ margin: 0 }}>{qa.answer}</dd>
                    </div>
                  ))}
                </dl>
              </div>
            )}
          </section>
        </div>

        <div>
          {pending && !done ? (
            <ApprovalPanel
              dirty={dirty}
              busy={busy}
              blockedReason={blocked ? "Compliance blocked this draft. Edit it or reject it." : null}
              preview={showPreview ? x.dryRun ?? { connects_cost: x.price?.connects_cost ?? null } : null}
              onPreview={() => setShowPreview(true)}
              onApprove={() => decide("approve")}
              onSaveEdit={() => decide("edit")}
              onReject={(r) => decide("reject", r)}
            />
          ) : null}
          <section className="card" aria-labelledby="checks-h">
            <h2 id="checks-h">Checks</h2>
            <dl className="kv">
              <dt>Claims</dt>
              <dd>
                {claims.length} total, <span className={unsupported.length ? "strength-none" : "strength-strong"}>{unsupported.length} unsupported</span>
              </dd>
              {x.unsupportedBefore != null && (
                <>
                  <dt>Verifier</dt>
                  <dd>
                    {x.unsupportedBefore} unsupported before, {x.unsupportedAfter ?? 0} after
                  </dd>
                </>
              )}
              {x.price && (
                <>
                  <dt>Bid</dt>
                  <dd>{fmtMoney(x.price.amount, x.price.budget_type === "hourly")}</dd>
                  <dt>Connects</dt>
                  <dd>{x.price.connects_cost}</dd>
                </>
              )}
            </dl>
            {x.risk && (
              <div style={{ marginTop: 10 }}>
                <RiskBadges flags={x.risk.flags} isScam={x.risk.is_scam} injection={x.risk.injection_detected} />
              </div>
            )}
            <div className="legend" style={{ marginTop: 12 }}>
              <span>
                <i style={{ background: "var(--ok)" }} />
                supported
              </span>
              <span>
                <i style={{ background: "var(--warn)" }} />
                partly
              </span>
              <span>
                <i style={{ background: "var(--bad)" }} />
                unsupported
              </span>
            </div>
            <p className="small muted" style={{ marginTop: 6 }}>
              Hover or focus an underlined claim to see the portfolio evidence behind it.
            </p>
          </section>
          {p.history && p.history.length > 0 && (
            <section className="card" aria-labelledby="hist-h">
              <h2 id="hist-h">Decision history</h2>
              <ul className="clean stack small">
                {p.history.map((h) => (
                  <li key={h.id}>
                    <strong>{h.action}</strong> {h.reason && <span className="muted">· {h.reason}</span>}
                  </li>
                ))}
              </ul>
            </section>
          )}
        </div>
      </div>
    </>
  );
}
