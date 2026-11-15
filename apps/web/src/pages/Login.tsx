import { BrandMark } from "../components/Layout";
import { useState, type FormEvent } from "react";
import { Navigate, useNavigate } from "react-router-dom";
import { api } from "../lib/api";
import { useAuth } from "../lib/auth";

export default function Login() {
  const { user, setUser } = useAuth();
  const nav = useNavigate();
  const [mode, setMode] = useState<"login" | "register">("login");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [name, setName] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  if (user) return <Navigate to={user.onboarded ? "/inbox" : "/onboarding"} replace />;

  async function submit(e: FormEvent) {
    e.preventDefault();
    setBusy(true);
    setError(null);
    try {
      const u = mode === "login" ? await api.login(email, password) : await api.register(email, password, name);
      setUser(u);
      nav(u.onboarded ? "/inbox" : "/onboarding", { replace: true });
    } catch (err) {
      setError(err instanceof Error ? err.message : "Sign-in failed");
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="auth-wrap">
      <main className="card auth-card">
        <div className="brand" style={{ padding: "0 0 12px" }}>
          <BrandMark />
          GigBid
        </div>
        <h1>{mode === "login" ? "Sign in" : "Create your account"}</h1>
        <p className="muted">Find the right jobs, write evidence-backed proposals, stay in control of every send.</p>
        <div className="tabs" role="tablist" aria-label="Sign in or register">
          <button role="tab" aria-selected={mode === "login"} onClick={() => setMode("login")}>
            Sign in
          </button>
          <button role="tab" aria-selected={mode === "register"} onClick={() => setMode("register")}>
            Register
          </button>
        </div>
        <form onSubmit={submit} className="stack" noValidate={false}>
          {mode === "register" && (
            <label className="field">
              <span>Name</span>
              <input type="text" value={name} onChange={(e) => setName(e.target.value)} autoComplete="name" />
            </label>
          )}
          <label className="field">
            <span>Email</span>
            <input
              type="email"
              required
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              autoComplete="email"
            />
          </label>
          <label className="field">
            <span>Password</span>
            <input
              type="password"
              required
              minLength={mode === "register" ? 8 : undefined}
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              autoComplete={mode === "login" ? "current-password" : "new-password"}
            />
            {mode === "register" && <span className="hint">At least 8 characters.</span>}
          </label>
          {error && (
            <div className="alert bad" role="alert">
              {error}
            </div>
          )}
          <button className="btn primary" type="submit" disabled={busy}>
            {busy ? "Please wait…" : mode === "login" ? "Sign in" : "Create account"}
          </button>
        </form>
      </main>
    </div>
  );
}
