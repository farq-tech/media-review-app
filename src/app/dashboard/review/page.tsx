"use client";

import { useState, useCallback } from "react";
import { usePOIContext } from "@/contexts/POIContext";
import FilterPanel from "@/components/FilterPanel";
import POICard from "@/components/POICard";
import DetailPanel from "@/components/DetailPanel";

export default function ReviewPage() {
  const {
    pagedPois, filteredPois, loading, getQaScore,
    page, setPage, perPage, dataTab, setDataTab,
  } = usePOIContext();
  const [selectedIdx, setSelectedIdx] = useState<number | null>(null);

  const selectedPoi = selectedIdx !== null ? filteredPois[selectedIdx] : null;

  const handleCardClick = useCallback((globalIdx: number) => {
    setSelectedIdx(globalIdx);
  }, []);

  const handleNav = useCallback((dir: -1 | 1) => {
    if (selectedIdx === null) return;
    const next = selectedIdx + dir;
    if (next >= 0 && next < filteredPois.length) {
      setSelectedIdx(next);
      const targetPage = Math.floor(next / perPage);
      if (targetPage !== page) setPage(targetPage);
    }
  }, [selectedIdx, filteredPois.length, perPage, page, setPage]);

  const tabs = [
    { key: "all", label: "All" },
    { key: "pending", label: "Pending" },
    { key: "reviewed", label: "Reviewed" },
    { key: "flagged", label: "Flagged" },
    { key: "rejected", label: "Rejected" },
  ];

  return (
    <div className="space-y-4">
      <div>
        <h1 className="text-2xl font-bold text-[#374151]">Review Queue</h1>
        <p className="text-sm text-[#6b7280] mt-0.5">
          {filteredPois.length} POIs to review
        </p>
      </div>

      {/* Data tabs */}
      <div className="flex gap-1 border-b border-[#e5e7eb] pb-0">
        {tabs.map((tab) => (
          <button
            key={tab.key}
            onClick={() => setDataTab(tab.key)}
            className={`px-4 py-2 text-sm font-medium rounded-t-lg transition-colors ${
              dataTab === tab.key
                ? "bg-[#22c55e] text-white"
                : "text-[#6b7280] hover:bg-[#f3f4f6] hover:text-[#374151]"
            }`}
          >
            {tab.label}
          </button>
        ))}
      </div>

      <FilterPanel />

      {loading ? (
        <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-3">
          {Array.from({ length: 6 }).map((_, i) => (
            <div key={i} className="bg-white rounded-xl border border-[#e5e7eb] p-4 h-32 animate-pulse" />
          ))}
        </div>
      ) : pagedPois.length === 0 ? (
        <div className="bg-white rounded-xl border border-[#e5e7eb] p-12 text-center">
          <p className="text-[#6b7280]">No POIs match your filters</p>
        </div>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-3">
          {pagedPois.map((poi, i) => {
            const globalIdx = page * perPage + i;
            return (
              <POICard
                key={poi.GlobalID}
                poi={poi}
                qaScore={getQaScore(poi)}
                onClick={() => handleCardClick(globalIdx)}
              />
            );
          })}
        </div>
      )}

      {selectedPoi && (
        <DetailPanel
          poi={selectedPoi}
          onClose={() => setSelectedIdx(null)}
          onNav={handleNav}
        />
      )}
    </div>
  );
}
