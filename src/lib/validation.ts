import type { POI } from "@/types/poi";
import { FNB_CATEGORIES, FNB_ONLY_FIELDS } from "./constants";

export interface ValidationError {
  code: string;
  field: string;
  message: string;
  severity: "BLOCKER" | "WARNING" | "INFO";
  fixValue?: string;
}

/**
 * Validate a POI against all gate rules. Returns an array of errors.
 */
export function validatePoi(poi: POI): ValidationError[] {
  const errors: ValidationError[] = [];
  const v = (field: string) => {
    const val = (poi as Record<string, unknown>)[field];
    if (val === undefined || val === null || val === "") return "";
    return String(val).trim();
  };

  // N1: Name_AR required
  if (!v("Name_AR") || v("Name_AR").length < 2) {
    errors.push({ code: "N1", field: "Name_AR", message: "Arabic name is missing or too short", severity: "BLOCKER" });
  }
  // N2: Name_EN required
  if (!v("Name_EN") || v("Name_EN").length < 2) {
    errors.push({ code: "N2", field: "Name_EN", message: "English name is missing or too short", severity: "BLOCKER" });
  }
  // M5: Category required
  if (!v("Category")) {
    errors.push({ code: "M5", field: "Category", message: "Category is empty", severity: "BLOCKER" });
  }
  // M6: District required
  if (!v("District_EN")) {
    errors.push({ code: "M6", field: "District_EN", message: "District (EN) is empty", severity: "BLOCKER" });
  }
  // D1: District_AR required
  if (!v("District_AR")) {
    errors.push({ code: "D1", field: "District_AR", message: "District (AR) is empty", severity: "WARNING" });
  }

  // Location checks
  const lat = Number(poi.Latitude);
  const lng = Number(poi.Longitude);
  if (!isNaN(lat) && !isNaN(lng)) {
    // L1: Coordinates are 0,0
    if (lat === 0 && lng === 0) {
      errors.push({ code: "L1", field: "Latitude", message: "Coordinates are 0,0", severity: "BLOCKER" });
    }
    // M3: Latitude out of Saudi bounds
    if (lat < 15 || lat > 35) {
      errors.push({ code: "M3", field: "Latitude", message: "Latitude outside Saudi Arabia bounds (15-35)", severity: "BLOCKER" });
    }
    // M4: Longitude out of Saudi bounds
    if (lng < 35 || lng > 60) {
      errors.push({ code: "M4", field: "Longitude", message: "Longitude outside Saudi Arabia bounds (35-60)", severity: "BLOCKER" });
    }
  } else {
    errors.push({ code: "M3", field: "Latitude", message: "Missing coordinates", severity: "BLOCKER" });
  }

  // M7: Working_Hours required
  if (!v("Working_Hours")) {
    errors.push({ code: "M7", field: "Working_Hours", message: "Working hours missing", severity: "WARNING" });
  }
  // H1: Working_Days required
  if (!v("Working_Days")) {
    errors.push({ code: "H1", field: "Working_Days", message: "Working days missing", severity: "WARNING" });
  }

  // V1: Exterior and interior photos identical
  if (v("Exterior_Photo_URL") && v("Interior_Photo_URL") && v("Exterior_Photo_URL") === v("Interior_Photo_URL")) {
    errors.push({ code: "V1", field: "Interior_Photo_URL", message: "Exterior and interior photos are identical", severity: "WARNING" });
  }

  // Phone format
  const phone = v("Phone_Number");
  if (phone && phone !== "UNAVAILABLE") {
    const cleaned = phone.replace(/[\s\-()]/g, "");
    if (!/^(\+?\d{7,15}|UNAVAILABLE|UNAPPLICABLE)$/i.test(cleaned)) {
      errors.push({ code: "P1", field: "Phone_Number", message: "Invalid phone number format", severity: "WARNING" });
    }
  }

  // Email format
  const email = v("Email");
  if (email && email !== "UNAVAILABLE" && email !== "UNAPPLICABLE") {
    if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email)) {
      errors.push({ code: "E1", field: "Email", message: "Invalid email format", severity: "WARNING" });
    }
  }

  // URL format
  for (const field of ["Website"]) {
    const url = v(field);
    if (url && url !== "UNAVAILABLE" && url !== "UNAPPLICABLE") {
      if (!/^https?:\/\/.+/i.test(url)) {
        errors.push({ code: "U1", field, message: `Invalid URL format in ${field}`, severity: "WARNING" });
      }
    }
  }

  // FNB field locking
  const cat = v("Category");
  const isFnb = FNB_CATEGORIES.has(cat);
  if (!isFnb) {
    for (const field of FNB_ONLY_FIELDS) {
      const val = v(field);
      if (val && val !== "UNAPPLICABLE" && val !== "UNAVAILABLE" && val !== "No") {
        errors.push({
          code: "FNB",
          field,
          message: `${field} should be UNAPPLICABLE for non-F&B category`,
          severity: "INFO",
          fixValue: "UNAPPLICABLE",
        });
      }
    }
  }

  return errors;
}

/**
 * Calculate QA score (0-100) based on completeness and validation.
 */
export function calcQaScore(poi: POI, errors: ValidationError[]): number {
  const fields = [
    "Name_AR", "Name_EN", "Category", "Subcategory", "District_EN", "District_AR",
    "Latitude", "Longitude", "Phone_Number", "Working_Hours", "Working_Days",
    "Exterior_Photo_URL", "Interior_Photo_URL",
  ];

  let filled = 0;
  for (const f of fields) {
    const val = (poi as Record<string, unknown>)[f];
    if (val && String(val).trim() && String(val).trim() !== "UNAVAILABLE") filled++;
  }
  const completeness = (filled / fields.length) * 100;

  const blockers = errors.filter((e) => e.severity === "BLOCKER").length;
  const warnings = errors.filter((e) => e.severity === "WARNING").length;
  const penalty = blockers * 15 + warnings * 5;

  return Math.max(0, Math.min(100, Math.round(completeness - penalty)));
}

/**
 * Get decision state from POI fields.
 */
export function getDecisionState(poi: POI): string {
  if (poi.Review_Status === "Rejected") return "Rejected";
  if (poi.Review_Status === "Archived") return "Archived";
  if (poi.Flagged === "Yes") return "Flagged";
  if (poi.Review_Status === "Reviewed" || poi.Review_Status === "Approved") return "Reviewed";
  return "Draft";
}
