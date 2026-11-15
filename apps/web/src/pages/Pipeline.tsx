import { useEffect } from "react";
import { KanbanBoard } from "../components/KanbanBoard";
import { PageHead } from "../components/Layout";
import { AsyncView, Empty } from "../components/States";
import { api } from "../lib/api";
import { useAsync } from "../lib/useAsync";

export default function Pipeline() {
  const state = useAsync(() => api.pipeline(), []);
  const { reload } = state;

  // Marketplace events (viewed, replied, hired...) are synced server-side; poll to pick them up.
  useEffect(() => {
    const t = window.setInterval(reload, 20000);
    return () => window.clearInterval(t);
  }, [reload]);

  return (
    <>
      <PageHead
        title="Pipeline"
        sub="Every proposal from draft to outcome. Cards move as the marketplace reports views, replies and hires."
        actions={
          <button className="btn" onClick={reload} disabled={state.loading}>
            Refresh
          </button>
        }
      />
      {state.data?.marketplace === "unavailable" && (
        <div className="alert warn" style={{ marginBottom: 12 }}>
          Marketplace unavailable: statuses may be stale.
        </div>
      )}
      <AsyncView
        state={state}
        rows={5}
        isEmpty={(d) => Object.values(d.columns ?? {}).every((c) => c.length === 0)}
        empty={<Empty title="No proposals yet">Analyse a job from the inbox and approve a draft to see it here.</Empty>}
      >
        {(d) => <KanbanBoard columns={d.columns ?? {}} />}
      </AsyncView>
    </>
  );
}
