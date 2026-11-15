import { Link } from "react-router-dom";
import type { PipelineCard } from "../lib/api";
import { fmtMoney, timeAgo } from "../lib/useAsync";

export const STAGES = ["drafted", "submitted", "viewed", "replied", "interview", "hired", "lost"] as const;

const STAGE_LABEL: Record<string, string> = {
  drafted: "Drafted",
  submitted: "Submitted",
  viewed: "Viewed",
  replied: "Replied",
  interview: "Interview",
  hired: "Hired",
  lost: "Lost",
};

function stageOf(status: string): string {
  const s = status.toLowerCase();
  if (["draft", "drafted", "pending_approval", "awaiting_approval", "needs_attention"].includes(s)) return "drafted";
  return (STAGES as readonly string[]).includes(s) ? s : "drafted";
}

export function KanbanBoard({ columns }: { columns: Record<string, PipelineCard[]> }) {
  const by = new Map<string, PipelineCard[]>(STAGES.map((s) => [s, []]));
  for (const [col, cards] of Object.entries(columns)) {
    for (const c of cards) by.get(stageOf(STAGES.includes(col as never) ? col : c.status))!.push(c);
  }
  return (
    <div className="kanban" data-testid="kanban">
      {STAGES.map((s) => {
        const list = by.get(s)!;
        return (
          <section key={s} className="kcol" data-stage={s} aria-labelledby={`col-${s}`}>
            <h3 id={`col-${s}`}>
              <span>{STAGE_LABEL[s]}</span>
              <span aria-label={`${list.length} cards`}>{list.length}</span>
            </h3>
            {list.length === 0 ? (
              <p className="small muted">No proposals</p>
            ) : (
              <ul className="clean">
                {list.map((c) => (
                  <li key={c.thread_id ?? c.job_id} className="kcard">
                    <Link to={s === "drafted" && c.thread_id ? `/studio/${encodeURIComponent(c.thread_id)}` : `/jobs/${encodeURIComponent(c.job_id)}`}>
                      {c.title}
                    </Link>
                    <div className="row-between small muted" style={{ marginTop: 8 }}>
                      <span>{c.bid_amount != null ? fmtMoney(c.bid_amount) : "No bid yet"}</span>
                      <span>{c.connects_spent != null ? `${c.connects_spent} Connects` : ""}</span>
                    </div>
                    {c.updated_at && <div className="small muted">{timeAgo(c.updated_at)}</div>}
                  </li>
                ))}
              </ul>
            )}
          </section>
        );
      })}
    </div>
  );
}
