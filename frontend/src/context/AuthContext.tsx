import { createContext, useContext, useMemo, useState, type ReactNode } from "react";
import type { AuthUser } from "../types";

const STORAGE_KEY = "dpm_auth";

const DEMO_USERS: Record<string, { password: string; name: string }> = {
  "admin@dental.com": { password: "dental123", name: "Admin User" },
  "demo@dental.com": { password: "demo1234", name: "Demo User" },
};

interface AuthContextValue {
  user: AuthUser | null;
  isAuthenticated: boolean;
  login: (email: string, password: string) => Promise<void>;
  logout: () => void;
}

const AuthContext = createContext<AuthContextValue | null>(null);

function readStoredUser(): AuthUser | null {
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    return raw ? (JSON.parse(raw) as AuthUser) : null;
  } catch {
    return null;
  }
}

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<AuthUser | null>(() => readStoredUser());

  const value = useMemo<AuthContextValue>(
    () => ({
      user,
      isAuthenticated: !!user,
      login: async (email: string, password: string) => {
        await new Promise((r) => setTimeout(r, 600));
        const normalized = email.trim().toLowerCase();
        const account = DEMO_USERS[normalized];
        if (!account || account.password !== password) {
          throw new Error("Invalid email or password");
        }
        const next: AuthUser = { email: normalized, name: account.name };
        localStorage.setItem(STORAGE_KEY, JSON.stringify(next));
        setUser(next);
      },
      logout: () => {
        localStorage.removeItem(STORAGE_KEY);
        setUser(null);
      },
    }),
    [user],
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth() {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error("useAuth must be used within AuthProvider");
  return ctx;
}
