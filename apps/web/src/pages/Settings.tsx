import { useEffect, useState } from "react";
import { Dialog } from "../components/Dialog";
import { PageHead } from "../components/Layout";
import { AsyncView, Empty } from "../components/States";
import { api, type Autonomy, type MemoryItem, type SettingsResponse } from "../lib/api";
import { fmtDate, useAsync } from "../lib/useAsync";

export default function Settings() {
  const state = useAsync(() => api.settings(), []);
  return (
    <>
      <PageHead title="Settings" sub="Control how much GigBid does on its own, what it spends, and what it remembers." />
      <AsyncView state={state} rows={6} isEmpty={() => false}>
        {(s) => <SettingsBody s={s} onSaved={(n) => state.setData(n)} reload={state.reload} />}
      </AsyncView>
      <MemoryViewer />
    </>
  );
}

function SettingsBody({ s, onSaved, reload }: { s: SettingsResponse; onSaved: (s: SettingsResponse) => void; reload: () => void }) {
  const [autonomy, setAutonomy] = useState<Autonomy>(s.settings.autonomy);
  const [weekly, setWeekly] = useState(String(s.settings.budgets.weekly_connects));
  const [perProp, setPerProp] = useState(String(s.settings.budgets.max_connects_per_proposal));
  const [usd, setUsd] = useState(String(s.settings.budgets.max_cost_usd_per_proposal));
  const [floor, setFloor] = useState(String(s.settings.rates.hourly_floor ?? ""));
  const [target, setTarget] = useState(String(s.settings.rates.hourly_target ?? ""));
  const [busy, setBusy] = useState(false);
  const [msg, setMsg] = useState<{ tone: "ok" | "bad"; text: string } | null>(null);
  const [ss, setSs] = useState({ name: "", query: "", category: "", interval: "30" });

  async function save() {
    setBusy(true);
    setMsg(null);
    try {
      const r = await api.saveSettings({
        autonomy,
        budgets: { weekly_connects: Number(weekly), max_connects_per_proposal: Number(perProp), max_cost_usd_per_proposal: Number(usd) },
        rates: { ...s.settings.rates, hourly_floor: floor ? Number(floor) : null, hourly_target: target ? Number(target) : null },
      });
      onSaved(r);
      setMsg({ tone: "ok", text: "Settings saved." });
    } catch (e) {
      setMsg({ tone: "bad", text: e instanceof Error ? e.message : "Save failed" });
    } finally {
      setBusy(false);
    }
  }

  async function addSearch() {
    if (!ss.name.trim()) return;
    setBusy(true);
    try {
      await api.addSavedSearch({
        name: ss.name.trim(),
        query: ss.query,
        category: ss.category || null,
        skills: [],
        interval_minutes: Number(ss.interval) || 30,
        enabled: true,
      });
      setSs({ name: "", query: "", category: "", interval: "30" });
      reload();
    } catch (e) {
      setMsg({ tone: "bad", text: e instanceof Error ? e.message : "Could not add search" });
    } finally {
      setBusy(false);
    }
  }

  async function delSearch(id: number) {
    try {
      await api.deleteSavedSearch(id);
      reload();
    } catch (e) {
      setMsg({ tone: "bad", text: e instanceof Error ? e.message : "Delete failed" });
    }
  }

  async function disconnect(provider: string) {
    try {
      await api.disconnectAccount(provider);
      reload();
    } catch (e) {
      setMsg({ tone: "bad", text: e instanceof Error ? e.message : "Disconnect failed" });
    }
  }

  return (
    <div className="stack" style={{ gap: 14 }}>
      {msg && (
        <div className={`alert ${msg.tone}`} role="status">
          {msg.text}
        </div>
      )}
      <div className="grid grid-2">
        <section className="card" aria-labelledby="auto-h">
          <h2 id="auto-h">Autonomy</h2>
          <fieldset style={{ border: 0, padding: 0, margin: 0 }}>
            <legend className="sr-only">Autonomy level</legend>
            <div className="stack" style={{ gap: 8 }}>
              {(
                [
                  ["manual", "Manual", "Approve every proposal and message."],
                  ["assisted", "Assisted", "Drafts are prepared automatically; you approve sends."],
                  ["autopilot", "Autopilot", "Low-risk, high-fit bids within budget may send without review."],
                ] as const
              ).map(([v, l, d]) => (
                <label key={v} className="check" style={{ alignItems: "flex-start" }}>
                  <input type="radio" name="autonomy" checked={autonomy === v} onChange={() => setAutonomy(v)} />
                  <span>
                    <strong>{l}</strong>
                    <br />
                    <span className="small muted">{d}</span>
                  </span>
                </label>
              ))}
            </div>
          </fieldset>
        </section>
        <section className="card" aria-labelledby="bud-h">
          <h2 id="bud-h">Budgets and rates</h2>
          <div className="grid grid-2">
            <label className="field">
              <span>Weekly Connects</span>
              <input type="number" min={0} value={weekly} onChange={(e) => setWeekly(e.target.value)} />
            </label>
            <label className="field">
              <span>Max Connects per proposal</span>
              <input type="number" min={0} value={perProp} onChange={(e) => setPerProp(e.target.value)} />
            </label>
            <label className="field">
              <span>Max model cost per proposal (USD)</span>
              <input type="number" min={0} step="0.01" value={usd} onChange={(e) => setUsd(e.target.value)} />
            </label>
            <span />
            <label className="field">
              <span>Hourly floor</span>
              <input type="number" min={0} value={floor} onChange={(e) => setFloor(e.target.value)} />
            </label>
            <label className="field">
              <span>Hourly target</span>
              <input type="number" min={0} value={target} onChange={(e) => setTarget(e.target.value)} />
            </label>
          </div>
        </section>
      </div>
      <div>
        <button className="btn primary" onClick={save} disabled={busy}>
          Save settings
        </button>
      </div>

      <section className="card" aria-labelledby="ss-h">
        <h2 id="ss-h">Saved searches</h2>
        {s.saved_searches.length === 0 ? (
          <p className="muted">No saved searches. Add one so the scout runs on a schedule.</p>
        ) : (
          <div className="table-wrap">
            <table>
              <thead>
                <tr>
                  <th scope="col">Name</th>
                  <th scope="col">Query</th>
                  <th scope="col">Every</th>
                  <th scope="col">Last run</th>
                  <th scope="col">
                    <span className="sr-only">Actions</span>
                  </th>
                </tr>
              </thead>
              <tbody>
                {s.saved_searches.map((x) => (
                  <tr key={x.id}>
                    <td>{x.name}</td>
                    <td>
                      {x.query} {x.category && <span className="chip">{x.category}</span>}
                    </td>
                    <td>{x.interval_minutes} min</td>
                    <td className="small muted">{x.last_run_at ? fmtDate(x.last_run_at) : "never"}</td>
                    <td>
                      <button className="btn danger sm" onClick={() => delSearch(x.id)} aria-label={`Delete saved search ${x.name}`}>
                        Delete
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
        <form
          className="grid grid-4"
          style={{ marginTop: 12, alignItems: "end" }}
          onSubmit={(e) => {
            e.preventDefault();
            void addSearch();
          }}
        >
          <label className="field">
            <span>Name</span>
            <input type="text" required value={ss.name} onChange={(e) => setSs({ ...ss, name: e.target.value })} />
          </label>
          <label className="field">
            <span>Query</span>
            <input type="text" value={ss.query} onChange={(e) => setSs({ ...ss, query: e.target.value })} />
          </label>
          <label className="field">
            <span>Interval (minutes, 5 to 1440)</span>
            <input type="number" min={5} max={1440} value={ss.interval} onChange={(e) => setSs({ ...ss, interval: e.target.value })} />
          </label>
          <button className="btn" type="submit" disabled={busy}>
            Add search
          </button>
        </form>
      </section>

      <section className="card" aria-labelledby="acc-h">
        <h2 id="acc-h">Connected accounts</h2>
        {s.accounts.length === 0 ? (
          <p className="muted">No marketplace connected. Connect GigSim or Upwork from onboarding.</p>
        ) : (
          <ul className="clean stack">
            {s.accounts.map((a) => (
              <li key={a.provider} className="row-between">
                <span className="row">
                  <strong>{a.provider}</strong>
                  <span className={`badge ${a.connected ? "ok" : ""}`}>{a.connected ? "connected" : "not connected"}</span>
                  {a.scope && <span className="small muted">{a.scope}</span>}
                </span>
                {a.connected && (
                  <button className="btn sm" onClick={() => disconnect(a.provider)}>
                    Disconnect
                  </button>
                )}
              </li>
            ))}
          </ul>
        )}
        <p className="small muted" style={{ marginTop: 8 }}>
          Marketplace mode: {s.settings.marketplace_mode}. OAuth tokens are stored encrypted and never shown.
        </p>
      </section>
    </div>
  );
}

function MemoryViewer() {
  const state = useAsync(() => api.memory(), []);
  const [confirm, setConfirm] = useState<MemoryItem | null>(null);
  const [err, setErr] = useState<string | null>(null);

  useEffect(() => setErr(null), [state.data]);

  async function remove(m: MemoryItem) {
    setConfirm(null);
    try {
      await api.deleteMemory(m);
      state.setData(state.data && { ...state.data, items: state.data.items.filter((x) => !(x.key === m.key && x.namespace.join("/") === m.namespace.join("/"))) });
    } catch (e) {
      setErr(e instanceof Error ? e.message : "Delete failed");
    }
  }

  return (
    <section className="card" aria-labelledby="mem-h" style={{ marginTop: 14 }}>
      <h2 id="mem-h">What GigBid has learned</h2>
      <p className="small muted">
        Style memory is promoted only after the same edit appears twice; outcome memory only from marketplace results. Delete anything you
        do not want used.
      </p>
      {err && (
        <div className="alert bad" role="alert">
          {err}
        </div>
      )}
      <AsyncView state={state} rows={3} isEmpty={(d) => d.items.length === 0} empty={<Empty title="Nothing learned yet" />}>
        {(d) => (
          <ul className="clean stack" data-testid="memory-list">
            {!d.available && <li className="alert warn">Memory store unavailable.</li>}
            {d.items.map((m) => (
              <li key={`${m.namespace.join("/")}:${m.key}`} className="row-between" style={{ borderBottom: "1px solid var(--border)", paddingBottom: 8 }}>
                <div style={{ minWidth: 0, flex: 1 }}>
                  <div className="row">
                    <span className="badge info">{m.kind}</span>
                    <span className="mono small">{m.namespace.join(" / ")}</span>
                    <span className="mono small muted">{m.key}</span>
                  </div>
                  <pre className="small" style={{ marginTop: 6 }}>
                    {typeof m.value === "string" ? m.value : JSON.stringify(m.value, null, 2)}
                  </pre>
                </div>
                <button className="btn danger sm" onClick={() => setConfirm(m)} aria-label={`Delete memory ${m.key}`}>
                  Delete
                </button>
              </li>
            ))}
          </ul>
        )}
      </AsyncView>
      <Dialog
        open={!!confirm}
        title="Delete this memory?"
        onClose={() => setConfirm(null)}
        actions={
          <>
            <button className="btn" onClick={() => setConfirm(null)}>
              Cancel
            </button>
            <button className="btn danger" onClick={() => confirm && void remove(confirm)}>
              Delete
            </button>
          </>
        }
      >
        <p>GigBid will stop using it in future drafts. This cannot be undone.</p>
      </Dialog>
    </section>
  );
}
