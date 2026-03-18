"use client";

import { useState, useCallback } from "react";
import type { POI } from "@/types/poi";
import { usePOIContext } from "@/contexts/POIContext";
import { useAuth } from "@/contexts/AuthContext";
import { useToast } from "./Toast";
import StatusBadge from "./StatusBadge";
import QAScoreBadge from "./QAScoreBadge";
import { getDecisionState } from "@/lib/validation";
import { DETAIL_SECTIONS, READONLY_FIELDS, YES_NO_OPTIONS, FIELD_DROPDOWN_OPTIONS, YES_NO_FIELDS, MEDIA_COLORS } from "@/lib/constants";

interface DetailPanelProps {
  poi: POI;
  onClose: () => void;
  onNav: (dir: -1 | 1) => void;
}

export default function DetailPanel({ poi, onClose, onNav }: DetailPanelProps) {
  const { editField, saveField, getEffectiveValue, getQaScore, getValidationErrors } = usePOIContext();
  const { user } = useAuth();
  const { toast } = useToast();
  const [saving, setSaving] = useState<string | null>(null);
  const [viewMode, setViewMode] = useState<"fields" | "photos">("fields");

  const gid = poi.GlobalID;
  const status = getDecisionState(poi);
  const qaScore = getQaScore(poi);
  const errors = getValidationErrors(gid);

  const handleSave = useCallback(async (field: string, value: unknown) => {
    setSaving(field);
    const ok = await saveField(gid, field, value);
    toast(ok ? `Saved ${field}` : `Failed to save ${field}`, ok ? "success" : "error");
    setSaving(null);
  }, [gid, saveField, toast]);

  const handleApprove = useCallback(async () => {
    await saveField(gid, "Review_Status", "Approved");
    if (user?.username) await saveField(gid, "last_reviewed_by", user.username);
    toast("POI approved", "success");
  }, [gid, saveField, user, toast]);

  const handleReject = useCallback(async () => {
    await saveField(gid, "Review_Status", "Rejected");
    toast("POI rejected", "info");
  }, [gid, saveField, toast]);

  const renderFieldValue = (field: string) => {
    const value = getEffectiveValue(poi, field);
    const strVal = value != null ? String(value) : "";
    const isReadonly = READONLY_FIELDS.has(field);
    const isSaving = saving === field;

    // Media URL fields - show as thumbnails
    if (field.includes("Photo_URL") || field === "Video_URL" || field === "Additional_Photo_URLs") {
      const urls = strVal.split(",").filter((u) => u.trim());
      if (urls.length === 0) return <span className="text-[#94a3b8] text-xs">Empty</span>;
      const mediaType = field.replace("_Photo_URL", "").replace("_URL", "").replace("Additional_Photo_URLs", "additional").toLowerCase();
      const color = MEDIA_COLORS[mediaType as keyof typeof MEDIA_COLORS] || "#6b7280";
      return (
        <div className="flex flex-wrap gap-1.5">
          {urls.map((url, i) => (
            <a
              key={i}
              href={url.trim()}
              target="_blank"
              rel="noopener noreferrer"
              className="inline-flex items-center px-2 py-0.5 rounded text-[10px] font-medium text-white hover:opacity-80"
              style={{ backgroundColor: color }}
            >
              {mediaType} {urls.length > 1 ? i + 1 : ""}
            </a>
          ))}
        </div>
      );
    }

    if (isReadonly) {
      return <span className="text-sm text-[#374151]">{strVal || <span className="text-[#94a3b8]">—</span>}</span>;
    }

    // Dropdown fields
    if (YES_NO_FIELDS.has(field)) {
      return (
        <select
          value={strVal}
          onChange={(e) => {
            editField(gid, field, e.target.value);
            handleSave(field, e.target.value);
          }}
          disabled={isSaving}
          className="px-2 py-1 border border-[#d1d5db] rounded-lg text-sm text-[#374151] focus:outline-none focus:ring-1 focus:ring-[#22c55e]/50"
        >
          <option value="">—</option>
          {YES_NO_OPTIONS.map((opt) => (
            <option key={opt} value={opt}>{opt}</option>
          ))}
        </select>
      );
    }

    if (FIELD_DROPDOWN_OPTIONS[field]) {
      return (
        <select
          value={strVal}
          onChange={(e) => {
            editField(gid, field, e.target.value);
            handleSave(field, e.target.value);
          }}
          disabled={isSaving}
          className="px-2 py-1 border border-[#d1d5db] rounded-lg text-sm text-[#374151] focus:outline-none focus:ring-1 focus:ring-[#22c55e]/50"
        >
          <option value="">—</option>
          {FIELD_DROPDOWN_OPTIONS[field].map((opt) => (
            <option key={opt} value={opt}>{opt}</option>
          ))}
        </select>
      );
    }

    // Text input
    return (
      <input
        type="text"
        value={strVal}
        onChange={(e) => editField(gid, field, e.target.value)}
        onBlur={(e) => {
          if (e.target.value !== String((poi as Record<string, unknown>)[field] ?? "")) {
            handleSave(field, e.target.value);
          }
        }}
        disabled={isSaving}
        className="w-full px-2 py-1 border border-[#d1d5db] rounded-lg text-sm text-[#374151] focus:outline-none focus:ring-1 focus:ring-[#22c55e]/50 disabled:opacity-50"
        dir={field.includes("_AR") ? "rtl" : undefined}
      />
    );
  };

  return (
    <div className="fixed inset-0 z-50 flex">
      {/* Backdrop */}
      <div className="flex-1 bg-black/30" onClick={onClose} />

      {/* Panel */}
      <div className="w-[58%] min-w-[480px] max-w-[900px] bg-white shadow-xl overflow-y-auto animate-slide-in">
        {/* Sticky header */}
        <div className="sticky top-0 bg-white border-b border-[#e5e7eb] p-4 z-10">
          <div className="flex items-center justify-between mb-2">
            <div className="flex items-center gap-2">
              <button onClick={onClose} className="text-[#6b7280] hover:text-[#374151] text-lg">&times;</button>
              <h2 className="text-lg font-bold text-[#374151] truncate">{poi.Name_EN || "Unnamed"}</h2>
            </div>
            <div className="flex items-center gap-2">
              <button onClick={() => onNav(-1)} className="px-2 py-1 border border-[#d1d5db] rounded-lg text-sm hover:bg-[#f3f4f6]">&larr;</button>
              <button onClick={() => onNav(1)} className="px-2 py-1 border border-[#d1d5db] rounded-lg text-sm hover:bg-[#f3f4f6]">&rarr;</button>
            </div>
          </div>
          <div className="flex items-center gap-2 flex-wrap">
            <StatusBadge status={status} />
            <QAScoreBadge score={qaScore} />
            {poi.Name_AR && (
              <span className="text-xs text-[#6b7280]" dir="rtl">{poi.Name_AR}</span>
            )}
            {errors.length > 0 && (
              <span className="text-xs text-red-600">{errors.filter((e) => e.severity === "BLOCKER").length} blockers</span>
            )}
          </div>
          {/* Action buttons */}
          <div className="flex gap-2 mt-3">
            <button
              onClick={handleApprove}
              className="px-4 py-1.5 bg-[#22c55e] hover:bg-[#16a34a] text-white text-sm font-medium rounded-lg transition-colors"
            >
              Approve
            </button>
            <button
              onClick={handleReject}
              className="px-4 py-1.5 bg-red-500 hover:bg-red-600 text-white text-sm font-medium rounded-lg transition-colors"
            >
              Reject
            </button>
            <div className="flex ml-auto border border-[#e5e7eb] rounded-lg overflow-hidden">
              <button
                onClick={() => setViewMode("fields")}
                className={`px-3 py-1.5 text-sm font-medium ${viewMode === "fields" ? "bg-[#22c55e] text-white" : "text-[#374151] hover:bg-[#f3f4f6]"}`}
              >
                Fields
              </button>
              <button
                onClick={() => setViewMode("photos")}
                className={`px-3 py-1.5 text-sm font-medium ${viewMode === "photos" ? "bg-[#22c55e] text-white" : "text-[#374151] hover:bg-[#f3f4f6]"}`}
              >
                Photos
              </button>
            </div>
          </div>
        </div>

        {/* Body */}
        <div className="p-4 space-y-4">
          {viewMode === "fields" ? (
            DETAIL_SECTIONS.map((section) => (
              <div key={section.title} className="border border-[#e5e7eb] rounded-xl overflow-hidden">
                <div className="bg-[#f9fafb] px-4 py-2 border-b border-[#e5e7eb]">
                  <h3 className="text-xs font-semibold text-[#6b7280] uppercase tracking-wider">{section.title}</h3>
                </div>
                <div className="divide-y divide-[#e5e7eb]">
                  {section.fields.map((field) => {
                    const fieldError = errors.find((e) => e.field === field);
                    return (
                      <div
                        key={field}
                        className={`flex items-center px-4 py-2 gap-4 ${fieldError ? (fieldError.severity === "BLOCKER" ? "bg-red-50/50" : "bg-amber-50/50") : ""}`}
                      >
                        <span className="text-xs text-[#6b7280] w-40 flex-shrink-0 truncate" title={field}>
                          {field.replace(/_/g, " ")}
                        </span>
                        <div className="flex-1 min-w-0">{renderFieldValue(field)}</div>
                        {fieldError && (
                          <span className={`text-[10px] flex-shrink-0 ${fieldError.severity === "BLOCKER" ? "text-red-600" : "text-amber-600"}`}>
                            {fieldError.message}
                          </span>
                        )}
                      </div>
                    );
                  })}
                </div>
              </div>
            ))
          ) : (
            <PhotosView poi={poi} />
          )}
        </div>
      </div>
    </div>
  );
}

