import type { Action, RiskFlag } from "../lib/api";

const LABELS: Record<string, string> = {
  scam: "Scam",
  free_work: "Free work",
  off_platform_contact: "Off-platform contact",
  off_platform_payment: "Off-platform payment",
  prompt_injection: "Prompt injection",
  low_client_quality: "Low client quality",
  unrealistic_budget: "Unrealistic budget",
  duplicate: "Duplicate",
};

export function RiskBadge({ flag }: { flag: RiskFlag }) {
  const tone = flag.severity === "high" ? "bad" : flag.severity === "medium" ? "warn" : "";
  return (
    <span className={`badge ${tone}`} title={flag.evidence} data-testid="risk-badge">
      <span aria-hidden="true">{flag.severity === "high" ? "!" : "•"}</span>
      {LABELS[flag.code] ?? flag.code.replace(/_/g, " ")}
      <span className="sr-only"> ({flag.severity} severity)</span>
    </span>
  );
}

export function RiskBadges({ flags, isScam, injection }: { flags?: RiskFlag[]; isScam?: boolean; injection?: boolean }) {
  const list = [...(flags ?? [])];
  if (isScam && !list.some((f) => f.code === "scam")) list.unshift({ code: "scam", severity: "high", evidence: "" });
  if (injection && !list.some((f) => f.code === "prompt_injection"))
    list.push({ code: "prompt_injection", severity: "high", evidence: "" });
  if (!list.length) return <span className="badge ok">No risk flags</span>;
  return (
    <span className="row" style={{ gap: 4 }}>
      {list.map((f, i) => (
        <RiskBadge key={`${f.code}-${i}`} flag={f} />
      ))}
    </span>
  );
}

export function ActionBadge({ action }: { action?: Action | null }) {
  if (!action) return <span className="badge">Not analysed</span>;
  const tone = action === "bid" ? "ok" : action === "watch" ? "warn" : "bad";
  const label = action === "bid" ? "Recommend bid" : action === "watch" ? "Watch" : "Recommend skip";
  return <span className={`badge ${tone}`}>{label}</span>;
}

export function FitScore({ score }: { score?: number | null }) {
  if (score === null || score === undefined) {
    return (
      <div className="fit lo" aria-label="Fit not scored">
        n/a
      </div>
    );
  }
  const pct = Math.round(score * 100);
  const tone = pct >= 70 ? "hi" : pct >= 45 ? "mid" : "lo";
  return (
    <div className={`fit ${tone}`} aria-label={`Fit ${pct} percent`}>
      {pct}
    </div>
  );
}
