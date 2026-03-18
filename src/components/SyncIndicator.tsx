"use client";

import { useSyncContext } from "@/contexts/SyncContext";

export default function SyncIndicator() {
  const { syncState } = useSyncContext();

  const styles = {
    idle: "bg-gray-50 text-gray-500 border-gray-200",
    syncing: "bg-blue-50 text-blue-700 border-blue-200",
    synced: "bg-green-50 text-green-700 border-green-200",
    failed: "bg-red-50 text-red-700 border-red-200",
  };

  const labels = {
    idle: "Idle",
    syncing: "Syncing...",
    synced: "Synced",
    failed: "Sync failed",
  };

  return (
    <span className={`inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-[11px] font-semibold border ${styles[syncState]}`}>
      {syncState === "syncing" && (
        <span className="w-2 h-2 rounded-full bg-blue-500 animate-pulse" />
      )}
      {syncState === "synced" && (
        <span className="w-2 h-2 rounded-full bg-green-500" />
      )}
      {syncState === "failed" && (
        <span className="w-2 h-2 rounded-full bg-red-500" />
      )}
      {labels[syncState]}
    </span>
  );
}
