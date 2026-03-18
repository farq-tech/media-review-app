"use client";

import type { POI } from "@/types/poi";
import StatusBadge from "./StatusBadge";
import QAScoreBadge from "./QAScoreBadge";
import { getDecisionState } from "@/lib/validation";
import { MEDIA_DB_FIELDS, MEDIA_COLORS, type MediaType } from "@/lib/constants";

interface POICardProps {
  poi: POI;
  qaScore: number;
  onClick: () => void;
}

function countMedia(poi: POI): number {
  let count = 0;
  for (const [, field] of Object.entries(MEDIA_DB_FIELDS)) {
    const val = (poi as Record<string, unknown>)[field];
    if (val && String(val).trim() && String(val) !== "UNAVAILABLE") {
      count += String(val).split(",").filter((u: string) => u.trim()).length;
    }
  }
  return count;
}

function getMediaTypes(poi: POI): MediaType[] {
  const types: MediaType[] = [];
  for (const [type, field] of Object.entries(MEDIA_DB_FIELDS)) {
    const val = (poi as Record<string, unknown>)[field];
    if (val && String(val).trim() && String(val) !== "UNAVAILABLE") {
      types.push(type as MediaType);
    }
  }
  return types;
}

export default function POICard({ poi, qaScore, onClick }: POICardProps) {
  const status = getDecisionState(poi);
  const mediaCount = countMedia(poi);
  const mediaTypes = getMediaTypes(poi);

  return (
    <div
      onClick={onClick}
      className="bg-white rounded-xl shadow-sm border border-[#e5e7eb] p-4 hover:shadow-md hover:border-[#22c55e]/30 transition-all cursor-pointer"
    >
      {/* Header row */}
      <div className="flex items-start justify-between mb-2">
        <div className="flex-1 min-w-0">
          <h3 className="text-sm font-semibold text-[#374151] truncate">
            {poi.Name_EN || "Unnamed"}
          </h3>
          {poi.Name_AR && (
            <p className="text-xs text-[#6b7280] truncate mt-0.5" dir="rtl">
              {poi.Name_AR}
            </p>
          )}
        </div>
        <div className="flex items-center gap-1.5 ml-2 flex-shrink-0">
          <StatusBadge status={status} />
          <QAScoreBadge score={qaScore} />
        </div>
      </div>

      {/* Details */}
      <div className="flex items-center gap-3 text-xs text-[#6b7280] mb-3">
        {poi.Category && (
          <span className="px-1.5 py-0.5 bg-[#f3f4f6] rounded text-[#374151]">
            {poi.Category}
          </span>
        )}
        {poi.District_EN && <span>{poi.District_EN}</span>}
        {poi.Phone_Number && poi.Phone_Number !== "UNAVAILABLE" && (
          <span>{poi.Phone_Number}</span>
        )}
      </div>

      {/* Media indicators */}
      <div className="flex items-center gap-1.5">
        {mediaTypes.map((type) => (
          <span
            key={type}
            className="px-1.5 py-0.5 rounded text-[10px] font-medium text-white"
            style={{ backgroundColor: MEDIA_COLORS[type] }}
          >
            {type}
          </span>
        ))}
        {mediaCount > 0 && (
          <span className="text-xs text-[#6b7280] ml-1">{mediaCount} files</span>
        )}
        {poi.Flagged === "Yes" && (
          <span className="ml-auto text-xs text-orange-600">
            🚩 {poi.Flag_Reason || "Flagged"}
          </span>
        )}
      </div>
    </div>
  );
}
