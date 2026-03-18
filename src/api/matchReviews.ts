import { apiFetch } from "./client";
import type { MatchReviewPair } from "@/types/poi";

export async function fetchReviewedPairs(reviewer?: string): Promise<Record<string, string>> {
  try {
    const params: Record<string, string> = {};
    if (reviewer) params.reviewer = reviewer;
    const data = await apiFetch<Record<string, string>>("/api/match-reviews/reviewed-pairs", { params });
    return data || {};
  } catch {
    return {};
  }
}

export async function submitReview(pair: {
  source_gid: string;
  candidate_gid: string;
  verdict: "MATCH" | "NOT_MATCH";
  reviewer: string;
  notes?: string;
}): Promise<boolean> {
  try {
    await apiFetch("/api/match-reviews", {
      method: "POST",
      body: JSON.stringify(pair),
    });
    return true;
  } catch {
    return false;
  }
}

export async function exportTrainingData(format: "json" | "csv" = "json"): Promise<unknown> {
  return apiFetch(`/api/match-reviews/export-training`, {
    params: { format },
  });
}
