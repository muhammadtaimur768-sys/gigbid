import type { Action, RiskFlag } from "../lib/api";
import { Icon } from "./Icon";

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

/** Scam-like signals are red, injection attempts amber, everything else follows severity. */
function riskTone(flag: RiskFlag): string {
  if (flag.code === "prompt_injection") return "risk-injection";
  if (flag.severity === "high") return "risk-scam";
  if (flag.severity === "medium") return "warn";
  return "";
}

export function RiskBadge({ flag }: { flag: RiskFlag }) {
  const tone = riskTone(flag);
  return (
    <span className={`badge ${tone}`} title={flag.evidence} data-testid="risk-badge">
      <Icon name={flag.code === "prompt_injection" ? "shield" : "alert"} />
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
  if (!list.length)
    return (
      <span className="badge risk-ok">
        <Icon name="check" />
        No risk flags
      </span>
    );
  return (
    <span className="row" style={{ gap: 4 }}>
      {list.map((f, i) => (
        <RiskBadge key={`${f.code}-${i}`} flag={f} />
      ))}
    </span>
  );
}

export function ActionBadge({ action }: { action?: Action | null }) {
  if (!action) return <span className="action-chip">Not analysed</span>;
  const label = action === "bid" ? "Recommend bid" : action === "watch" ? "Watch" : "Recommend skip";
  return <span className={`action-chip ${action}`}>{label}</span>;
}

export function FitScore({ score }: { score?: number | null }) {
  if (score === null || score === undefined) {
    return (
      <div className="fit lo" role="img" aria-label="Fit not scored">
        <div className="fit-top">
          <span className="fit-num">—</span>
        </div>
        <div className="fit-track" />
        <span className="fit-label">Not scored</span>
      </div>
    );
  }
  const pct = Math.max(0, Math.min(100, Math.round(score * 100)));
  const tone = pct >= 70 ? "hi" : pct >= 45 ? "mid" : "lo";
  const band = tone === "hi" ? "Strong fit" : tone === "mid" ? "Partial fit" : "Weak fit";
  return (
    <div className={`fit ${tone}`} role="img" aria-label={`Fit ${pct} percent`}>
      <div className="fit-top" aria-hidden="true">
        <span className="fit-num">{pct}</span>
        <span className="fit-unit">/100</span>
      </div>
      <div className="fit-track" aria-hidden="true">
        <div className="fit-fill" style={{ width: `${pct}%` }} />
      </div>
      <span className="fit-label" aria-hidden="true">
        {band}
      </span>
    </div>
  );
}
