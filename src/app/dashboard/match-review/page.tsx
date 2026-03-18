"use client";

import { useState, useEffect, useCallback, useMemo } from "react";
import { usePOIContext } from "@/contexts/POIContext";
import { useAuth } from "@/contexts/AuthContext";
import { useToast } from "@/components/Toast";
import { detectDuplicates, type DuplicatePair } from "@/api/duplicates";
import { fetchReviewedPairs, submitReview } from "@/api/matchReviews";
import MapView from "@/components/MapView";

export default function MatchReviewPage() {
  const { allPois } = usePOIContext();
  const { user } = useAuth();
  const { toast } = useToast();

  const [pairs, setPairs] = useState<DuplicatePair[]>([]);
  const [verdicts, setVerdicts] = useState<Record<string, string>>({});
  const [currentIdx, setCurrentIdx] = useState(0);
  const [filter, setFilter] = useState<"all" | "unreviewed" | "match" | "not_match">("unreviewed");
  const [loading, setLoading] = useState(false);
  const [notes, setNotes] = useState("");

  // Load pairs and verdicts
  useEffect(() => {
    let cancelled = false;
    const load = async () => {
      setLoading(true);
      const [result, reviewed] = await Promise.all([
        detectDuplicates(),
        fetchReviewedPairs(user?.username),
      ]);
      if (!cancelled) {
        setPairs(result.pairs);
        setVerdicts(reviewed);
        setLoading(false);
      }
    };
    load();
    return () => { cancelled = true; };
  }, [user?.username]);

  // Filter pairs
  const filteredPairs = useMemo(() => {
    return pairs.filter((p) => {
      const key = `${p.source_gid}|${p.candidate_gid}`;
      const verdict = verdicts[key];
      if (filter === "unreviewed") return !verdict;
      if (filter === "match") return verdict === "MATCH";
      if (filter === "not_match") return verdict === "NOT_MATCH";
      return true;
    });
  }, [pairs, verdicts, filter]);

  const currentPair = filteredPairs[currentIdx];

  const handleSubmit = useCallback(async (verdict: "MATCH" | "NOT_MATCH") => {
    if (!currentPair || !user?.username) return;
    const ok = await submitReview({
      source_gid: currentPair.source_gid,
      candidate_gid: currentPair.candidate_gid,
      verdict,
      reviewer: user.username,
      notes,
    });

    if (ok) {
      const key = `${currentPair.source_gid}|${currentPair.candidate_gid}`;
      setVerdicts((prev) => ({ ...prev, [key]: verdict }));
      toast(`Marked as ${verdict}`, "success");
      setNotes("");
      // Auto-advance
      if (currentIdx < filteredPairs.length - 1) setCurrentIdx(currentIdx + 1);
    } else {
      toast("Failed to save verdict", "error");
    }
  }, [currentPair, user, notes, toast, currentIdx, filteredPairs.length]);

  const findPoi = (gid: string) => allPois.find((p) => p.GlobalID === gid);

  const source = currentPair ? findPoi(currentPair.source_gid) : null;
  const candidate = currentPair ? findPoi(currentPair.candidate_gid) : null;

  const mapMarkers = useMemo(() => {
    if (!source || !candidate) return [];
    const markers = [];
    if (source.Latitude && source.Longitude) {
      markers.push({ id: source.GlobalID, lat: Number(source.Latitude), lng: Number(source.Longitude), label: "S: " + (source.Name_EN || "Source"), color: "#3b82f6" });
    }
    if (candidate.Latitude && candidate.Longitude) {
      markers.push({ id: candidate.GlobalID, lat: Number(candidate.Latitude), lng: Number(candidate.Longitude), label: "C: " + (candidate.Name_EN || "Candidate"), color: "#f59e0b" });
    }
    return markers;
  }, [source, candidate]);

  const reviewedCount = Object.keys(verdicts).length;
  const matchCount = Object.values(verdicts).filter((v) => v === "MATCH").length;
  const notMatchCount = Object.values(verdicts).filter((v) => v === "NOT_MATCH").length;

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-[#374151]">Match Review</h1>
          <p className="text-sm text-[#6b7280] mt-0.5">
            {reviewedCount} reviewed &middot; {matchCount} match &middot; {notMatchCount} not match &middot; {pairs.length - reviewedCount} remaining
          </p>
        </div>
      </div>

      {/* Progress bar */}
      {pairs.length > 0 && (
        <div className="bg-[#f3f4f6] rounded-full h-2">
          <div
            className="bg-[#22c55e] h-2 rounded-full transition-all"
            style={{ width: `${(reviewedCount / pairs.length) * 100}%` }}
          />
        </div>
      )}

      {/* Filter tabs */}
      <div className="flex gap-1">
        {(["all", "unreviewed", "match", "not_match"] as const).map((f) => (
          <button
            key={f}
            onClick={() => { setFilter(f); setCurrentIdx(0); }}
            className={`px-3 py-1.5 rounded-lg text-sm font-medium transition-colors ${
              filter === f ? "bg-[#22c55e] text-white" : "text-[#6b7280] hover:bg-[#f3f4f6]"
            }`}
          >
            {f === "all" ? "All" : f === "unreviewed" ? "Unreviewed" : f === "match" ? "Match" : "Not Match"}
          </button>
        ))}
      </div>

      {loading ? (
        <div className="bg-white rounded-xl border border-[#e5e7eb] p-12 animate-pulse h-64" />
      ) : !currentPair ? (
        <div className="bg-white rounded-xl border border-[#e5e7eb] p-12 text-center">
          <p className="text-2xl mb-2">✅</p>
          <p className="text-[#6b7280]">
            {pairs.length === 0 ? "No pairs to review. Run duplicate detection first." : "All pairs in this filter have been reviewed!"}
          </p>
        </div>
      ) : (
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
          {/* Pair list */}
          <div className="bg-white rounded-xl border border-[#e5e7eb] overflow-hidden">
            <div className="max-h-[600px] overflow-y-auto">
              {filteredPairs.map((pair, i) => {
                const key = `${pair.source_gid}|${pair.candidate_gid}`;
                const verdict = verdicts[key];
                return (
                  <div
                    key={key}
                    onClick={() => setCurrentIdx(i)}
                    className={`flex items-center gap-3 px-4 py-3 border-b border-[#e5e7eb] cursor-pointer hover:bg-[#f9fafb] ${
                      i === currentIdx ? "bg-[#22c55e]/5 border-l-2 border-l-[#22c55e]" : ""
                    }`}
                  >
                    <div className="flex-1 min-w-0">
                      <p className="text-xs font-medium text-[#374151] truncate">{pair.source_name}</p>
                      <p className="text-xs text-[#6b7280] truncate">{pair.candidate_name}</p>
                    </div>
                    <span className="text-xs font-bold text-[#374151]">{pair.final_score}%</span>
                    {verdict && (
                      <span className={`px-1.5 py-0.5 rounded text-[10px] font-medium ${
                        verdict === "MATCH" ? "bg-green-100 text-green-800" : "bg-red-100 text-red-800"
                      }`}>
                        {verdict}
                      </span>
                    )}
                  </div>
                );
              })}
            </div>
          </div>

          {/* Detail panel */}
          <div className="space-y-4">
            {/* Score cards */}
            <div className="grid grid-cols-3 gap-2">
              {[
                { label: "Name", score: currentPair.name_score },
                { label: "Distance", score: currentPair.distance_score },
                { label: "Phone", score: currentPair.phone_score },
              ].map((s) => (
                <div key={s.label} className="bg-white rounded-xl border border-[#e5e7eb] p-3 text-center">
                  <p className="text-xs text-[#6b7280]">{s.label}</p>
                  <p className="text-xl font-bold text-[#374151]">{s.score}</p>
                </div>
              ))}
            </div>

            {/* Map */}
            {mapMarkers.length > 0 && (
              <MapView markers={mapMarkers} height="250px" />
            )}

            {/* Comparison */}
            <div className="bg-white rounded-xl border border-[#e5e7eb] p-4">
              <div className="grid grid-cols-3 gap-2 text-xs mb-2">
                <span className="font-semibold text-[#6b7280]">Field</span>
                <span className="font-semibold text-blue-600">Source</span>
                <span className="font-semibold text-amber-600">Candidate</span>
              </div>
              {["Name_EN", "Name_AR", "Category", "Phone_Number", "District_EN", "Working_Hours"].map((field) => (
                <div key={field} className="grid grid-cols-3 gap-2 text-xs py-1 border-t border-[#e5e7eb]">
                  <span className="text-[#6b7280]">{field.replace(/_/g, " ")}</span>
                  <span className="text-[#374151]">{source ? String(source[field] ?? "—") : "—"}</span>
                  <span className="text-[#374151]">{candidate ? String(candidate[field] ?? "—") : "—"}</span>
                </div>
              ))}
            </div>

            {/* Notes + Actions */}
            <div className="bg-white rounded-xl border border-[#e5e7eb] p-4 space-y-3">
              <textarea
                value={notes}
                onChange={(e) => setNotes(e.target.value)}
                placeholder="Optional notes..."
                className="w-full px-3 py-2 border border-[#d1d5db] rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-[#22c55e]/50"
                rows={2}
              />
              <div className="flex gap-2">
                <button
                  onClick={() => handleSubmit("MATCH")}
                  className="flex-1 py-2 bg-green-500 hover:bg-green-600 text-white text-sm font-medium rounded-lg"
                >
                  MATCH
                </button>
                <button
                  onClick={() => handleSubmit("NOT_MATCH")}
                  className="flex-1 py-2 bg-red-500 hover:bg-red-600 text-white text-sm font-medium rounded-lg"
                >
                  NOT MATCH
                </button>
                <button
                  onClick={() => {
                    if (currentIdx < filteredPairs.length - 1) setCurrentIdx(currentIdx + 1);
                  }}
                  className="px-4 py-2 border border-[#d1d5db] rounded-lg text-sm text-[#374151] hover:bg-[#f3f4f6]"
                >
                  Skip
                </button>
              </div>
            </div>

            {/* Navigation */}
            <div className="flex items-center justify-between text-sm text-[#6b7280]">
              <button
                onClick={() => setCurrentIdx(Math.max(0, currentIdx - 1))}
                disabled={currentIdx === 0}
                className="px-3 py-1 border border-[#d1d5db] rounded-lg hover:bg-[#f3f4f6] disabled:opacity-50"
              >
                &larr; Previous
              </button>
              <span>{currentIdx + 1} / {filteredPairs.length}</span>
              <button
                onClick={() => setCurrentIdx(Math.min(filteredPairs.length - 1, currentIdx + 1))}
                disabled={currentIdx >= filteredPairs.length - 1}
                className="px-3 py-1 border border-[#d1d5db] rounded-lg hover:bg-[#f3f4f6] disabled:opacity-50"
              >
                Next &rarr;
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
