"use client";

import { useState, useMemo } from "react";
import { usePOIContext } from "@/contexts/POIContext";
import { MEDIA_DB_FIELDS, MEDIA_COLORS, type MediaType } from "@/lib/constants";

export default function MediaPage() {
  const { allPois, loading } = usePOIContext();
  const [typeFilter, setTypeFilter] = useState<MediaType | "all">("all");
  const [search, setSearch] = useState("");

  // Build media index
  const mediaItems = useMemo(() => {
    const items: { poi: string; poiName: string; type: MediaType; url: string; field: string }[] = [];
    for (const poi of allPois) {
      for (const [type, field] of Object.entries(MEDIA_DB_FIELDS)) {
        const val = poi[field];
        if (val && typeof val === "string" && val.trim() && val !== "UNAVAILABLE") {
          const urls = val.split(",").filter((u: string) => u.trim());
          for (const url of urls) {
            items.push({
              poi: poi.GlobalID,
              poiName: poi.Name_EN || "Unnamed",
              type: type as MediaType,
              url: url.trim(),
              field,
            });
          }
        }
      }
    }
    return items;
  }, [allPois]);

  const filteredMedia = useMemo(() => {
    let list = mediaItems;
    if (typeFilter !== "all") {
      list = list.filter((m) => m.type === typeFilter);
    }
    if (search.trim()) {
      const q = search.toLowerCase();
      list = list.filter((m) => m.poiName.toLowerCase().includes(q) || m.url.toLowerCase().includes(q));
    }
    return list;
  }, [mediaItems, typeFilter, search]);

  // Counts by type
  const typeCounts = useMemo(() => {
    const counts: Record<string, number> = {};
    for (const m of mediaItems) {
      counts[m.type] = (counts[m.type] || 0) + 1;
    }
    return counts;
  }, [mediaItems]);

  return (
    <div className="space-y-4">
      <div>
        <h1 className="text-2xl font-bold text-[#374151]">Media Gallery</h1>
        <p className="text-sm text-[#6b7280] mt-0.5">
          {mediaItems.length} total media files across {allPois.length} POIs
        </p>
      </div>

      {/* Type filter pills */}
      <div className="flex flex-wrap gap-2">
        <button
          onClick={() => setTypeFilter("all")}
          className={`px-3 py-1.5 rounded-lg text-sm font-medium transition-colors ${
            typeFilter === "all" ? "bg-[#22c55e] text-white" : "bg-[#f3f4f6] text-[#374151] hover:bg-[#e5e7eb]"
          }`}
        >
          All ({mediaItems.length})
        </button>
        {(Object.keys(MEDIA_DB_FIELDS) as MediaType[]).map((type) => (
          <button
            key={type}
            onClick={() => setTypeFilter(type)}
            className={`px-3 py-1.5 rounded-lg text-sm font-medium transition-colors ${
              typeFilter === type ? "text-white" : "text-[#374151] hover:opacity-80"
            }`}
            style={{
              backgroundColor: typeFilter === type ? MEDIA_COLORS[type] : `${MEDIA_COLORS[type]}20`,
              color: typeFilter === type ? "white" : MEDIA_COLORS[type],
            }}
          >
            {type} ({typeCounts[type] || 0})
          </button>
        ))}
      </div>

      {/* Search */}
      <input
        type="text"
        value={search}
        onChange={(e) => setSearch(e.target.value)}
        placeholder="Search by POI name or URL..."
        className="w-full max-w-md px-3 py-2 border border-[#d1d5db] rounded-lg text-sm text-[#374151] focus:outline-none focus:ring-2 focus:ring-[#22c55e]/50"
      />

      {/* Gallery grid */}
      {loading ? (
        <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-4 xl:grid-cols-5 gap-3">
          {Array.from({ length: 10 }).map((_, i) => (
            <div key={i} className="aspect-square bg-[#f3f4f6] rounded-xl animate-pulse" />
          ))}
        </div>
      ) : filteredMedia.length === 0 ? (
        <div className="bg-white rounded-xl border border-[#e5e7eb] p-12 text-center">
          <p className="text-[#6b7280]">No media files found</p>
        </div>
      ) : (
        <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-4 xl:grid-cols-5 gap-3">
          {filteredMedia.slice(0, 100).map((item, i) => (
            <a
              key={`${item.poi}-${item.type}-${i}`}
              href={item.url}
              target="_blank"
              rel="noopener noreferrer"
              className="group relative aspect-square bg-[#f3f4f6] rounded-xl overflow-hidden border border-[#e5e7eb] hover:border-[#22c55e] transition-colors"
            >
              {item.type === "video" ? (
                <div className="w-full h-full flex items-center justify-center text-[#6b7280]">
                  <span className="text-3xl">🎬</span>
                </div>
              ) : (
                // eslint-disable-next-line @next/next/no-img-element
                <img
                  src={item.url}
                  alt={`${item.type} - ${item.poiName}`}
                  className="w-full h-full object-cover"
                  loading="lazy"
                  onError={(e) => {
                    (e.target as HTMLImageElement).style.display = "none";
                  }}
                />
              )}
              {/* Overlay */}
              <div className="absolute bottom-0 left-0 right-0 bg-gradient-to-t from-black/60 to-transparent p-2">
                <span
                  className="inline-flex px-1.5 py-0.5 rounded text-[10px] font-medium text-white"
                  style={{ backgroundColor: MEDIA_COLORS[item.type] }}
                >
                  {item.type}
                </span>
                <p className="text-[10px] text-white/80 truncate mt-0.5">{item.poiName}</p>
              </div>
            </a>
          ))}
        </div>
      )}
      {filteredMedia.length > 100 && (
        <p className="text-sm text-[#6b7280] text-center">Showing 100 of {filteredMedia.length} items</p>
      )}
    </div>
  );
}
