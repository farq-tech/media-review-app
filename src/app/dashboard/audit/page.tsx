"use client";

import { useState, useEffect } from "react";
import { fetchAuditLog, fetchReviewerProductivity, type AuditEvent, type ReviewerStats } from "@/api/stats";

function timeAgo(iso: string): string {
  const d = new Date(iso);
  const now = Date.now();
  const diff = now - d.getTime();
  const mins = Math.floor(diff / 60000);
  if (mins < 1) return "just now";
  if (mins < 60) return `${mins}m ago`;
  const hours = Math.floor(mins / 60);
  if (hours < 24) return `${hours}h ago`;
  const days = Math.floor(hours / 24);
  return `${days}d ago`;
}

export default function AuditPage() {
  const [events, setEvents] = useState<AuditEvent[]>([]);
  const [reviewers, setReviewers] = useState<ReviewerStats[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let cancelled = false;
    Promise.all([fetchAuditLog(), fetchReviewerProductivity()])
      .then(([auditData, prodData]) => {
        if (!cancelled) {
          setEvents(auditData.logs);
          setReviewers(prodData.reviewers);
        }
      })
      .finally(() => { if (!cancelled) setLoading(false); });
    return () => { cancelled = true; };
  }, []);

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold text-[#374151]">Audit Log</h1>
        <p className="text-sm text-[#6b7280] mt-0.5">Edit history and reviewer activity</p>
      </div>

      {/* Reviewer productivity */}
      {reviewers.length > 0 && (
        <div className="bg-white rounded-xl border border-[#e5e7eb] p-5">
          <h2 className="text-sm font-semibold text-[#374151] mb-3">Reviewer Activity</h2>
          <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
            {reviewers.map((r) => (
              <div key={r.reviewer} className="bg-[#f9fafb] rounded-lg p-3 text-center">
                <p className="text-xs font-medium text-[#374151]">{r.reviewer}</p>
                <p className="text-lg font-bold text-[#374151]">{r.total_actions}</p>
                <p className="text-[10px] text-[#94a3b8]">
                  {r.approvals} approved &middot; {r.edits} edits
                </p>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Timeline */}
      {loading ? (
        <div className="space-y-3">
          {Array.from({ length: 5 }).map((_, i) => (
            <div key={i} className="bg-white rounded-xl border border-[#e5e7eb] p-4 h-16 animate-pulse" />
          ))}
        </div>
      ) : events.length === 0 ? (
        <div className="bg-white rounded-xl border border-[#e5e7eb] p-12 text-center">
          <p className="text-[#6b7280]">No audit events found</p>
        </div>
      ) : (
        <div className="bg-white rounded-xl border border-[#e5e7eb] overflow-hidden">
          <table className="w-full text-sm">
            <thead>
              <tr className="bg-[#f9fafb] border-b border-[#e5e7eb]">
                <th className="px-4 py-2 text-left text-xs font-semibold text-[#6b7280]">Time</th>
                <th className="px-4 py-2 text-left text-xs font-semibold text-[#6b7280]">Reviewer</th>
                <th className="px-4 py-2 text-left text-xs font-semibold text-[#6b7280]">POI</th>
                <th className="px-4 py-2 text-left text-xs font-semibold text-[#6b7280]">Action</th>
                <th className="px-4 py-2 text-left text-xs font-semibold text-[#6b7280]">Field</th>
                <th className="px-4 py-2 text-left text-xs font-semibold text-[#6b7280]">Change</th>
              </tr>
            </thead>
            <tbody>
              {events.slice(0, 100).map((evt) => (
                <tr key={evt.id} className="border-b border-[#e5e7eb] hover:bg-[#f9fafb]">
                  <td className="px-4 py-2 text-xs text-[#6b7280]">{timeAgo(evt.created_at)}</td>
                  <td className="px-4 py-2 text-xs font-medium text-[#374151]">{evt.reviewer}</td>
                  <td className="px-4 py-2 text-xs text-[#374151] truncate max-w-[150px]">{evt.poi_name || evt.global_id}</td>
                  <td className="px-4 py-2">
                    <span className="px-1.5 py-0.5 bg-blue-50 text-blue-700 rounded text-[10px] font-medium">
                      {evt.action}
                    </span>
                  </td>
                  <td className="px-4 py-2 text-xs text-[#6b7280]">{evt.field_name}</td>
                  <td className="px-4 py-2 text-xs">
                    {evt.old_value && (
                      <span className="text-red-500 line-through mr-1">{evt.old_value.slice(0, 20)}</span>
                    )}
                    <span className="text-green-600">{evt.new_value?.slice(0, 30)}</span>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
