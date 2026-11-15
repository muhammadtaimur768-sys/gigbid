import type { ReactNode } from "react";

export function Loading({ label = "Loading", rows = 3 }: { label?: string; rows?: number }) {
  return (
    <div role="status" aria-live="polite" aria-busy="true" className="stack" data-testid="loading">
      <span className="sr-only">{label}…</span>
      {Array.from({ length: rows }).map((_, i) => (
        <div key={i} className="skeleton" style={{ width: `${90 - i * 12}%`, height: 16 }} />
      ))}
    </div>
  );
}

export function Empty({ title, children, action }: { title: string; children?: ReactNode; action?: ReactNode }) {
  return (
    <div className="state" data-testid="empty">
      <h3>{title}</h3>
      {children && <p>{children}</p>}
      {action}
    </div>
  );
}

export function ErrorState({ error, onRetry }: { error: Error | string; onRetry?: () => void }) {
  const msg = typeof error === "string" ? error : error.message;
  return (
    <div className="state error" role="alert" data-testid="error">
      <h3>Something went wrong</h3>
      <p>{msg}</p>
      {onRetry && (
        <button className="btn" onClick={onRetry}>
          Try again
        </button>
      )}
    </div>
  );
}

/** Renders loading / error / empty / content for an async resource. */
export function AsyncView<T>({
  state,
  empty,
  isEmpty,
  children,
  rows,
}: {
  state: { data: T | undefined; error: Error | undefined; loading: boolean; reload: () => void };
  empty?: ReactNode;
  isEmpty?: (d: T) => boolean;
  children: (d: T) => ReactNode;
  rows?: number;
}) {
  if (state.loading && state.data === undefined) return <Loading rows={rows} />;
  if (state.error) return <ErrorState error={state.error} onRetry={state.reload} />;
  if (state.data === undefined) return <Loading rows={rows} />;
  const d = state.data;
  if (isEmpty ? isEmpty(d) : Array.isArray(d) && d.length === 0) return <>{empty ?? <Empty title="Nothing here yet" />}</>;
  return <>{children(d)}</>;
}
