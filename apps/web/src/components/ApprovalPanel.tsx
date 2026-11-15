import { useState } from "react";
import { Dialog } from "./Dialog";
import type { DryRunPreview } from "../lib/api";

export const REJECT_REASONS = [
  "Weak fit for this job",
  "Price is wrong",
  "Tone or style is off",
  "Unsupported claims",
  "Client looks risky",
  "Other",
];

/**
 * Human-in-the-loop decision for an interrupted bid run. Approve resumes the
 * graph with the current text; Edit resumes with the edited text; Reject
 * requires a reason that feeds analytics and memory.
 */
export function ApprovalPanel({
  dirty,
  busy,
  disabled,
  blockedReason,
  preview,
  onPreview,
  onApprove,
  onSaveEdit,
  onReject,
}: {
  dirty: boolean;
  busy: boolean;
  disabled?: boolean;
  blockedReason?: string | null;
  preview?: DryRunPreview | null;
  onPreview: () => void;
  onApprove: () => void;
  onSaveEdit: () => void;
  onReject: (reason: string) => void;
}) {
  const [rejectOpen, setRejectOpen] = useState(false);
  const [confirmOpen, setConfirmOpen] = useState(false);
  const [reason, setReason] = useState(REJECT_REASONS[0]);
  const [note, setNote] = useState("");
  const finalReason = reason === "Other" ? note.trim() : note.trim() ? `${reason}: ${note.trim()}` : reason;

  return (
    <section className="card approval-card" aria-labelledby="approval-h">
      <div className="card-title">
        <h2 id="approval-h">Approval</h2>
        {dirty && <span className="badge warn">Unsaved edits</span>}
      </div>
      {blockedReason && (
        <div className="alert bad" style={{ marginBottom: 10 }}>
          {blockedReason}
        </div>
      )}
      <div className="stack">
        <button className="btn" onClick={onPreview} disabled={busy || disabled} data-testid="dry-run">
          Preview send (dry run)
        </button>
        {preview && (preview as { unavailable?: boolean; error?: string }).error && (
          <div className="alert warn" data-testid="dry-run-error">
            Dry run unavailable: {(preview as { error?: string }).error}
          </div>
        )}
        {preview && !(preview as { error?: string }).error && (
          <div className="alert info" data-testid="dry-run-preview">
            <div className="row-between">
              <strong>Dry run: nothing was sent</strong>
            </div>
            <dl className="kv" style={{ marginTop: 6 }}>
              <dt>Connects cost</dt>
              <dd data-testid="dry-run-cost">{preview.connects_cost ?? "n/a"}</dd>
              <dt>Balance after</dt>
              <dd>{preview.balance_after ?? "n/a"}</dd>
              {preview.would_send && typeof preview.would_send === "object" && "bid_amount" in preview.would_send && (
                <>
                  <dt>Bid</dt>
                  <dd>{String((preview.would_send as Record<string, unknown>).bid_amount)}</dd>
                </>
              )}
            </dl>
            {preview.would_send && (
              <details style={{ marginTop: 6 }}>
                <summary>Payload that would be sent</summary>
                <pre>{JSON.stringify(preview.would_send, null, 2)}</pre>
              </details>
            )}
          </div>
        )}
        {dirty ? (
          <button className="btn primary" onClick={onSaveEdit} disabled={busy || disabled} data-testid="save-edit">
            Save edits and approve
          </button>
        ) : (
          <button className="btn primary" onClick={() => setConfirmOpen(true)} disabled={busy || disabled} data-testid="approve">
            Approve and submit
          </button>
        )}
        <button className="btn danger" onClick={() => setRejectOpen(true)} disabled={busy || disabled} data-testid="reject">
          Reject
        </button>
      </div>

      <Dialog
        open={confirmOpen}
        title="Submit this proposal?"
        onClose={() => setConfirmOpen(false)}
        actions={
          <>
            <button className="btn" onClick={() => setConfirmOpen(false)}>
              Cancel
            </button>
            <button
              className="btn primary"
              data-testid="confirm-approve"
              onClick={() => {
                setConfirmOpen(false);
                onApprove();
              }}
            >
              Approve and submit
            </button>
          </>
        }
      >
        <p>
          GigBid will resume the run and submit the proposal to the marketplace
          {preview?.connects_cost != null ? `, spending ${preview.connects_cost} Connects` : ""}.
        </p>
      </Dialog>

      <Dialog
        open={rejectOpen}
        title="Reject this draft"
        onClose={() => setRejectOpen(false)}
        actions={
          <>
            <button className="btn" onClick={() => setRejectOpen(false)}>
              Cancel
            </button>
            <button
              className="btn danger"
              disabled={!finalReason}
              data-testid="confirm-reject"
              onClick={() => {
                setRejectOpen(false);
                onReject(finalReason);
              }}
            >
              Reject draft
            </button>
          </>
        }
      >
        <fieldset style={{ border: 0, padding: 0, margin: 0 }}>
          <legend className="label" style={{ marginBottom: 6 }}>
            Why are you rejecting it?
          </legend>
          <div className="stack" style={{ gap: 6 }}>
            {REJECT_REASONS.map((r) => (
              <label key={r} className="check">
                <input type="radio" name="reject-reason" value={r} checked={reason === r} onChange={() => setReason(r)} />
                {r}
              </label>
            ))}
          </div>
        </fieldset>
        <label className="field" style={{ marginTop: 10 }}>
          <span>Details {reason === "Other" ? "(required)" : "(optional)"}</span>
          <textarea value={note} onChange={(e) => setNote(e.target.value)} rows={3} data-testid="reject-note" />
        </label>
      </Dialog>
    </section>
  );
}
