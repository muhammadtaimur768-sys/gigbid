import { useEffect, useMemo, useRef, useState } from "react";
import { api, type RunEvent } from "../lib/api";

type Conn = "connecting" | "live" | "closed" | "error";

const NODE_EVENTS = ["node_start", "node_end", "progress", "interrupt", "error"];

/** Converts one SSE or stored event (node_start, node_end, interrupt, error...) into a timeline event. */
export function toEvent(event: string, data: unknown, ts?: string): RunEvent | null {
  const d = (data && typeof data === "object" ? data : {}) as Record<string, unknown>;
  if (!NODE_EVENTS.includes(event)) return null;
  const node =
    typeof d.node === "string" && d.node
      ? d.node
      : event === "interrupt"
        ? "approval"
        : event === "error"
          ? "error"
          : null;
  if (!node) return null;
  if (event === "progress" && !d.error && d.latency_ms == null && d.tokens_in == null) return null;
  return {
    node,
    event: event === "progress" && d.error ? "error" : event,
    ts: ts ?? new Date().toISOString(),
    latency_ms: (d.latency_ms as number) ?? null,
    tokens_in: (d.tokens_in as number) ?? null,
    tokens_out: (d.tokens_out as number) ?? null,
    cost_usd: (d.cost_usd as number) ?? null,
    payload: d.summary ?? d.payload ?? d.message ?? d.error,
  };
}

interface NodeRow {
  node: string;
  status: "running" | "done" | "error" | "interrupt";
  latency_ms?: number | null;
  tokens?: number | null;
  cost_usd?: number | null;
  count: number;
}

function rows(events: RunEvent[]): NodeRow[] {
  const order: string[] = [];
  const map = new Map<string, NodeRow>();
  for (const e of events) {
    let r = map.get(e.node);
    if (!r) {
      r = { node: e.node, status: "running", count: 0 };
      map.set(e.node, r);
      order.push(e.node);
    }
    if (e.event === "error") r.status = "error";
    else if (e.event === "interrupt") r.status = "interrupt";
    else if (e.event === "node_end") {
      r.status = "done";
      r.count += 1;
    } else if (e.event === "node_start") r.status = "running";
    if (e.latency_ms != null) r.latency_ms = e.latency_ms;
    if (e.tokens_in != null || e.tokens_out != null) r.tokens = (e.tokens_in ?? 0) + (e.tokens_out ?? 0);
    if (e.cost_usd != null) r.cost_usd = e.cost_usd;
  }
  return order.map((n) => map.get(n)!);
}

function parse(msg: MessageEvent): unknown {
  try {
    return JSON.parse(msg.data);
  } catch {
    return { message: msg.data };
  }
}

/** Live node-by-node progress of a LangGraph run streamed over SSE. */
export function RunTimeline({ threadId, onDone }: { threadId: string; onDone?: (status: string) => void }) {
  const [events, setEvents] = useState<RunEvent[]>([]);
  const [conn, setConn] = useState<Conn>("connecting");
  const [final, setFinal] = useState<string | null>(null);
  const [tokens, setTokens] = useState("");
  const doneRef = useRef(onDone);
  doneRef.current = onDone;

  useEffect(() => {
    setEvents([]);
    setFinal(null);
    setTokens("");
    if (typeof EventSource === "undefined") {
      setConn("error");
      return;
    }
    // The server replays persisted events first, so a refresh rebuilds the whole run.
    const es = new EventSource(api.runStreamUrl(threadId), { withCredentials: true });
    es.onopen = () => setConn("live");
    for (const t of NODE_EVENTS) {
      es.addEventListener(t, ((msg: MessageEvent) => {
        const ev = toEvent(t, parse(msg));
        if (ev) setEvents((cur) => [...cur, ev]);
      }) as EventListener);
    }
    es.addEventListener("token", ((msg: MessageEvent) => {
      const d = parse(msg) as { text?: string };
      if (d.text) setTokens((cur) => (cur + d.text).slice(-600));
    }) as EventListener);
    es.addEventListener("done", ((msg: MessageEvent) => {
      const status = (parse(msg) as { status?: string }).status ?? "done";
      setFinal(status);
      setConn("closed");
      es.close();
      doneRef.current?.(status);
    }) as EventListener);
    es.onerror = () => {
      if (es.readyState === EventSource.CLOSED) setConn((c) => (c === "closed" ? c : "error"));
      else setConn("connecting");
    };
    return () => es.close();
  }, [threadId]);

  const list = useMemo(() => rows(events), [events]);

  return (
    <div>
      <div className="row-between" style={{ marginBottom: 8 }}>
        <span className="row">
          <span className={`badge ${conn === "live" ? "ok" : conn === "error" ? "bad" : conn === "closed" ? "" : "warn"}`}>
            {conn === "live" ? "Live" : conn === "connecting" ? "Connecting" : conn === "closed" ? "Segment finished" : "Stream lost"}
          </span>
          {final && <span className="badge info">{final === "interrupted" ? "Waiting for approval" : `Run ${final}`}</span>}
        </span>
        <span className="small muted" aria-live="polite">
          {list.length} node{list.length === 1 ? "" : "s"}
        </span>
      </div>
      {list.length === 0 ? (
        <p className="muted small" data-testid="timeline-empty">
          {conn === "error" ? "Could not open the live stream. Try reloading the page." : "Waiting for the first node…"}
        </p>
      ) : (
        <ol className="timeline" data-testid="run-timeline">
          {list.map((r) => (
            <li key={r.node}>
              <span className={`dot ${r.status}`} aria-hidden="true" />
              <span>
                <strong className="mono">{r.node}</strong>
                <span className="small muted"> · {r.status === "interrupt" ? "waiting for approval" : r.status}</span>
                {r.count > 1 && <span className="small muted"> · ran {r.count}×</span>}
              </span>
              <span className="small muted mono">
                {r.latency_ms != null ? `${Math.round(r.latency_ms)} ms` : ""}
                {r.tokens ? ` · ${r.tokens} tok` : ""}
                {r.cost_usd != null ? ` · $${r.cost_usd.toFixed(4)}` : ""}
              </span>
            </li>
          ))}
        </ol>
      )}
      {tokens && conn === "live" && (
        <div style={{ marginTop: 10 }}>
          <div className="label">Streaming output</div>
          <pre className="small">{tokens}</pre>
        </div>
      )}
    </div>
  );
}
