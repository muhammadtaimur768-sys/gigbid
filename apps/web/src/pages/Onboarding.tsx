import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { api, type Autonomy } from "../lib/api";
import { useAuth } from "../lib/auth";

const PERSONAS = [
  { id: "aiml", title: "AI/ML engineer", desc: "LLM apps, RAG, model training and evaluation." },
  { id: "fullstack", title: "Full-stack web developer", desc: "React, Node, Python back ends, deployments." },
  { id: "data", title: "Data analyst", desc: "SQL, dashboards, reporting and analysis." },
];

const STEPS = ["Profile", "Marketplace", "Portfolio", "Rates and filters", "Budget"];

function splitList(s: string): string[] {
  return s
    .split(",")
    .map((x) => x.trim())
    .filter(Boolean);
}

export default function Onboarding() {
  const { user, setUser } = useAuth();
  const nav = useNavigate();
  const [step, setStep] = useState(0);
  const [persona, setPersona] = useState(user?.persona ?? "aiml");
  const [ownProfile, setOwnProfile] = useState(false);
  const [mode, setMode] = useState<"gigsim" | "upwork">("gigsim");
  const [mpToken, setMpToken] = useState("");
  const [mpStatus, setMpStatus] = useState<{ ok: boolean; text: string } | null>(null);
  const [files, setFiles] = useState<File[]>([]);
  const [uploads, setUploads] = useState<{ name: string; ok: boolean; detail: string }[]>([]);
  const [floor, setFloor] = useState("45");
  const [target, setTarget] = useState("70");
  const [categories, setCategories] = useState("");
  const [skills, setSkills] = useState("");
  const [minBudget, setMinBudget] = useState("");
  const [weekly, setWeekly] = useState("80");
  const [perProposal, setPerProposal] = useState("16");
  const [autonomy, setAutonomy] = useState<Autonomy>("manual");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function connect() {
    setBusy(true);
    setError(null);
    try {
      if (mode === "upwork") {
        const r = await api.upworkStart();
        if (r.configured && r.authorize_url) {
          window.location.assign(r.authorize_url);
          return;
        }
        setMpStatus({ ok: false, text: r.detail || "Upwork OAuth is not configured on this server. Use GigSim for now." });
      } else {
        const r = await api.connectMarketplace("gigsim", mpToken || undefined);
        setMpStatus({ ok: r.connected, text: r.detail || (r.connected ? "Connected to GigSim." : "Saved, but GigSim is unreachable.") });
      }
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setBusy(false);
    }
  }

  async function upload() {
    setBusy(true);
    setError(null);
    const out: typeof uploads = [];
    for (const f of files) {
      try {
        const r = await api.uploadPortfolio(f);
        out.push({ name: r.filename, ok: true, detail: r.indexed ? "Indexed" : r.detail || "Stored" });
      } catch (e) {
        out.push({ name: f.name, ok: false, detail: e instanceof Error ? e.message : "Upload failed" });
      }
    }
    setUploads((u) => [...u, ...out]);
    setFiles([]);
    setBusy(false);
  }

  async function finish() {
    setBusy(true);
    setError(null);
    try {
      const u = await api.saveOnboarding({
        persona,
        rates: { hourly_floor: Number(floor) || null, hourly_target: Number(target) || null },
        filters: { categories: splitList(categories), skills: splitList(skills), min_budget: minBudget ? Number(minBudget) : null },
        budgets: { weekly_connects: Number(weekly) || 0, max_connects_per_proposal: Number(perProposal) || 0 },
        autonomy,
      });
      setUser(u);
      nav("/inbox", { replace: true });
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setBusy(false);
    }
  }

  const rateError = Number(target) < Number(floor) ? "Target rate should be at least the floor." : null;

  return (
    <div className="auth-wrap">
      <main className="card" style={{ width: "100%", maxWidth: 720 }}>
        <h1>Set up GigBid</h1>
        <p className="muted">
          Step {step + 1} of {STEPS.length}: {STEPS[step]}
        </p>
        <div className="steps" aria-hidden="true">
          {STEPS.map((s, i) => (
            <span key={s} className={i <= step ? "done" : ""} />
          ))}
        </div>

        {step === 0 && (
          <section aria-labelledby="persona-h">
            <h2 id="persona-h">Who are you bidding as?</h2>
            <div className="choice-grid" role="radiogroup" aria-label="Persona">
              {PERSONAS.map((p) => (
                <button
                  key={p.id}
                  type="button"
                  role="radio"
                  aria-checked={persona === p.id}
                  className="choice"
                  onClick={() => setPersona(p.id)}
                  data-testid={`persona-${p.id}`}
                >
                  <strong>{p.title}</strong>
                  <span className="small muted">{p.desc}</span>
                </button>
              ))}
            </div>
            <label className="check" style={{ marginTop: 12 }}>
              <input type="checkbox" checked={ownProfile} onChange={(e) => setOwnProfile(e.target.checked)} />
              Use my own profile (start from the closest persona and upload your own portfolio in step 3)
            </label>
          </section>
        )}

        {step === 1 && (
          <section aria-labelledby="mp-h" className="stack">
            <h2 id="mp-h">Connect a marketplace</h2>
            <div className="choice-grid" role="radiogroup" aria-label="Marketplace">
              <button type="button" role="radio" aria-checked={mode === "gigsim"} className="choice" onClick={() => setMode("gigsim")}>
                <strong>GigSim</strong>
                <span className="small muted">Simulated marketplace for safe practice and evaluation.</span>
              </button>
              <button type="button" role="radio" aria-checked={mode === "upwork"} className="choice" onClick={() => setMode("upwork")}>
                <strong>Upwork (OAuth)</strong>
                <span className="small muted">Live jobs. GigBid only creates drafts; you send.</span>
              </button>
            </div>
            {mode === "gigsim" && (
              <label className="field">
                <span>GigSim token (optional)</span>
                <input type="text" value={mpToken} onChange={(e) => setMpToken(e.target.value)} placeholder="Defaults to the persona demo token" />
              </label>
            )}
            <div className="row">
              <button className="btn" onClick={connect} disabled={busy} data-testid="connect-marketplace">
                {mode === "upwork" ? "Continue to Upwork" : "Connect GigSim"}
              </button>
              {mpStatus && (
                <span className={`badge ${mpStatus.ok ? "ok" : "warn"}`} role="status" data-testid="marketplace-status">
                  {mpStatus.text}
                </span>
              )}
            </div>
          </section>
        )}

        {step === 2 && (
          <section aria-labelledby="pf-h" className="stack">
            <h2 id="pf-h">Upload portfolio</h2>
            <p className="muted small">
              Case studies, CV, README files or past proposals (.md, .txt, .pdf, .json, up to 10 MB). Every claim in a
              proposal must point back to one of these.
              {!ownProfile && " The persona already ships with a sample portfolio, so this step is optional."}
            </p>
            <label className="field">
              <span>Files</span>
              <input
                type="file"
                multiple
                accept=".md,.txt,.pdf,.json"
                onChange={(e) => setFiles(Array.from(e.target.files ?? []))}
                data-testid="portfolio-input"
              />
            </label>
            <div>
              <button className="btn" onClick={upload} disabled={busy || files.length === 0} data-testid="upload-portfolio">
                Upload {files.length ? `${files.length} file${files.length > 1 ? "s" : ""}` : ""}
              </button>
            </div>
            {uploads.length > 0 && (
              <ul className="clean stack" style={{ gap: 4 }} data-testid="upload-list">
                {uploads.map((u, i) => (
                  <li key={i} className="row">
                    <span className={`badge ${u.ok ? "ok" : "bad"}`}>{u.ok ? "OK" : "Failed"}</span>
                    <span className="mono">{u.name}</span>
                    <span className="small muted">{u.detail}</span>
                  </li>
                ))}
              </ul>
            )}
          </section>
        )}

        {step === 3 && (
          <section aria-labelledby="rates-h" className="stack">
            <h2 id="rates-h">Rates and filters</h2>
            <div className="grid grid-2">
              <label className="field">
                <span>Hourly floor (USD)</span>
                <input type="number" min={0} value={floor} onChange={(e) => setFloor(e.target.value)} data-testid="rate-floor" />
                <span className="hint">GigBid never bids below this.</span>
              </label>
              <label className="field">
                <span>Hourly target (USD)</span>
                <input type="number" min={0} value={target} onChange={(e) => setTarget(e.target.value)} data-testid="rate-target" aria-invalid={!!rateError} />
                {rateError && <span className="hint" style={{ color: "var(--bad)" }}>{rateError}</span>}
              </label>
              <label className="field">
                <span>Categories</span>
                <input type="text" value={categories} onChange={(e) => setCategories(e.target.value)} placeholder="e.g. AI/ML, Web Development" />
                <span className="hint">Comma separated. Leave empty for all.</span>
              </label>
              <label className="field">
                <span>Skills</span>
                <input type="text" value={skills} onChange={(e) => setSkills(e.target.value)} placeholder="e.g. python, langchain" />
              </label>
              <label className="field">
                <span>Minimum fixed budget (USD)</span>
                <input type="number" min={0} value={minBudget} onChange={(e) => setMinBudget(e.target.value)} />
              </label>
            </div>
          </section>
        )}

        {step === 4 && (
          <section aria-labelledby="budget-h" className="stack">
            <h2 id="budget-h">Connects budget and autonomy</h2>
            <div className="grid grid-2">
              <label className="field">
                <span>Weekly Connects budget</span>
                <input type="number" min={0} max={1000} value={weekly} onChange={(e) => setWeekly(e.target.value)} data-testid="weekly-connects" />
              </label>
              <label className="field">
                <span>Max Connects per proposal</span>
                <input type="number" min={0} max={100} value={perProposal} onChange={(e) => setPerProposal(e.target.value)} />
              </label>
            </div>
            <fieldset style={{ border: 0, padding: 0, margin: 0 }}>
              <legend className="label">Autonomy</legend>
              <div className="stack" style={{ gap: 6, marginTop: 6 }}>
                <label className="check">
                  <input type="radio" name="autonomy" checked={autonomy === "manual"} onChange={() => setAutonomy("manual")} />
                  Manual: I approve every proposal and message
                </label>
                <label className="check">
                  <input type="radio" name="autonomy" checked={autonomy === "assisted"} onChange={() => setAutonomy("assisted")} />
                  Assisted: drafts are prepared automatically, I approve sends
                </label>
                <label className="check">
                  <input type="radio" name="autonomy" checked={autonomy === "autopilot"} onChange={() => setAutonomy("autopilot")} />
                  Autopilot: low-risk, high-fit bids within budget may send without review
                </label>
              </div>
            </fieldset>
          </section>
        )}

        {error && (
          <div className="alert bad" role="alert" style={{ marginTop: 12 }}>
            {error}
          </div>
        )}

        <div className="row-between" style={{ marginTop: 20 }}>
          <button className="btn" onClick={() => setStep((s) => Math.max(0, s - 1))} disabled={step === 0 || busy}>
            Back
          </button>
          {step < STEPS.length - 1 ? (
            <button
              className="btn primary"
              onClick={() => setStep((s) => s + 1)}
              disabled={busy || (step === 3 && !!rateError)}
              data-testid="onboarding-next"
            >
              Continue
            </button>
          ) : (
            <button className="btn primary" onClick={finish} disabled={busy} data-testid="onboarding-finish">
              {busy ? "Saving…" : "Finish setup"}
            </button>
          )}
        </div>
      </main>
    </div>
  );
}
