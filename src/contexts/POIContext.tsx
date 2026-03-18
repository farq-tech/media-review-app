"use client";

import React, { createContext, useContext, useState, useEffect, useCallback, useMemo } from "react";
import type { POI } from "@/types/poi";
import { fetchPOIs, updatePOI } from "@/api/pois";
import { validatePoi, calcQaScore, type ValidationError } from "@/lib/validation";
import { useAuth } from "./AuthContext";

interface Edits {
  [gid: string]: Record<string, unknown>;
}

interface POIContextType {
  allPois: POI[];
  filteredPois: POI[];
  loading: boolean;
  edits: Edits;
  validationResults: Map<string, ValidationError[]>;

  // Filters
  search: string;
  setSearch: (s: string) => void;
  statusFilter: string;
  setStatusFilter: (s: string) => void;
  categoryFilter: string;
  setCategoryFilter: (s: string) => void;
  dataTab: string;
  setDataTab: (s: string) => void;

  // Pagination
  page: number;
  setPage: (p: number) => void;
  perPage: number;
  setPerPage: (p: number) => void;
  pagedPois: POI[];
  totalPages: number;

  // Actions
  reload: () => Promise<void>;
  editField: (gid: string, field: string, value: unknown) => void;
  saveField: (gid: string, field: string, value: unknown) => Promise<boolean>;
  getEffectiveValue: (poi: POI, field: string) => unknown;
  getQaScore: (poi: POI) => number;
  getValidationErrors: (gid: string) => ValidationError[];

  // Categories
  categories: string[];
}

const POIContext = createContext<POIContextType | undefined>(undefined);

export function POIProvider({ children }: { children: React.ReactNode }) {
  const { user } = useAuth();
  const [allPois, setAllPois] = useState<POI[]>([]);
  const [loading, setLoading] = useState(true);
  const [edits, setEdits] = useState<Edits>({});
  const [validationResults, setValidationResults] = useState<Map<string, ValidationError[]>>(new Map());

  // Filters
  const [search, setSearch] = useState("");
  const [statusFilter, setStatusFilter] = useState("all");
  const [categoryFilter, setCategoryFilter] = useState("all");
  const [dataTab, setDataTab] = useState("all");

  // Pagination
  const [page, setPage] = useState(0);
  const [perPage, setPerPage] = useState(25);

  const reload = useCallback(async () => {
    setLoading(true);
    const data = await fetchPOIs();
    setAllPois(data);
    // Run validation on all POIs
    const results = new Map<string, ValidationError[]>();
    for (const poi of data) {
      if (poi.GlobalID) {
        results.set(poi.GlobalID, validatePoi(poi));
      }
    }
    setValidationResults(results);
    setLoading(false);
  }, []);

  useEffect(() => { reload(); }, [reload]);

  // Filtered list
  const filteredPois = useMemo(() => {
    let list = allPois;

    // Data tab filter
    if (dataTab === "pending") {
      list = list.filter((p) => !p.Review_Status || p.Review_Status === "Draft" || p.Review_Status === "Pending");
    } else if (dataTab === "reviewed") {
      list = list.filter((p) => p.Review_Status === "Reviewed" || p.Review_Status === "Approved");
    } else if (dataTab === "flagged") {
      list = list.filter((p) => p.Flagged === "Yes");
    } else if (dataTab === "rejected") {
      list = list.filter((p) => p.Review_Status === "Rejected");
    }

    // Status filter
    if (statusFilter !== "all") {
      list = list.filter((p) => {
        if (statusFilter === "pending") return !p.Review_Status || p.Review_Status === "Draft";
        if (statusFilter === "reviewed") return p.Review_Status === "Reviewed" || p.Review_Status === "Approved";
        return true;
      });
    }

    // Category filter
    if (categoryFilter !== "all") {
      list = list.filter((p) => p.Category === categoryFilter);
    }

    // Search
    if (search.trim()) {
      const q = search.toLowerCase();
      list = list.filter((p) =>
        (p.Name_EN || "").toLowerCase().includes(q) ||
        (p.Name_AR || "").includes(q) ||
        (p.GlobalID || "").toLowerCase().includes(q) ||
        (p.Phone_Number || "").includes(q) ||
        (p.Category || "").toLowerCase().includes(q)
      );
    }

    return list;
  }, [allPois, search, statusFilter, categoryFilter, dataTab]);

  // Pagination
  const totalPages = Math.ceil(filteredPois.length / perPage);
  const pagedPois = useMemo(
    () => filteredPois.slice(page * perPage, (page + 1) * perPage),
    [filteredPois, page, perPage]
  );

  // Categories
  const categories = useMemo(() => {
    const cats = new Set<string>();
    for (const p of allPois) {
      if (p.Category) cats.add(p.Category);
    }
    return Array.from(cats).sort();
  }, [allPois]);

  // Edit tracking
  const editField = useCallback((gid: string, field: string, value: unknown) => {
    setEdits((prev) => ({
      ...prev,
      [gid]: { ...prev[gid], [field]: value },
    }));
  }, []);

  const saveField = useCallback(async (gid: string, field: string, value: unknown): Promise<boolean> => {
    const ok = await updatePOI(gid, { [field]: value }, user?.username);
    if (ok) {
      setAllPois((prev) =>
        prev.map((p) =>
          p.GlobalID === gid ? { ...p, [field]: value } : p
        )
      );
    }
    return ok;
  }, [user?.username]);

  const getEffectiveValue = useCallback((poi: POI, field: string): unknown => {
    const gid = poi.GlobalID;
    if (edits[gid] && field in edits[gid]) return edits[gid][field];
    return (poi as Record<string, unknown>)[field];
  }, [edits]);

  const getQaScore = useCallback((poi: POI): number => {
    const errors = validationResults.get(poi.GlobalID) || [];
    return calcQaScore(poi, errors);
  }, [validationResults]);

  const getValidationErrors = useCallback((gid: string): ValidationError[] => {
    return validationResults.get(gid) || [];
  }, [validationResults]);

  // Reset page on filter change
  useEffect(() => { setPage(0); }, [search, statusFilter, categoryFilter, dataTab]);

  return (
    <POIContext.Provider
      value={{
        allPois, filteredPois, loading, edits, validationResults,
        search, setSearch, statusFilter, setStatusFilter,
        categoryFilter, setCategoryFilter, dataTab, setDataTab,
        page, setPage, perPage, setPerPage, pagedPois, totalPages,
        reload, editField, saveField, getEffectiveValue, getQaScore, getValidationErrors,
        categories,
      }}
    >
      {children}
    </POIContext.Provider>
  );
}

export function usePOIContext() {
  const ctx = useContext(POIContext);
  if (!ctx) throw new Error("usePOIContext must be used within POIProvider");
  return ctx;
}
