import { useEffect, useState } from "react";
import { useSearchParams } from "react-router-dom";
import { Dialog } from "../components/Dialog";
import { PageHead } from "../components/Layout";
import { RunTimeline } from "../components/RunTimeline";
import { AsyncView, Empty } from "../components/States";
import { api, type Slot, type ThreadDetail } from "../lib/api";
import { fmtDate, timeAgo, useAsync } from "../lib/useAsync";

type ReplyPayload = { reply?: { body?: string; proposed_slots?: Slot[] }; body?: string; proposed_slots?: Slot[]; slots?: Slot[]; intent?: { intent?: string } };

function suggestion(t: ThreadDetail): { body: string; slots: Slot[]; intent?: string } | null {
  const p = (t.pending_approval?.payload ?? {}) as ReplyPayload;
  const r = p.reply ?? t.reply ?? null;
  const body = r?.body ?? p.body;
  if (!body) return null;
  return { body, slots: r?.proposed_slots ?? p.proposed_slots ?? p.slots ?? [], intent: p.intent?.intent };
}

export default function Messages() {
  const [params, setParams] = useSearchParams();
  const list = useAsync(() => api.threads(), []);
  const selected = params.get("t") ?? list.data?.threads?.[0]?.thread_id ?? null;

  return (
    <>
      <PageHead title="Messages" sub="Client threads with suggested replies. Nothing is sent until you approve it." />
      {list.data?.marketplace === "unavailable" && (
        <div className="alert warn" style={{ marginBottom: 12 }}>
          Marketplace unavailable: showing cached threads.
        </div>
      )}
      <AsyncView
        state={list}
        rows={4}
        isEmpty={(d) => !d.threads?.length}
        empty={<Empty title="No conversations yet">When a client replies to a proposal, the thread shows up here.</Empty>}
      >
        {(d) => (
          <div className="msg-layout">
            <nav className="card" style={{ padding: 0, overflow: "hidden" }} aria-label="Threads">
              <ul className="clean">
                {d.threads.map((t) => (
                  <li key={t.thread_id}>
                    <button
                      className="thread-item"
                      aria-current={t.thread_id === selected}
                      onClick={() => setParams({ t: t.thread_id })}
                    >
                      <div className="row-between">
                        <strong className="mono small">{t.job_id ?? t.thread_id}</strong>
                        {t.unread ? <span className="badge info">{t.unread} new</span> : null}
                      </div>
                      <div className="small muted row-between">
                        <span>{t.client_id}</span>
                        <span>{timeAgo(t.last_message_at)}</span>
                      </div>
                      {t.pending_reply && <span className="badge warn">Reply awaiting approval</span>}
                    </button>
                  </li>
                ))}
              </ul>
            </nav>
            {selected ? <ThreadPane key={selected} id={selected} /> : <Empty title="Select a thread" />}
          </div>
        )}
      </AsyncView>
    </>
  );
}

