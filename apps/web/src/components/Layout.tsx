import { useEffect, useState } from "react";
import { NavLink, Outlet, useLocation } from "react-router-dom";
import { DegradedBanner } from "./DegradedBanner";
import { Icon, type IconName } from "./Icon";
import { useAuth } from "../lib/auth";

const NAV: { to: string; label: string; icon: IconName }[] = [
  { to: "/inbox", label: "Job inbox", icon: "inbox" },
  { to: "/pipeline", label: "Pipeline", icon: "pipeline" },
  { to: "/messages", label: "Messages", icon: "messages" },
  { to: "/runs", label: "Agent runs", icon: "runs" },
  { to: "/analytics", label: "Analytics", icon: "analytics" },
  { to: "/settings", label: "Settings", icon: "settings" },
];

const PERSONA_LABEL: Record<string, string> = {
  aiml: "AI/ML engineer",
  fullstack: "Full-stack developer",
  data: "Data analyst",
};

export function personaLabel(p?: string | null): string {
  if (!p) return "No persona yet";
  return PERSONA_LABEL[p] ?? p;
}

function initials(s: string): string {
  const parts = s.replace(/@.*/, "").split(/[\s._-]+/).filter(Boolean);
  return ((parts[0]?.[0] ?? "") + (parts[1]?.[0] ?? "")).toUpperCase() || "G";
}

export function BrandMark() {
  return (
    <span className="brand-mark" aria-hidden="true">
      <Icon name="mark" />
    </span>
  );
}

export function Layout() {
  const { user, signOut } = useAuth();
  const [open, setOpen] = useState(false);
  const loc = useLocation();

  useEffect(() => setOpen(false), [loc.pathname]);
  useEffect(() => {
    if (!open) return;
    const onKey = (e: KeyboardEvent) => e.key === "Escape" && setOpen(false);
    document.addEventListener("keydown", onKey);
    return () => document.removeEventListener("keydown", onKey);
  }, [open]);

  return (
    <div className="shell">
      <a href="#main" className="skip-link">
        Skip to content
      </a>
      {open && <div className="scrim" onClick={() => setOpen(false)} aria-hidden="true" />}
      <aside className={`sidebar ${open ? "open" : ""}`} aria-label="Primary">
        <div className="brand">
          <BrandMark />
          GigBid
        </div>
        <nav className="nav" aria-label="Main">
          {NAV.map((n) => (
            <NavLink key={n.to} to={n.to} className={({ isActive }) => (isActive ? "active" : "")}>
              <Icon name={n.icon} />
              {n.label}
            </NavLink>
          ))}
        </nav>
        <div className="sidebar-foot">
          <button className="btn ghost sm" style={{ justifyContent: "flex-start" }} onClick={() => void signOut()}>
            <Icon name="logout" size="sm" />
            Sign out
          </button>
        </div>
      </aside>
      <div className="main">
        <header className="topbar">
          <button className="btn ghost sm menu-btn" aria-label="Open navigation" aria-expanded={open} onClick={() => setOpen(true)}>
            <Icon name="menu" />
          </button>
          <span className="topbar-brand">GigBid</span>
          <span className="topbar-spacer" />
          {user && (
            <div className="user-chip" data-testid="user-chip">
              <span className="who">
                <strong>{user.name || user.email}</strong>
                <span>{personaLabel(user.persona)}</span>
              </span>
              <span className="avatar" aria-hidden="true">
                {initials(user.name || user.email)}
              </span>
            </div>
          )}
        </header>
        <DegradedBanner />
        <main id="main" className="content" tabIndex={-1}>
          <Outlet />
        </main>
      </div>
    </div>
  );
}

export function PageHead({ title, sub, actions }: { title: string; sub?: string; actions?: React.ReactNode }) {
  return (
    <div className="page-head">
      <div>
        <h1>{title}</h1>
        {sub && <p>{sub}</p>}
      </div>
      {actions && <div className="row">{actions}</div>}
    </div>
  );
}
