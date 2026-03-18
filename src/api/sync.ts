import { apiFetch } from "./client";
import type { SyncUpdate } from "@/types/poi";

export async function fetchRecentUpdates(): Promise<SyncUpdate[]> {
  try {
    const data = await apiFetch<SyncUpdate[]>("/api/pois/recent-updates");
    return Array.isArray(data) ? data : [];
  } catch {
    return [];
  }
}

export async function sendPresenceHeartbeat(username: string): Promise<void> {
  try {
    await apiFetch("/api/presence/heartbeat", {
      method: "POST",
      body: JSON.stringify({ username }),
    });
  } catch {
    // Silently fail
  }
}

export async function fetchPresenceUsers(): Promise<{ username: string; view?: string; poi?: string }[]> {
  try {
    const data = await apiFetch<{ ok: boolean; users: { username: string; view?: string; poi?: string }[]; count: number }>("/api/presence/active");
    return Array.isArray(data.users) ? data.users : [];
  } catch {
    return [];
  }
}
