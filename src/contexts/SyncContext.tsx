"use client";

import React, { createContext, useContext, useState, useEffect, useCallback, useRef } from "react";
import { useAuth } from "./AuthContext";
import { fetchRecentUpdates, sendPresenceHeartbeat, fetchPresenceUsers } from "@/api/sync";
import type { SyncUpdate } from "@/types/poi";

interface UndoEntry {
  gid: string;
  field: string;
  prevValue: unknown;
  action: string;
  timestamp: number;
}

interface SyncContextType {
  syncState: "idle" | "syncing" | "synced" | "failed";
  pendingUpdates: SyncUpdate[];
  presenceUsers: { username: string; color?: string }[];
  undoStack: UndoEntry[];
  pushUndo: (entry: Omit<UndoEntry, "timestamp">) => void;
  popUndo: () => UndoEntry | undefined;
  dismissUpdates: () => void;
}

const SyncContext = createContext<SyncContextType | undefined>(undefined);

const UNDO_MAX = 20;
const SYNC_INTERVAL = 10_000;
const PRESENCE_INTERVAL = 15_000;

export function SyncProvider({ children }: { children: React.ReactNode }) {
  const { user } = useAuth();
  const [syncState, setSyncState] = useState<"idle" | "syncing" | "synced" | "failed">("idle");
  const [pendingUpdates, setPendingUpdates] = useState<SyncUpdate[]>([]);
  const [presenceUsers, setPresenceUsers] = useState<{ username: string; color?: string }[]>([]);
  const [undoStack, setUndoStack] = useState<UndoEntry[]>([]);
  const syncTimer = useRef<ReturnType<typeof setInterval>>();
  const presenceTimer = useRef<ReturnType<typeof setInterval>>();

  // Poll for updates every 10s
  useEffect(() => {
    if (!user) return;

    const checkUpdates = async () => {
      setSyncState("syncing");
      try {
        const updates = await fetchRecentUpdates();
        if (updates.length > 0) {
          setPendingUpdates((prev) => [...updates, ...prev].slice(0, 50));
        }
        setSyncState("synced");
      } catch {
        setSyncState("failed");
      }
    };

    checkUpdates();
    syncTimer.current = setInterval(checkUpdates, SYNC_INTERVAL);
    return () => clearInterval(syncTimer.current);
  }, [user]);

  // Presence heartbeat every 15s
  useEffect(() => {
    if (!user) return;

    const heartbeat = async () => {
      if (user.username) await sendPresenceHeartbeat(user.username);
      const users = await fetchPresenceUsers();
      setPresenceUsers(users);
    };

    heartbeat();
    presenceTimer.current = setInterval(heartbeat, PRESENCE_INTERVAL);
    return () => clearInterval(presenceTimer.current);
  }, [user]);

  const pushUndo = useCallback((entry: Omit<UndoEntry, "timestamp">) => {
    setUndoStack((prev) => [{ ...entry, timestamp: Date.now() }, ...prev].slice(0, UNDO_MAX));
  }, []);

  const popUndo = useCallback((): UndoEntry | undefined => {
    let entry: UndoEntry | undefined;
    setUndoStack((prev) => {
      if (prev.length === 0) return prev;
      entry = prev[0];
      return prev.slice(1);
    });
    return entry;
  }, []);

  const dismissUpdates = useCallback(() => {
    setPendingUpdates([]);
  }, []);

  return (
    <SyncContext.Provider
      value={{
        syncState, pendingUpdates, presenceUsers,
        undoStack, pushUndo, popUndo, dismissUpdates,
      }}
    >
      {children}
    </SyncContext.Provider>
  );
}

export function useSyncContext() {
  const ctx = useContext(SyncContext);
  if (!ctx) throw new Error("useSyncContext must be used within SyncProvider");
  return ctx;
}
