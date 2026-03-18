"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { useAuth } from "@/contexts/AuthContext";

export default function LoginPage() {
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);
  const { login } = useAuth();
  const router = useRouter();

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError("");
    setLoading(true);
    try {
      const ok = await login(username, password);
      if (!ok) {
        setError("Invalid username or password. Please try again.");
        return;
      }
      router.push("/dashboard");
      router.refresh();
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="min-h-screen bg-[#f2f2f2] flex flex-col items-center justify-center p-4">
      {/* Logo */}
      <div className="text-center mb-8">
        <div className="inline-flex items-center gap-2 mb-1">
          <span className="text-3xl font-bold text-[#22c55e]">F</span>
          <span className="text-2xl font-semibold text-[#374151]">arq</span>
        </div>
        <p className="text-sm text-[#6b7280]">POI Review Dashboard</p>
      </div>

      {/* Login card */}
      <div className="w-full max-w-md bg-white rounded-xl shadow-md p-8">
        <h1 className="text-xl font-bold text-[#374151] mb-1">Welcome back</h1>
        <p className="text-sm text-[#6b7280] mb-6">Enter your credentials to continue</p>

        <form onSubmit={handleSubmit} className="space-y-4">
          <div>
            <label htmlFor="username" className="block text-sm font-medium text-[#374151] mb-1">
              Username
            </label>
            <input
              id="username"
              type="text"
              value={username}
              onChange={(e) => setUsername(e.target.value)}
              className="w-full px-3 py-2 border border-[#d1d5db] rounded-lg text-[#374151] focus:outline-none focus:ring-2 focus:ring-[#22c55e]/50 focus:border-[#22c55e]"
              placeholder="Enter username"
              autoComplete="username"
            />
          </div>
          <div>
            <label htmlFor="password" className="block text-sm font-medium text-[#374151] mb-1">
              Password
            </label>
            <input
              id="password"
              type="password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              className="w-full px-3 py-2 border border-[#d1d5db] rounded-lg text-[#374151] focus:outline-none focus:ring-2 focus:ring-[#22c55e]/50 focus:border-[#22c55e]"
              placeholder="Enter password"
              autoComplete="current-password"
            />
          </div>
          {error && <p className="text-sm text-red-600">{error}</p>}
          <p className="text-xs text-[#6b7280]">
            Make sure you&apos;re connected to the required VPN if applicable.
          </p>
          <button
            type="submit"
            disabled={loading}
            className="w-full py-3 bg-[#22c55e] hover:bg-[#16a34a] disabled:opacity-70 text-white font-medium rounded-lg transition-colors"
          >
            {loading ? "Signing in\u2026" : "Login"}
          </button>
        </form>
      </div>
    </div>
  );
}
