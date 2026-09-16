import { createContext, useCallback, useContext, useEffect, useMemo, useState, type ReactNode } from "react";
import { authApi, type PrincipalOut } from "@/api/endpoints";
import { APIError } from "@/api/client";

type Role = "USER" | "AGENT" | "ADMIN";

interface AuthState {
  principal: PrincipalOut | null;
  loading: boolean;
  error: string | null;
  isStaff: boolean;
  isAdmin: boolean;
  login: (email: string, password: string) => Promise<void>;
  logout: () => Promise<void>;
  refresh: () => Promise<void>;
}

const AuthContext = createContext<AuthState | null>(null);

export function AuthProvider({ children }: { children: ReactNode }) {
  const [principal, setPrincipal] = useState<PrincipalOut | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const refresh = useCallback(async () => {
    try {
      const me = await authApi.me();
      setPrincipal(me);
    } catch {
      setPrincipal(null);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void refresh();
  }, [refresh]);

  const login = useCallback(async (email: string, password: string) => {
    setError(null);
    try {
      const me = await authApi.login(email, password);
      setPrincipal(me);
    } catch (e) {
      const msg = e instanceof APIError ? e.detail || e.message : "登录失败";
      setError(msg);
      throw e;
    }
  }, []);

  const logout = useCallback(async () => {
    try {
      await authApi.logout();
    } finally {
      setPrincipal(null);
    }
  }, []);

  const value = useMemo<AuthState>(() => {
    const role = (principal?.role ?? "USER") as Role;
    return {
      principal,
      loading,
      error,
      isStaff: principal?.is_staff ?? false,
      isAdmin: role === "ADMIN",
      login,
      logout,
      refresh,
    };
  }, [principal, loading, error, login, logout, refresh]);

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth(): AuthState {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error("useAuth 必须在 AuthProvider 内使用");
  return ctx;
}
