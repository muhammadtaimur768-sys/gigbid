import { createContext, useCallback, useContext, useEffect, useState, type ReactNode } from "react";
import { api, type User } from "./api";

interface AuthCtx {
  user: User | null;
  ready: boolean;
  refresh: () => Promise<User | null>;
  setUser: (u: User | null) => void;
  signOut: () => Promise<void>;
}

const Ctx = createContext<AuthCtx | null>(null);

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<User | null>(null);
  const [ready, setReady] = useState(false);

  const refresh = useCallback(async () => {
    try {
      const u = await api.me();
      setUser(u);
      return u;
    } catch {
      setUser(null);
      return null;
    } finally {
      setReady(true);
    }
  }, []);

  useEffect(() => {
    void refresh();
  }, [refresh]);

  const signOut = useCallback(async () => {
    try {
      await api.logout();
    } catch {
      /* ignore */
    }
    setUser(null);
  }, []);

  return <Ctx.Provider value={{ user, ready, refresh, setUser, signOut }}>{children}</Ctx.Provider>;
}

export function useAuth(): AuthCtx {
  const c = useContext(Ctx);
  if (!c) throw new Error("useAuth outside AuthProvider");
  return c;
}
