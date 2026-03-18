"use client";

import React, { createContext, useContext, useState, useEffect } from "react";

interface User {
  username: string;
  display_name?: string;
  role?: string;
  color?: string;
}

interface AuthContextType {
  user: User | null;
  login: (username: string, password: string) => Promise<boolean>;
  logout: () => void;
  isReady: boolean;
}

const AuthContext = createContext<AuthContextType | undefined>(undefined);

const AUTH_KEY = "farq-reviewer";

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const [user, setUser] = useState<User | null>(null);
  const [isReady, setIsReady] = useState(false);

  useEffect(() => {
    try {
      const stored = typeof window !== "undefined" ? localStorage.getItem(AUTH_KEY) : null;
      if (stored) {
        setUser(JSON.parse(stored) as User);
      }
    } catch {
      setUser(null);
    }
    setIsReady(true);
  }, []);

  const login = async (username: string, password: string): Promise<boolean> => {
    if (!username?.trim() || !password?.trim()) return false;

    const colors = ["#22c55e", "#3b82f6", "#f59e0b", "#ef4444", "#8b5cf6", "#ec4899"];

    try {
      const res = await fetch("/api/login", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ username: username.trim(), password }),
      });

      const data = await res.json();

      if (data.ok) {
        const u: User = {
          username: data.username || username.trim(),
          display_name: data.display_name,
          role: data.role || "reviewer",
          color: colors[Math.floor(Math.random() * colors.length)],
        };
        setUser(u);
        if (typeof window !== "undefined") localStorage.setItem(AUTH_KEY, JSON.stringify(u));
        return true;
      }

      // Invalid credentials
      return false;
    } catch {
      // API unreachable
      return false;
    }
  };

  const logout = () => {
    setUser(null);
    if (typeof window !== "undefined") localStorage.removeItem(AUTH_KEY);
  };

  return (
    <AuthContext.Provider value={{ user, login, logout, isReady }}>
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth() {
  const ctx = useContext(AuthContext);
  if (ctx === undefined) throw new Error("useAuth must be used within AuthProvider");
  return ctx;
}
