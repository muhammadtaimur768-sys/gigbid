import type { ReactNode } from "react";
import { Navigate, Route, Routes, useLocation } from "react-router-dom";
import { Layout } from "./components/Layout";
import { Loading } from "./components/States";
import { useAuth } from "./lib/auth";
import Analytics from "./pages/Analytics";
import Inbox from "./pages/Inbox";
import JobDetail from "./pages/JobDetail";
import Login from "./pages/Login";
import Messages from "./pages/Messages";
import Onboarding from "./pages/Onboarding";
import Pipeline from "./pages/Pipeline";
import RunViewer, { RunList } from "./pages/Runs";
import Settings from "./pages/Settings";
import Studio from "./pages/Studio";

function RequireAuth({ children, allowUnonboarded = false }: { children: ReactNode; allowUnonboarded?: boolean }) {
  const { user, ready } = useAuth();
  const loc = useLocation();
  if (!ready)
    return (
      <div className="auth-wrap">
        <div style={{ width: 320 }}>
          <Loading label="Loading your workspace" />
        </div>
      </div>
    );
  if (!user) return <Navigate to="/login" replace state={{ from: loc.pathname }} />;
  if (!user.onboarded && !allowUnonboarded) return <Navigate to="/onboarding" replace />;
  return <>{children}</>;
}

function NotFound() {
  return (
    <div className="state">
      <h3>Page not found</h3>
      <p>
        <a href="/inbox">Back to the inbox</a>
      </p>
    </div>
  );
}

export default function App() {
  return (
    <Routes>
      <Route path="/login" element={<Login />} />
      <Route
        path="/onboarding"
        element={
          <RequireAuth allowUnonboarded>
            <Onboarding />
          </RequireAuth>
        }
      />
      <Route
        element={
          <RequireAuth>
            <Layout />
          </RequireAuth>
        }
      >
        <Route path="/" element={<Navigate to="/inbox" replace />} />
        <Route path="/inbox" element={<Inbox />} />
        <Route path="/jobs/:id" element={<JobDetail />} />
        <Route path="/studio/:id" element={<Studio />} />
        <Route path="/pipeline" element={<Pipeline />} />
        <Route path="/messages" element={<Messages />} />
        <Route path="/runs" element={<RunList />} />
        <Route path="/runs/:id" element={<RunViewer />} />
        <Route path="/analytics" element={<Analytics />} />
        <Route path="/settings" element={<Settings />} />
        <Route path="*" element={<NotFound />} />
      </Route>
    </Routes>
  );
}
