import { apiFetch } from "./client";
import type { POI } from "@/types/poi";

export async function fetchPOIs(): Promise<POI[]> {
  try {
    const data = await apiFetch<POI[] | Record<string, unknown>>("/api/pois");
    if (Array.isArray(data)) return data;
    return [];
  } catch {
    return [];
  }
}

export async function fetchPOI(gid: string): Promise<POI | null> {
  try {
    return await apiFetch<POI>(`/api/pois/${encodeURIComponent(gid)}`);
  } catch {
    return null;
  }
}

export async function updatePOI(
  gid: string,
  fields: Record<string, unknown>,
  reviewer?: string
): Promise<boolean> {
  try {
    await apiFetch(`/api/pois/${encodeURIComponent(gid)}`, {
      method: "PATCH",
      body: JSON.stringify({ ...fields, _reviewer: reviewer }),
    });
    return true;
  } catch {
    return false;
  }
}

export async function runQAPipeline(): Promise<unknown> {
  return apiFetch("/api/validate-all", { method: "POST" });
}
