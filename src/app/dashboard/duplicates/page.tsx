"use client";

import { useState, useCallback } from "react";
import { usePOIContext } from "@/contexts/POIContext";
import { useToast } from "@/components/Toast";
import { detectDuplicates, type DuplicateGroup, type DuplicatePair } from "@/api/duplicates";

export default function DuplicatesPage() {
  const { allPois } = usePOIContext();
  const { toast } = useToast();
  const [loading, setLoading] = useState(false);
  const [groups, setGroups] = useState<DuplicateGroup[]>([]);
  const [pairs, setPairs] = useState<DuplicatePair[]>([]);
  const [expandedGroup, setExpandedGroup] = useState<number | null>(null);

  const runDetection = useCallback(async () => {
    setLoading(true);
    toast("Running duplicate detection...", "info");
    const result = await detectDuplicates();
    setGroups(result.groups);
    setPairs(result.pairs);
    toast(`Found ${result.groups.length} groups, ${result.pairs.length} pairs`, "success");
    setLoading(false);
  }, [toast]);

  const findPoi = (gid: string) => allPois.find((p) => p.GlobalID === gid);

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-[#374151]">Duplicate Detection</h1>
          <p className="text-sm text-[#6b7280] mt-0.5">
            {groups.length > 0 ? `${groups.length} groups found` : "Run detection to find duplicates"}
          </p>
        </div>
        <button
          onClick={runDetection}
          disabled={loading}
          className="px-4 py-2 bg-[#22c55e] hover:bg-[#16a34a] disabled:opacity-70 text-white text-sm font-medium rounded-lg transition-colors"
        >
          {loading ? "Detecting..." : "Run Detection"}
        </button>
      </div>

      {loading && (
        <div className="space-y-3">
          {Array.from({ length: 3 }).map((_, i) => (
            <div key={i} className="bg-white rounded-xl border border-[#e5e7eb] p-6 h-24 animate-pulse" />
          ))}
        </div>
      )}

      {!loading && pairs.length > 0 && (
        <div className="space-y-3">
          {pairs.map((pair, i) => {
            const source = findPoi(pair.source_gid);
            const candidate = findPoi(pair.candidate_gid);
            const isExpanded = expandedGroup === i;

            return (
              <div
                key={`${pair.source_gid}-${pair.candidate_gid}`}
                className="bg-white rounded-xl border border-[#e5e7eb] overflow-hidden"
              >
                {/* Header */}
                <div
                  className="flex items-center justify-between p-4 cursor-pointer hover:bg-[#f9fafb]"
                  onClick={() => setExpandedGroup(isExpanded ? null : i)}
                >
                  <div className="flex items-center gap-4 flex-1 min-w-0">
                    <span className={`px-2 py-0.5 rounded text-xs font-medium ${
                      pair.match_status === "MATCH"
                        ? "bg-red-100 text-red-800"
                        : "bg-amber-100 text-amber-800"
                    }`}>
                      {pair.match_status === "MATCH" ? "Match" : "Possible"}
                    </span>
                    <div className="flex-1 min-w-0">
                      <span className="text-sm font-medium text-[#374151] truncate">
                        {pair.source_name || source?.Name_EN || pair.source_gid}
                      </span>
                      <span className="mx-2 text-[#6b7280]">&harr;</span>
                      <span className="text-sm font-medium text-[#374151] truncate">
                        {pair.candidate_name || candidate?.Name_EN || pair.candidate_gid}
                      </span>
                    </div>
                  </div>
                  <div className="flex items-center gap-3 flex-shrink-0">
                    <span className="text-sm font-bold text-[#374151]">{pair.final_score}%</span>
                    {pair.distance_m > 0 && (
                      <span className="text-xs text-[#6b7280]">{Math.round(pair.distance_m)}m</span>
                    )}
                    <span className="text-[#6b7280]">{isExpanded ? "▾" : "›"}</span>
                  </div>
                </div>

                {/* Expanded detail */}
                {isExpanded && (
                  <div className="border-t border-[#e5e7eb] p-4 bg-[#f9fafb]">
                    {/* Score breakdown */}
                    <div className="grid grid-cols-2 sm:grid-cols-5 gap-3 mb-4">
                      {[
                        { label: "Name", score: pair.name_score },
                        { label: "Phone", score: pair.phone_score },
                        { label: "Distance", score: pair.distance_score },
                        { label: "Category", score: pair.category_score },
                        { label: "Auxiliary", score: pair.auxiliary_score },
                      ].map((s) => (
                        <div key={s.label} className="bg-white rounded-lg border border-[#e5e7eb] p-3 text-center">
                          <p className="text-xs text-[#6b7280] mb-1">{s.label}</p>
                          <p className="text-lg font-bold text-[#374151]">{s.score}</p>
                        </div>
                      ))}
                    </div>

                    {/* Match reasons */}
                    {pair.match_reasons?.length > 0 && (
                      <div className="flex flex-wrap gap-1.5 mb-3">
                        {pair.match_reasons.map((r, j) => (
                          <span key={j} className="px-2 py-0.5 bg-blue-50 text-blue-700 rounded text-xs">
                            {r}
                          </span>
                        ))}
                      </div>
                    )}

                    {/* Side-by-side comparison */}
                    {source && candidate && (
                      <div className="grid grid-cols-2 gap-3">
                        {["Name_EN", "Name_AR", "Category", "Phone_Number", "District_EN"].map((field) => (
                          <div key={field} className="col-span-2 grid grid-cols-3 gap-2 text-xs">
                            <span className="text-[#6b7280]">{field.replace(/_/g, " ")}</span>
                            <span className="text-[#374151]">{String(source[field] ?? "—")}</span>
                            <span className="text-[#374151]">{String(candidate[field] ?? "—")}</span>
                          </div>
                        ))}
                      </div>
                    )}
                  </div>
                )}
              </div>
            );
          })}
        </div>
      )}

      {!loading && groups.length === 0 && pairs.length === 0 && (
        <div className="bg-white rounded-xl border border-[#e5e7eb] p-12 text-center">
          <p className="text-2xl mb-2">🔍</p>
          <p className="text-[#6b7280]">Click &quot;Run Detection&quot; to find duplicate POIs</p>
        </div>
      )}
    </div>
  );
}
