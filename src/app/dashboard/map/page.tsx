"use client";

import { useState, useMemo, useCallback } from "react";
import { usePOIContext } from "@/contexts/POIContext";
import MapView from "@/components/MapView";
import type { MapMarker } from "@/components/MapView";
import DetailPanel from "@/components/DetailPanel";
import FilterPanel from "@/components/FilterPanel";

export default function MapPage() {
  const { filteredPois, loading, page, setPage, perPage } = usePOIContext();
  const [selectedIdx, setSelectedIdx] = useState<number | null>(null);

  const markers: MapMarker[] = useMemo(() => {
    return filteredPois
      .filter((p) => p.Latitude && p.Longitude && !isNaN(Number(p.Latitude)) && !isNaN(Number(p.Longitude)))
      .map((p, i) => ({
        id: p.GlobalID,
        lat: Number(p.Latitude),
        lng: Number(p.Longitude),
        label: p.Name_EN || "Unnamed",
        sublabel: [p.Category, p.District_EN].filter(Boolean).join(" · "),
      }));
  }, [filteredPois]);

  const handleMarkerClick = useCallback((id: string) => {
    const idx = filteredPois.findIndex((p) => p.GlobalID === id);
    if (idx !== -1) setSelectedIdx(idx);
  }, [filteredPois]);

  const handleNav = useCallback((dir: -1 | 1) => {
    if (selectedIdx === null) return;
    const next = selectedIdx + dir;
    if (next >= 0 && next < filteredPois.length) {
      setSelectedIdx(next);
      const targetPage = Math.floor(next / perPage);
      if (targetPage !== page) setPage(targetPage);
    }
  }, [selectedIdx, filteredPois.length, perPage, page, setPage]);

  const selectedPoi = selectedIdx !== null ? filteredPois[selectedIdx] : null;

  return (
    <div className="space-y-4">
      <div>
        <h1 className="text-2xl font-bold text-[#374151]">Map View</h1>
        <p className="text-sm text-[#6b7280] mt-0.5">
          {markers.length} POIs with coordinates
        </p>
      </div>

      <FilterPanel />

      {loading ? (
        <div className="bg-[#f3f4f6] rounded-xl animate-pulse" style={{ height: "560px" }} />
      ) : (
        <MapView
          markers={markers}
          height="560px"
          onMarkerClick={handleMarkerClick}
        />
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
