import { apiFetch } from "./client";

export interface DuplicatePair {
  source_gid: string;
  candidate_gid: string;
  source_name: string;
  candidate_name: string;
  final_score: number;
  name_score: number;
  phone_score: number;
  distance_score: number;
  category_score: number;
  auxiliary_score: number;
  match_reasons: string[];
  distance_m: number;
  match_status: "MATCH" | "POSSIBLE_MATCH";
}

export interface DuplicateGroup {
  golden_index: number;
  members: DuplicatePair[];
}

export async function detectDuplicates(options?: {
  max_distance?: number;
  match_threshold?: number;
  possible_threshold?: number;
}): Promise<{ groups: DuplicateGroup[]; pairs: DuplicatePair[] }> {
  try {
    const data = await apiFetch<{ groups: DuplicateGroup[]; pairs: DuplicatePair[] }>("/api/detect-duplicates", {
      method: "POST",
      body: JSON.stringify(options || {}),
    });
    return data;
  } catch {
    return { groups: [], pairs: [] };
  }
}
