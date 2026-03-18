"use client";

import { useState, useCallback, useMemo } from "react";
import { usePOIContext } from "@/contexts/POIContext";
import { useToast } from "@/components/Toast";
import FilterPanel from "@/components/FilterPanel";
import StatusBadge from "@/components/StatusBadge";
import DetailPanel from "@/components/DetailPanel";
import { getDecisionState } from "@/lib/validation";
import { COL_GROUPS, READONLY_FIELDS, YES_NO_FIELDS, YES_NO_OPTIONS, FIELD_DROPDOWN_OPTIONS } from "@/lib/constants";

type ColGroup = keyof typeof COL_GROUPS;

export default function ExcelPage() {
  const {
    pagedPois, filteredPois, loading, editField, saveField,
    getEffectiveValue, page, setPage, perPage,
  } = usePOIContext();
  const { toast } = useToast();
  const [colGroup, setColGroup] = useState<ColGroup>("key");
  const [selectedIdx, setSelectedIdx] = useState<number | null>(null);
  const [bulkSelected, setBulkSelected] = useState<Set<string>>(new Set());

  const columns = COL_GROUPS[colGroup];
  const selectedPoi = selectedIdx !== null ? filteredPois[selectedIdx] : null;

  const toggleBulkSelect = useCallback((gid: string) => {
    setBulkSelected((prev) => {
      const next = new Set(prev);
      if (next.has(gid)) next.delete(gid);
      else next.add(gid);
      return next;
    });
  }, []);

  const bulkApprove = useCallback(async () => {
    if (bulkSelected.size === 0) return;
    let ok = 0;
    for (const gid of bulkSelected) {
      const success = await saveField(gid, "Review_Status", "Approved");
      if (success) ok++;
    }
    toast(`Approved ${ok} of ${bulkSelected.size} POIs`, "success");
    setBulkSelected(new Set());
  }, [bulkSelected, saveField, toast]);

  const handleCellSave = useCallback(async (gid: string, field: string, value: string) => {
    editField(gid, field, value);
    const ok = await saveField(gid, field, value);
    if (!ok) toast(`Failed to save ${field}`, "error");
  }, [editField, saveField, toast]);

  const handleNav = useCallback((dir: -1 | 1) => {
    if (selectedIdx === null) return;
    const next = selectedIdx + dir;
    if (next >= 0 && next < filteredPois.length) {
      setSelectedIdx(next);
      const targetPage = Math.floor(next / perPage);
      if (targetPage !== page) setPage(targetPage);
    }
  }, [selectedIdx, filteredPois.length, perPage, page, setPage]);

  const colGroupTabs: { key: ColGroup; label: string }[] = [
    { key: "key", label: "Key" },
    { key: "basic", label: "Basic" },
    { key: "contact", label: "Contact" },
    { key: "hours", label: "Hours" },
    { key: "photos", label: "Photos" },
    { key: "amenities", label: "Amenities" },
    { key: "qa", label: "QA" },
  ];

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-[#374151]">Excel View</h1>
          <p className="text-sm text-[#6b7280] mt-0.5">
            {filteredPois.length} POIs &middot; {bulkSelected.size} selected
          </p>
        </div>
        {bulkSelected.size > 0 && (
          <div className="flex gap-2">
            <button
              onClick={bulkApprove}
              className="px-4 py-2 bg-[#22c55e] hover:bg-[#16a34a] text-white text-sm font-medium rounded-lg"
            >
              Approve ({bulkSelected.size})
            </button>
            <button
              onClick={() => setBulkSelected(new Set())}
              className="px-4 py-2 border border-[#d1d5db] rounded-lg text-sm text-[#374151] hover:bg-[#f3f4f6]"
            >
              Clear
            </button>
          </div>
        )}
      </div>

      {/* Column group tabs */}
      <div className="flex gap-1 border-b border-[#e5e7eb]">
        {colGroupTabs.map((tab) => (
          <button
            key={tab.key}
            onClick={() => setColGroup(tab.key)}
            className={`px-3 py-2 text-sm font-medium rounded-t-lg transition-colors ${
              colGroup === tab.key
                ? "bg-[#22c55e] text-white"
                : "text-[#6b7280] hover:bg-[#f3f4f6]"
            }`}
          >
            {tab.label}
          </button>
        ))}
      </div>

      <FilterPanel />

      {/* Table */}
      {loading ? (
        <div className="bg-white rounded-xl border border-[#e5e7eb] p-8 animate-pulse h-64" />
      ) : (
        <div className="bg-white rounded-xl border border-[#e5e7eb] overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="bg-[#f9fafb] border-b border-[#e5e7eb]">
                <th className="px-3 py-2 text-left text-xs font-semibold text-[#6b7280] w-8">
                  <input
                    type="checkbox"
                    checked={bulkSelected.size === pagedPois.length && pagedPois.length > 0}
                    onChange={(e) => {
                      if (e.target.checked) {
                        setBulkSelected(new Set(pagedPois.map((p) => p.GlobalID)));
                      } else {
                        setBulkSelected(new Set());
                      }
                    }}
                  />
                </th>
                <th className="px-3 py-2 text-left text-xs font-semibold text-[#6b7280] w-8">#</th>
                {columns.map((col) => (
                  <th key={col} className="px-3 py-2 text-left text-xs font-semibold text-[#6b7280] whitespace-nowrap">
                    {col.replace(/_/g, " ")}
                  </th>
                ))}
                <th className="px-3 py-2 text-left text-xs font-semibold text-[#6b7280]">Status</th>
              </tr>
            </thead>
            <tbody>
              {pagedPois.map((poi, i) => {
                const globalIdx = page * perPage + i;
                return (
                  <tr
                    key={poi.GlobalID}
                    className={`border-b border-[#e5e7eb] hover:bg-[#f9fafb] ${
                      bulkSelected.has(poi.GlobalID) ? "bg-[#22c55e]/5" : ""
                    }`}
                  >
                    <td className="px-3 py-2">
                      <input
                        type="checkbox"
                        checked={bulkSelected.has(poi.GlobalID)}
                        onChange={() => toggleBulkSelect(poi.GlobalID)}
                      />
                    </td>
                    <td className="px-3 py-2 text-xs text-[#6b7280]">{globalIdx + 1}</td>
                    {columns.map((col) => (
                      <td key={col} className="px-3 py-2">
                        <EditableCell
                          poi={poi}
                          field={col}
                          value={String(getEffectiveValue(poi, col) ?? "")}
                          onSave={(v) => handleCellSave(poi.GlobalID, col, v)}
                          onClick={col === "Name_EN" ? () => setSelectedIdx(globalIdx) : undefined}
                        />
                      </td>
                    ))}
                    <td className="px-3 py-2">
                      <StatusBadge status={getDecisionState(poi)} />
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
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

function EditableCell({
  poi,
  field,
  value,
  onSave,
  onClick,
}: {
  poi: { GlobalID: string };
  field: string;
  value: string;
  onSave: (v: string) => void;
  onClick?: () => void;
}) {
  const isReadonly = READONLY_FIELDS.has(field);
  const [editing, setEditing] = useState(false);
  const [editVal, setEditVal] = useState(value);

  if (isReadonly || field === "GlobalID") {
    return (
      <span
        className={`text-xs text-[#374151] ${onClick ? "text-[#22c55e] cursor-pointer hover:underline font-medium" : ""}`}
        onClick={onClick}
        title={value}
      >
        {value.length > 30 ? value.slice(0, 30) + "..." : value || "—"}
      </span>
    );
  }

  if (YES_NO_FIELDS.has(field)) {
    return (
      <select
        value={value}
        onChange={(e) => onSave(e.target.value)}
        className="px-1 py-0.5 border border-[#d1d5db] rounded text-xs text-[#374151] focus:ring-1 focus:ring-[#22c55e]/50"
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
        value={value}
        onChange={(e) => onSave(e.target.value)}
        className="px-1 py-0.5 border border-[#d1d5db] rounded text-xs text-[#374151] focus:ring-1 focus:ring-[#22c55e]/50"
      >
        <option value="">—</option>
        {FIELD_DROPDOWN_OPTIONS[field].map((opt) => (
          <option key={opt} value={opt}>{opt}</option>
        ))}
      </select>
    );
  }

  if (editing) {
    return (
      <input
        autoFocus
        value={editVal}
        onChange={(e) => setEditVal(e.target.value)}
        onBlur={() => {
          setEditing(false);
          if (editVal !== value) onSave(editVal);
        }}
        onKeyDown={(e) => {
          if (e.key === "Enter") {
            setEditing(false);
            if (editVal !== value) onSave(editVal);
          }
          if (e.key === "Escape") {
            setEditing(false);
            setEditVal(value);
          }
        }}
        className="w-full px-1 py-0.5 border border-[#22c55e] rounded text-xs text-[#374151] focus:outline-none"
        dir={field.includes("_AR") ? "rtl" : undefined}
      />
    );
  }

  return (
    <span
      className={`text-xs text-[#374151] cursor-text hover:bg-[#f3f4f6] px-1 py-0.5 rounded inline-block min-w-[40px] ${
        onClick ? "text-[#22c55e] cursor-pointer hover:underline font-medium" : ""
      }`}
      onClick={onClick || (() => { setEditing(true); setEditVal(value); })}
      title={value}
    >
      {value.length > 30 ? value.slice(0, 30) + "..." : value || "—"}
    </span>
  );
}
