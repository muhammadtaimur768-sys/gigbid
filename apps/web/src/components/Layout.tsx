import { useEffect, useState } from "react";
import { NavLink, Outlet, useLocation } from "react-router-dom";
import { DegradedBanner } from "./DegradedBanner";
import { useAuth } from "../lib/auth";

const NAV = [
  { to: "/inbox", label: "Job inbox" },
  { to: "/pipeline", label: "Pipeline" },
  { to: "/messages", label: "Messages" },
  { to: "/runs", label: "Agent runs" },
  { to: "/analytics", label: "Analytics" },
  { to: "/settings", label: "Settings" },
];

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
          <span className="brand-mark" aria-hidden="true">
            G
          </span>
          GigBid
        </div>
        <nav className="nav stack" style={{ gap: 2 }}>
          {NAV.map((n) => (
            <NavLink key={n.to} to={n.to} className={({ isActive }) => (isActive ? "active" : "")}>
              {n.label}
            </NavLink>
          ))}
        </nav>
        <div className="sidebar-foot">
          <div style={{ fontWeight: 600, color: "var(--text)" }}>{user?.name || user?.email}</div>
          {user?.persona && <div>Persona: {user.persona}</div>}
          <button className="btn sm" style={{ marginTop: 8 }} onClick={() => void signOut()}>
            Sign out
          </button>
        </div>
      </aside>
      <div className="main">
        <header className="topbar">
          <button className="btn sm" aria-label="Open navigation" aria-expanded={open} onClick={() => setOpen(true)}>
            Menu
          </button>
          <strong>GigBid</strong>
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
