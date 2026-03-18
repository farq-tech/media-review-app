export interface POI {
  [key: string]: unknown;
  GlobalID: string;
  OBJECTID?: number;
  Name_EN: string;
  Name_AR?: string;
  Category?: string;
  Subcategory?: string;
  Level_3?: string;
  Phone_Number?: string;
  Email?: string;
  Website?: string;
  Google_Map_URL?: string;
  Latitude?: number;
  Longitude?: number;
  Region?: string;
  City?: string;
  District?: string;
  District_EN?: string;
  District_AR?: string;
  Street?: string;
  Building_Number?: string;
  Floor?: string;
  Postal_Code?: string;
  Description_EN?: string;
  Description_AR?: string;
  Operating_Hours?: string;
  Menu?: string;
  Cuisine?: string;
  Dine_In?: string;
  Drive_Thru?: string;
  Delivery?: string;
  WiFi?: string;
  Wheelchair_Accessible?: string;
  Parking?: string;
  Outdoor_Seating?: string;
  Exterior_Photo_URL?: string;
  Interior_Photo_URL?: string;
  Menu_Photo_URL?: string;
  Video_URL?: string;
  License_Photo_URL?: string;
  Additional_Photo_URLs?: string;
  Source?: string;
  Confidence?: string;
  QA_Score?: number;
  Review_Status?: string;
  Review_Notes?: string;
  Flagged?: string;
  Flag_Reason?: string;
  last_reviewed_by?: string;
  last_reviewed_at?: string;
  updated_at?: string;
  created_at?: string;

  // Availability fields
  Exterior_Photo_Availability?: string;
  Interior_Photo_Availability?: string;
  Menu_Photo_Availability?: string;
  Video_Availability?: string;
  License_Photo_Availability?: string;

  // Computed fields
  _editedFields?: string[];
  _mergedInto?: string;
}

export type DecisionState = "Draft" | "Reviewed" | "Rejected" | "Archived" | "Flagged";

export interface ValidationError {
  field: string;
  message: string;
  severity: "BLOCKER" | "WARNING" | "INFO";
  fixValue?: string;
}

export interface DuplicateGroup {
  golden_index: number;
  members: DuplicateMember[];
}

export interface DuplicateMember {
  poi: POI;
  final_score: number;
  name_score: number;
  phone_score: number;
  distance_score: number;
  category_score: number;
  auxiliary_score: number;
  match_reasons: string[];
  distance_m: number;
  match_status: "MATCH" | "POSSIBLE_MATCH";
}

export interface MatchReviewPair {
  source: POI;
  candidate: POI;
  scores: {
    final_score: number;
    name_score: number;
    phone_score: number;
    distance_score: number;
    category_score: number;
    auxiliary_score: number;
  };
  match_reasons: string[];
  distance_m: number;
  verdict?: "MATCH" | "NOT_MATCH";
  reviewer?: string;
  notes?: string;
}

export interface SyncUpdate {
  id: number;
  global_id: string;
  poi_name: string;
  source: string;
  action: string;
  created_at: string;
  acknowledged: boolean;
  changed_fields: Record<string, unknown>;
}

export const MEDIA_TYPES = ["exterior", "interior", "menu", "video", "license", "additional"] as const;
export type MediaType = (typeof MEDIA_TYPES)[number];

export const MEDIA_DB_FIELDS: Record<MediaType, string> = {
  exterior: "Exterior_Photo_URL",
  interior: "Interior_Photo_URL",
  menu: "Menu_Photo_URL",
  video: "Video_URL",
  license: "License_Photo_URL",
  additional: "Additional_Photo_URLs",
};

export const MEDIA_COLORS: Record<MediaType, string> = {
  exterior: "#f59e0b",
  interior: "#8b5cf6",
  menu: "#f97316",
  video: "#ec4899",
  license: "#14b8a6",
  additional: "#78909c",
};
