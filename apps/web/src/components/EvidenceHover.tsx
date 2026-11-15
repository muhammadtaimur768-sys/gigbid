import { useId, useState, type ReactNode } from "react";
import type { Claim, EvidenceRef } from "../lib/api";

const STATUS_LABEL: Record<Claim["status"], string> = {
  supported: "Supported",
  partly_supported: "Partly supported",
  unsupported: "Unsupported",
};

/**
 * Wraps a claim in the draft. Hover or keyboard focus shows the portfolio
 * evidence that backs it (or flags that nothing does).
 */
export function EvidenceHover({
  claim,
  evidence,
  children,
}: {
  claim: Claim;
  evidence: EvidenceRef[];
  children: ReactNode;
}) {
  const [open, setOpen] = useState(false);
  const id = useId();
  return (
    <span
      className="evh"
      onMouseEnter={() => setOpen(true)}
      onMouseLeave={() => setOpen(false)}
      onKeyDown={(e) => e.key === "Escape" && setOpen(false)}
    >
      <button
        type="button"
        className={`claim ${claim.status}`}
        aria-describedby={open ? id : undefined}
        aria-expanded={open}
        onFocus={() => setOpen(true)}
        onBlur={() => setOpen(false)}
        onClick={() => setOpen((o) => !o)}
        data-testid="claim"
        data-claim-status={claim.status}
      >
        {children}
      </button>
      {open && (
        <span role="tooltip" id={id} className="evh-pop" data-testid="evidence-popover">
          <span className="row-between">
            <strong>{STATUS_LABEL[claim.status]}</strong>
            {claim.action && claim.action !== "kept" && <span className="badge warn">{claim.action}</span>}
          </span>
          {evidence.length === 0 ? (
            <span style={{ display: "block" }} className="muted">
              No portfolio evidence backs this claim. Remove or rewrite it before approving.
            </span>
          ) : (
            evidence.map((ev) => (
              <span key={ev.chunk_id} className="ev" style={{ display: "block" }}>
                <span className="row" style={{ gap: 6 }}>
                  <span className="badge info">{ev.type}</span>
                  <span className="mono">{ev.item_id}</span>
                  {ev.outcome && <span className="badge">{ev.outcome}</span>}
                </span>
                <span style={{ display: "block", marginTop: 4 }}>&ldquo;{ev.snippet}&rdquo;</span>
              </span>
            ))
          )}
        </span>
      )}
    </span>
  );
}

/** Splits a paragraph into plain text and EvidenceHover spans for claims found in it. */
export function annotate(
  paragraph: string,
  claims: Claim[],
  lookup: (chunkId: string) => EvidenceRef | undefined,
): ReactNode[] {
  type Hit = { start: number; end: number; claim: Claim };
  const hits: Hit[] = [];
  for (const c of claims) {
    if (!c.text) continue;
    const idx = paragraph.indexOf(c.text);
    if (idx >= 0 && !hits.some((h) => idx < h.end && idx + c.text.length > h.start)) {
      hits.push({ start: idx, end: idx + c.text.length, claim: c });
    }
  }
  hits.sort((a, b) => a.start - b.start);
  const out: ReactNode[] = [];
  let pos = 0;
  hits.forEach((h, i) => {
    if (h.start > pos) out.push(paragraph.slice(pos, h.start));
    const ev = h.claim.evidence_ids.map((id) => lookup(id)).filter((e): e is EvidenceRef => !!e);
    const fallback: EvidenceRef[] = ev.length
      ? ev
      : h.claim.evidence_ids.map((cid) => ({ chunk_id: cid, item_id: cid.split("#")[0], type: "evidence", snippet: cid }));
    out.push(
      <EvidenceHover key={`c${i}`} claim={h.claim} evidence={fallback}>
        {paragraph.slice(h.start, h.end)}
      </EvidenceHover>,
    );
    pos = h.end;
  });
  if (pos < paragraph.length) out.push(paragraph.slice(pos));
  return out;
}
