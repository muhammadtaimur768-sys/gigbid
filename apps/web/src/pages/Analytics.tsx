import { GroupedBars, HBars } from "../components/Charts";
import { PageHead } from "../components/Layout";
import { AsyncView, Empty } from "../components/States";
import { api, type Analytics as A } from "../lib/api";
import { useAsync } from "../lib/useAsync";

const DASH = "—";
const pct = (v?: number | null) => (v == null ? DASH : `${Math.round(v * 1000) / 10}%`);
const num = (v?: number | null, unit = "") => (v == null ? DASH : `${Math.round(v * 100) / 100}${unit}`);

function Stat({ label, value, meta }: { label: string; value: string; meta?: string }) {
  return (
    <div className="kpi">
      <span className="l">{label}</span>
      <span className="v">{value}</span>
      {meta && <span className="m">{meta}</span>}
    </div>
  );
}

export default function Analytics() {
  const state = useAsync(() => api.analytics(), []);
  return (
    <>
      <PageHead title="Analytics" sub="Outcomes from your submitted proposals. Figures come straight from recorded events." />
      <AsyncView
        state={state}
        rows={6}
        isEmpty={(d) => d.by_category.length === 0 && Object.keys(d.outcomes ?? {}).length === 0}
        empty={<Empty title="No outcomes yet">Analytics appear once proposals are submitted and clients respond.</Empty>}
      >
        {(d: A) => {
          const sent = d.by_category.reduce((s, c) => s + c.proposals, 0);
          const replied = d.by_category.reduce((s, c) => s + c.replied, 0);
          const hired = d.by_category.reduce((s, c) => s + c.hired, 0);
          return (
            <div className="stack" style={{ gap: 16 }}>
              <section className="kpis" style={{ marginBottom: 0 }} aria-label="Outcome summary">
                <Stat label="Proposals sent" value={String(sent)} />
                <Stat label="Reply rate" value={sent ? pct(replied / sent) : DASH} meta={sent ? `${replied} of ${sent} replied` : "Not measured"} />
                <Stat label="Hire rate" value={sent ? pct(hired / sent) : DASH} meta={sent ? `${hired} of ${sent} hired` : "Not measured"} />
                <Stat label="Connects spent" value={String(d.connects_spent_total)} />
                <Stat label="Connects per reply" value={num(d.connects_per_reply)} />
                <Stat label="Cost per proposal" value={d.cost_per_proposal_usd == null ? DASH : `$${d.cost_per_proposal_usd.toFixed(4)}`} />
                <Stat label="Latency p50" value={num(d.latency_p50_ms, " ms")} />
                <Stat label="Latency p95" value={num(d.latency_p95_ms, " ms")} />
              </section>
              {d.note && <p className="small muted">{d.note} · runs measured: {d.runs_measured}</p>}
              <div className="grid grid-2">
                <section className="card chart-card span-2" aria-labelledby="rate-h">
                  <h2 id="rate-h">Reply and hire rate by category</h2>
                  <p className="chart-sub">Share of submitted proposals that got a reply or a hire</p>
                  {d.by_category.length ? (
                    <GroupedBars
                      title="Reply and hire rate by category"
                      data={d.by_category.map((c) => ({ category: c.category, reply: c.reply_rate ?? 0, hire: c.hire_rate ?? 0 }))}
                      labelKey="category"
                      series={[
                        { key: "reply", label: "Reply rate", className: "bar-b" },
                        { key: "hire", label: "Hire rate", className: "bar-a" },
                      ]}
                      format={(n) => `${Math.round(n * 100)}%`}
                      height={240}
                    />
                  ) : (
                    <p className="muted">No submitted proposals yet.</p>
                  )}
                </section>
                <section className="card chart-card" aria-labelledby="conn-h">
                  <h2 id="conn-h">Connects spent versus outcomes</h2>
                  <p className="chart-sub">Connects against replies and hires, per category</p>
                  {d.by_category.length ? (
                    <GroupedBars
                      title="Connects spent versus replies and hires by category"
                      data={d.by_category.map((c) => ({ category: c.category, connects: c.connects_spent, replied: c.replied, hired: c.hired }))}
                      labelKey="category"
                      series={[
                        { key: "connects", label: "Connects", className: "bar-c" },
                        { key: "replied", label: "Replies", className: "bar-b" },
                        { key: "hired", label: "Hires", className: "bar-a" },
                      ]}
                    />
                  ) : (
                    <p className="muted">No Connects spent yet.</p>
                  )}
                </section>
                <section className="card chart-card" aria-labelledby="rej-h">
                  <h2 id="rej-h">Top rejection reasons</h2>
                  {d.top_rejection_reasons.length ? (
                    <HBars
                      title="Top rejection reasons"
                      data={d.top_rejection_reasons.map((r) => ({ label: String(r.reason ?? ""), value: Number(r.count ?? 0) }))}
                    />
                  ) : (
                    <p className="muted">No drafts rejected yet.</p>
                  )}
                </section>
                <section className="card chart-card span-2" aria-labelledby="out-h">
                  <h2 id="out-h">Outcomes and approvals</h2>
                  <div className="grid grid-2">
                    <HBars title="Proposal outcomes" data={Object.entries(d.outcomes).map(([label, value]) => ({ label, value }))} />
                    <HBars title="Approval decisions" data={Object.entries(d.approvals).map(([label, value]) => ({ label, value }))} />
                  </div>
                </section>
              </div>
              <section className="card table-wrap" aria-labelledby="tbl-h">
                <h2 id="tbl-h">By category</h2>
                <table>
                  <thead>
                    <tr>
                      <th scope="col">Category</th>
                      <th scope="col">Proposals</th>
                      <th scope="col">Replied</th>
                      <th scope="col">Hired</th>
                      <th scope="col">Reply rate</th>
                      <th scope="col">Connects</th>
                    </tr>
                  </thead>
                  <tbody>
                    {d.by_category.map((c) => (
                      <tr key={c.category}>
                        <td>{c.category}</td>
                        <td>{c.proposals}</td>
                        <td>{c.replied}</td>
                        <td>{c.hired}</td>
                        <td>{pct(c.reply_rate)}</td>
                        <td>{c.connects_spent}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </section>
            </div>
          );
        }}
      </AsyncView>
    </>
  );
}
