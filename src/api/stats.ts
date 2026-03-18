import { apiFetch } from "./client";

export interface AuditEvent {
  id: number;
  global_id: string;
  poi_name?: string;
  field_name: string;
  old_value: string;
  new_value: string;
  reviewer: string;
  action: string;
  created_at: string;
}

export interface ReviewerStats {
  reviewer: string;
  total_actions: number;
  approvals: number;
  rejections: number;
  edits: number;
  pois_touched: number;
  first_activity: string;
  last_activity: string;
  active_days: number;
}

export async function fetchAuditLog(gid?: string): Promise<{ logs: AuditEvent[]; total: number }> {
  try {
    const params: Record<string, string> = {};
    if (gid) params.global_id = gid;
    const data = await apiFetch<{ logs: AuditEvent[]; total: number }>("/api/audit-log", { params });
    return { logs: Array.isArray(data.logs) ? data.logs : [], total: data.total || 0 };
  } catch {
    return { logs: [], total: 0 };
  }
}

export async function fetchReviewerProductivity(): Promise<{ reviewers: ReviewerStats[]; daily: { day: string; reviewer: string; actions: number }[] }> {
  try {
    const data = await apiFetch<{ ok: boolean; reviewers: ReviewerStats[]; daily: { day: string; reviewer: string; actions: number }[] }>("/api/stats/reviewer-productivity");
    return { reviewers: data.reviewers || [], daily: data.daily || [] };
  } catch {
    return { reviewers: [], daily: [] };
  }
}