function PhotosView({ poi }: { poi: POI }) {
  const mediaFields = [
    { label: "Exterior", field: "Exterior_Photo_URL", color: "#f59e0b" },
    { label: "Interior", field: "Interior_Photo_URL", color: "#8b5cf6" },
    { label: "Menu", field: "Menu_Photo_URL", color: "#f97316" },
    { label: "Video", field: "Video_URL", color: "#ec4899" },
    { label: "License", field: "License_Photo_URL", color: "#14b8a6" },
    { label: "Additional", field: "Additional_Photo_URLs", color: "#78909c" },
  ];

  return (
    <div className="space-y-4">
      {mediaFields.map(({ label, field, color }) => {
        const val = (poi as Record<string, unknown>)[field];
        const urls = val ? String(val).split(",").filter((u: string) => u.trim()) : [];
        if (urls.length === 0) return null;
        return (
          <div key={field}>
            <h4 className="text-sm font-medium mb-2" style={{ color }}>
              {label} ({urls.length})
            </h4>
            <div className="grid grid-cols-2 sm:grid-cols-3 gap-2">
              {urls.map((url, i) => (
                <a
                  key={i}
                  href={url.trim()}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="block aspect-video bg-[#f3f4f6] rounded-lg overflow-hidden border border-[#e5e7eb] hover:border-[#22c55e] transition-colors"
                >
                  {field === "Video_URL" ? (
                    <div className="w-full h-full flex items-center justify-center text-[#6b7280] text-sm">
                      🎬 Video {i + 1}
                    </div>
                  ) : (
                    // eslint-disable-next-line @next/next/no-img-element
                    <img
                      src={url.trim()}
                      alt={`${label} ${i + 1}`}
                      className="w-full h-full object-cover"
                      loading="lazy"
                      onError={(e) => {
                        (e.target as HTMLImageElement).style.display = "none";
                      }}
                    />
                  )}
                </a>
              ))}
            </div>
          </div>
        );
      })}
    </div>
  );
}
