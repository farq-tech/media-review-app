"use client";

import { useSyncContext } from "@/contexts/SyncContext";

const DEFAULT_COLORS = ["#22c55e", "#3b82f6", "#f59e0b", "#ef4444", "#8b5cf6", "#ec4899"];

export default function PresenceBar() {
  const { presenceUsers } = useSyncContext();

  if (presenceUsers.length === 0) return null;

  return (
    <div className="flex items-center gap-0.5">
      {presenceUsers.slice(0, 5).map((u, i) => (
        <div
          key={u.username}
          className="relative w-7 h-7 rounded-full flex items-center justify-center text-white text-[10px] font-bold border-2 border-white"
          style={{
            backgroundColor: u.color || DEFAULT_COLORS[i % DEFAULT_COLORS.length],
            marginLeft: i > 0 ? "-6px" : "0",
            zIndex: 5 - i,
          }}
          title={u.username}
        >
          {u.username.charAt(0).toUpperCase()}
          <span className="absolute -bottom-0.5 -right-0.5 w-2 h-2 rounded-full bg-green-400 border border-white" />
        </div>
      ))}
      {presenceUsers.length > 5 && (
        <span className="text-xs text-[#6b7280] ml-1">+{presenceUsers.length - 5}</span>
      )}
    </div>
  );
}
