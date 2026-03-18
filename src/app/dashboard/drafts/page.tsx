"use client";

import { useState, useMemo } from "react";
import { usePOIContext } from "@/contexts/POIContext";
import { useToast } from "@/components/Toast";
import StatusBadge from "@/components/StatusBadge";

export default function DraftsPage() {
  const { allPois, loading, saveField } = usePOIContext();
  const { toast } = useToast();
  const [filter, setFilter] = useState<"all" | "draft" | "pending">("draft");

  const drafts = useMemo(() => {
    return allPois.filter((p) => {
      if (filter === "draft") return !p.Review_Status || p.Review_Status === "Draft";
      if (filter === "pending") return p.Review_Status === "Pending";
      return !p.Review_Status || p.Review_Status === "Draft" || p.Review_Status === "Pending";
    });
  }, [allPois, filter]);

  const handleConfirm = async (gid: string) => {
    const ok = await saveField(gid, "Review_Status", "Reviewed");
    toast(ok ? "Draft confirmed" : "Failed to confirm", ok ? "success" : "error");
  };

  const handleReject = async (gid: string) => {
    const ok = await saveField(gid, "Review_Status", "Rejected");
    toast(ok ? "Draft rejected" : "Failed to reject", ok ? "info" : "error");
  };

  return (
    <div className="space-y-4">
      <div>
        <h1 className="text-2xl font-bold text-[#374151]">Drafts</h1>
        <p className="text-sm text-[#6b7280] mt-0.5">{drafts.length} draft POIs</p>
      </div>

      <div className="flex gap-1">
        {(["all", "draft", "pending"] as const).map((f) => (
          <button
            key={f}
            onClick={() => setFilter(f)}
            className={`px-3 py-1.5 rounded-lg text-sm font-medium transition-colors ${
              filter === f ? "bg-[#22c55e] text-white" : "text-[#6b7280] hover:bg-[#f3f4f6]"
            }`}
          >
            {f.charAt(0).toUpperCase() + f.slice(1)}
          </button>
        ))}
      </div>

      {loading ? (
        <div className="space-y-3">
          {Array.from({ length: 5 }).map((_, i) => (
            <div key={i} className="bg-white rounded-xl border border-[#e5e7eb] p-4 h-16 animate-pulse" />
          ))}
        </div>
      ) : drafts.length === 0 ? (
        <div className="bg-white rounded-xl border border-[#e5e7eb] p-12 text-center">
          <p className="text-[#6b7280]">No drafts found</p>
        </div>
      ) : (
        <div className="bg-white rounded-xl border border-[#e5e7eb] overflow-hidden">
          <table className="w-full text-sm">
            <thead>
              <tr className="bg-[#f9fafb] border-b border-[#e5e7eb]">
                <th className="px-4 py-2 text-left text-xs font-semibold text-[#6b7280]">Name</th>
                <th className="px-4 py-2 text-left text-xs font-semibold text-[#6b7280]">Category</th>
                <th className="px-4 py-2 text-left text-xs font-semibold text-[#6b7280]">District</th>
                <th className="px-4 py-2 text-left text-xs font-semibold text-[#6b7280]">Status</th>
                <th className="px-4 py-2 text-left text-xs font-semibold text-[#6b7280]">Actions</th>
              </tr>
            </thead>
            <tbody>
              {drafts.slice(0, 50).map((poi) => (
                <tr key={poi.GlobalID} className="border-b border-[#e5e7eb] hover:bg-[#f9fafb]">
                  <td className="px-4 py-2">
                    <p className="text-sm font-medium text-[#374151]">{poi.Name_EN || "Unnamed"}</p>
                    {poi.Name_AR && <p className="text-xs text-[#6b7280]" dir="rtl">{poi.Name_AR}</p>}
                  </td>
                  <td className="px-4 py-2 text-xs text-[#374151]">{String(poi.Category ?? "—")}</td>
                  <td className="px-4 py-2 text-xs text-[#374151]">{String(poi.District_EN ?? "—")}</td>
                  <td className="px-4 py-2">
                    <StatusBadge status={String(poi.Review_Status ?? "Draft")} />
                  </td>
                  <td className="px-4 py-2">
                    <div className="flex gap-1.5">
                      <button
                        onClick={() => handleConfirm(poi.GlobalID)}
                        className="px-2 py-1 bg-[#22c55e] hover:bg-[#16a34a] text-white text-xs rounded"
                      >
                        Confirm
                      </button>
                      <button
                        onClick={() => handleReject(poi.GlobalID)}
                        className="px-2 py-1 bg-red-500 hover:bg-red-600 text-white text-xs rounded"
                      >
                        Reject
                      </button>
                    </div>
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