function ThreadPane({ id }: { id: string }) {
  const t = useAsync(() => api.thread(id), [id]);
  const [body, setBody] = useState("");
  const [slot, setSlot] = useState<Slot | null>(null);
  const [busy, setBusy] = useState(false);
  const [runId, setRunId] = useState<string | null>(null);
  const [msg, setMsg] = useState<{ tone: "ok" | "bad"; text: string } | null>(null);
  const [rejectOpen, setRejectOpen] = useState(false);
  const [reason, setReason] = useState("");
  const sug = t.data ? suggestion(t.data) : null;

  useEffect(() => {
    if (sug) setBody(sug.body);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [sug?.body]);

  async function suggest() {
    setBusy(true);
    setMsg(null);
    try {
      const r = await api.suggestReply(id);
      setRunId(r.thread_id);
    } catch (e) {
      setMsg({ tone: "bad", text: e instanceof Error ? e.message : "Could not draft a reply" });
    } finally {
      setBusy(false);
    }
  }

  async function decide(action: "approve" | "edit" | "reject", why?: string) {
    setBusy(true);
    setMsg(null);
    try {
      await api.decideReply(id, action, { edited_text: action === "edit" ? body : undefined, reason: why, slot });
      setMsg({ tone: "ok", text: action === "reject" ? "Suggested reply discarded." : "Approved. The reply is being sent." });
      t.reload();
    } catch (e) {
      setMsg({ tone: "bad", text: e instanceof Error ? e.message : "Failed" });
    } finally {
      setBusy(false);
    }
  }

  const edited = sug && body.trim() !== sug.body.trim();
  const runRef = runId ?? (t.data?.suggestion_status && ["queued", "running"].includes(t.data.suggestion_status) ? t.data.suggestion_run : null);

  return (
    <section className="card" aria-label="Conversation">
      <AsyncView state={t} rows={5} isEmpty={() => false}>
        {(d) => (
          <div className="stack">
            <div style={{ maxHeight: 420, overflowY: "auto" }} aria-live="polite">
              {d.messages.length === 0 ? (
                <p className="muted">No messages in this thread.</p>
              ) : (
                d.messages.map((m) => (
                  <div key={m.id} className={`bubble ${m.sender === "freelancer" ? "freelancer" : "client"}`}>
                    <div className="small muted">
                      {m.sender === "freelancer" ? "You" : "Client"} · {fmtDate(m.created_at)}
                    </div>
                    {m.body}
                  </div>
                ))
              )}
            </div>
            {msg && (
              <div className={`alert ${msg.tone}`} role="status">
                {msg.text}
              </div>
            )}
            {runRef && !sug && (
              <div className="card" style={{ background: "var(--surface-2)" }}>
                <RunTimeline threadId={runRef} onDone={() => t.reload()} />
              </div>
            )}
            {sug ? (
              <div className="stack">
                <div className="row-between">
                  <h3 style={{ margin: 0 }}>Suggested reply</h3>
                  {sug.intent && <span className="badge info">intent: {sug.intent}</span>}
                </div>
                <label className="field">
                  <span className="sr-only">Reply text</span>
                  <textarea value={body} onChange={(e) => setBody(e.target.value)} rows={6} />
                </label>
                {sug.slots.length > 0 && (
                  <fieldset style={{ border: 0, padding: 0, margin: 0 }}>
                    <legend className="label">Offer an interview slot</legend>
                    <div className="row" style={{ marginTop: 6 }}>
                      {sug.slots.map((s) => (
                        <label key={s.start} className="check chip" style={{ padding: "4px 8px" }}>
                          <input type="radio" name="slot" checked={slot?.start === s.start} onChange={() => setSlot(s)} />
                          {fmtDate(s.start)}
                        </label>
                      ))}
                    </div>
                  </fieldset>
                )}
                <div className="row">
                  <button className="btn primary" disabled={busy} onClick={() => decide(edited ? "edit" : "approve")}>
                    {edited ? "Save edits and send" : "Approve and send"}
                  </button>
                  <button className="btn danger" disabled={busy} onClick={() => setRejectOpen(true)}>
                    Discard
                  </button>
                </div>
              </div>
            ) : (
              !runRef && (
                <div>
                  <button className="btn primary" onClick={suggest} disabled={busy}>
                    Suggest a reply
                  </button>
                </div>
              )
            )}
            <Dialog
              open={rejectOpen}
              title="Discard suggested reply"
              onClose={() => setRejectOpen(false)}
              actions={
                <>
                  <button className="btn" onClick={() => setRejectOpen(false)}>
                    Cancel
                  </button>
                  <button
                    className="btn danger"
                    disabled={!reason.trim()}
                    onClick={() => {
                      setRejectOpen(false);
                      void decide("reject", reason.trim());
                    }}
                  >
                    Discard
                  </button>
                </>
              }
            >
              <label className="field">
                <span>Reason</span>
                <textarea value={reason} onChange={(e) => setReason(e.target.value)} rows={3} />
              </label>
            </Dialog>
          </div>
        )}
      </AsyncView>
    </section>
  );
}
