import { useEffect, useState } from "react";
import { api, type Health } from "../lib/api";

type Status = { kind: "ok" } | { kind: "degraded"; detail: string } | { kind: "down"; detail: string };

export function healthStatus(h: Health): Status {
  const mpDetail = h.marketplace_detail;
  const bad = (s?: string) => !!s && !["ok", "up", "healthy", "connected"].includes(s.toLowerCase());
  if (bad(h.marketplace) || bad(h.status)) {
    return {
      kind: "degraded",
      detail: mpDetail || "The marketplace is unavailable. Analysis keeps working on cached jobs; submissions are paused.",
    };
  }
  return { kind: "ok" };
}

/** Polls /api/health and shows a banner when the marketplace or API is unavailable. */
export function DegradedBanner({ intervalMs = 30000 }: { intervalMs?: number }) {
  const [status, setStatus] = useState<Status>({ kind: "ok" });

  useEffect(() => {
    let alive = true;
    const check = async () => {
      try {
        const h = await api.health();
        if (alive) setStatus(healthStatus(h));
      } catch (e) {
        if (alive)
          setStatus({
            kind: "down",
            detail: e instanceof Error ? e.message : "The GigBid API is unreachable.",
          });
      }
    };
    void check();
    const t = window.setInterval(check, intervalMs);
    return () => {
      alive = false;
      window.clearInterval(t);
    };
  }, [intervalMs]);

  if (status.kind === "ok") return null;
  return (
    <div className={`banner ${status.kind === "down" ? "bad" : "warn"}`} role="status" data-testid="degraded-banner">
      <strong>{status.kind === "down" ? "GigBid API unavailable." : "Marketplace unavailable: degraded mode."}</strong>
      <span>{status.detail}</span>
    </div>
  );
}
