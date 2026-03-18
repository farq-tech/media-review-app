/* ═══════════ FIELD GROUPS ═══════════ */
export const COL_GROUPS = {
  key: ["GlobalID", "Name_AR", "Name_EN", "Category", "District_EN", "Phone_Number", "QA_Score", "Review_Status", "Review_Flag"],
  basic: ["GlobalID", "Name_AR", "Name_EN", "Legal_Name", "Category", "Subcategory", "Category_Level_3", "Company_Status", "Latitude", "Longitude", "Google_Map_URL", "District_AR", "District_EN", "Building_Number", "Floor_Number", "Entrance_Location"],
  contact: ["GlobalID", "Name_EN", "Phone_Number", "Email", "Website", "Social_Media", "Menu_Barcode_URL", "Language", "Cuisine", "Payment_Methods", "Commercial_License"],
  hours: ["GlobalID", "Name_EN", "Working_Days", "Working_Hours", "Break_Time", "Holidays"],
  photos: ["GlobalID", "Name_EN", "Exterior_Photo_URL", "Interior_Photo_URL", "Menu_Photo_URL", "Video_URL", "License_Photo_URL", "Additional_Photo_URLs", "Num_Menu_Photos", "Num_Additional_Photos"],
  amenities: ["GlobalID", "Name_EN", "Amenities", "Menu", "Drive_Thru", "Dine_In", "Only_Delivery", "Reservation", "Require_Ticket", "Order_from_Car", "Pickup_Point", "WiFi", "Music", "Valet_Parking", "Has_Parking_Lot", "Wheelchair_Accessible", "Family_Seating", "Waiting_Area", "Private_Dining", "Smoking_Area", "Children_Area", "Shisha", "Live_Sports", "Is_Landmark", "Is_Trending", "Large_Groups", "Women_Prayer_Room", "Iftar_Tent", "Iftar_Menu", "Open_Suhoor", "Free_Entry"],
  qa: ["GlobalID", "Name_EN", "Confidence", "Source", "All_Sources", "Importance_Score", "QA_Score", "Review_Flag", "Review_Notes", "Review_Status", "flagged", "flag_reason", "draft_reason", "last_reviewed_at", "last_reviewed_by", "review_version"],
};

export const DETAIL_SECTIONS = [
  { title: "IDENTITY", fields: ["GlobalID", "Name_AR", "Name_EN", "Legal_Name", "Category", "Subcategory", "Category_Level_3", "Company_Status"] },
  { title: "LOCATION", fields: ["Latitude", "Longitude", "Google_Map_URL", "District_AR", "District_EN", "Building_Number", "Floor_Number", "Entrance_Location"] },
  { title: "CONTACT", fields: ["Phone_Number", "Email", "Website", "Social_Media", "Menu_Barcode_URL", "Language", "Cuisine", "Payment_Methods", "Commercial_License"] },
  { title: "WORKING HOURS", fields: ["Working_Days", "Working_Hours", "Break_Time", "Holidays"] },
  { title: "MEDIA", fields: ["Exterior_Photo_URL", "Interior_Photo_URL", "Menu_Photo_URL", "Video_URL", "License_Photo_URL", "Additional_Photo_URLs", "Num_Menu_Photos", "Num_Additional_Photos"] },
  { title: "AMENITIES & SERVICES", fields: ["Amenities", "Menu", "Drive_Thru", "Dine_In", "Only_Delivery", "Reservation", "Require_Ticket", "Order_from_Car", "Pickup_Point", "WiFi", "Music", "Valet_Parking", "Has_Parking_Lot", "Wheelchair_Accessible", "Family_Seating", "Waiting_Area", "Private_Dining", "Smoking_Area", "Children_Area", "Shisha", "Live_Sports", "Is_Landmark", "Is_Trending", "Large_Groups", "Women_Prayer_Room", "Iftar_Tent", "Iftar_Menu", "Open_Suhoor", "Free_Entry"] },
  { title: "QA & REVIEW", fields: ["Confidence", "Source", "All_Sources", "Importance_Score", "QA_Score", "Review_Flag", "Review_Notes", "Review_Status", "flagged", "flag_reason", "draft_reason", "archived_reason", "rejected_reason", "last_reviewed_at", "last_reviewed_by", "review_version"] },
];

/* ═══════════ READONLY & SPECIAL FIELDS ═══════════ */
export const READONLY_FIELDS = new Set([
  "GlobalID", "Google_Map_URL", "Confidence", "Source", "All_Sources",
  "Importance_Score", "QA_Score", "Num_Menu_Photos", "Num_Additional_Photos",
  "flagged", "flag_reason", "draft_reason", "archived_reason", "rejected_reason",
  "last_reviewed_at", "last_reviewed_by", "review_version",
]);

export const FNB_CATEGORIES = new Set([
  "Restaurants", "Food and Beverages", "Coffee Shops",
  "Food & Beverage", "Restaurant", "Cafe", "Cafes", "Coffee Shop",
  "Bakery", "Fast Food", "Fine Dining", "Catering", "Food Truck", "Juice Bar",
  "Ice Cream", "Dessert", "Buffet",
]);

export const FNB_ONLY_FIELDS = [
  "Menu", "Dine_In", "Only_Delivery", "Cuisine", "Menu_Barcode_URL", "Menu_Photo_URL",
  "Reservation", "Iftar_Tent", "Iftar_Menu", "Open_Suhoor", "Shisha",
];

/* ═══════════ DROPDOWN OPTIONS ═══════════ */
export const YES_NO_OPTIONS = ["Yes", "No", "UNAVAILABLE", "UNAPPLICABLE"];

export const FIELD_DROPDOWN_OPTIONS: Record<string, string[]> = {
  Working_Days: ["Daily", "Sun, Mon, Tue, Wed, Thu, Fri, Sat", "Sun, Mon, Tue, Wed, Thu", "Sun, Mon, Tue, Wed, Thu, Sat", "Sun, Mon, Tue, Wed, Thu, Fri", "Mon, Tue, Wed, Thu, Fri", "UNAVAILABLE"],
  Working_Hours: ["06:00 - 22:00", "06:00 - 00:00", "07:00 - 23:00", "08:00 - 22:00", "08:00 - 23:00", "08:00 - 00:00", "09:00 - 17:00", "09:00 - 21:00", "09:00 - 22:00", "09:00 - 23:00", "09:00 - 00:00", "10:00 - 22:00", "10:00 - 23:00", "10:00 - 00:00", "12:00 - 00:00", "16:00 - 00:00", "16:00 - 02:00", "Open 24 Hours", "UNAVAILABLE"],
  Break_Time: ["No Break", "12:00 - 13:00", "12:30 - 13:30", "13:00 - 14:00", "13:00 - 16:00", "14:00 - 16:00", "15:00 - 17:00", "UNAVAILABLE", "UNAPPLICABLE"],
  Holidays: ["No Holidays", "Friday", "Friday & Saturday", "Saturday", "National Holidays Only", "Ramadan Hours", "UNAVAILABLE"],
  Payment_Methods: ["Cash, Mada, Visa, Mastercard, Apple Pay", "Cash, Mada, Visa, Mastercard", "Mada, Visa, Mastercard, Apple Pay", "Cash, Mada, Visa, Apple Pay", "Cash, Mada, Mastercard, Apple Pay", "Cash, Mada, Visa, Mastercard, Apple Pay, STC Pay", "Cash, Mada, Visa", "Cash, Mada", "Mada, Visa, Mastercard", "Mada, Apple Pay", "Cash", "Apple Pay", "UNAVAILABLE"],
  Language: ["Arabic", "English", "Arabic, English", "Arabic, English, Urdu", "Arabic, English, Filipino", "Arabic, English, Hindi", "Arabic, English, French", "UNAVAILABLE"],
  Cuisine: ["Fast Food", "Mixed", "Restaurants", "Coffee / Cafe", "Coffee", "Saudi / Arabic", "Saudi", "International", "Pizza / Italian", "Bakery / Pastry", "Lebanese", "Middle Eastern", "Indian", "Pakistani", "Chinese", "Japanese", "Korean", "Thai", "Italian", "American", "Turkish", "Yemeni", "Egyptian", "Syrian", "Seafood", "Grills", "UNAVAILABLE", "UNAPPLICABLE"],
  Entrance_Location: ["Front", "Side", "Back", "Mall Entrance", "Basement", "UNAVAILABLE"],
};

export const ALLOWED_COMPANY_STATUS = ["Open", "Temporarily Closed", "Permanently Closed"];
export const ALLOWED_FLOOR_NUMBERS = ["G", "B1", "1", "2", "3", "4", "5"];

/* ═══════════ FLAG REASONS ═══════════ */
export const REVIEW_FLAGS = [
  "Business name is incorrect",
  "Image and Text's Phone Number is Different",
  "Has Multiple Images But Are All The Same",
  "Image is Unusable",
  "Completely Wrong Category",
  "Commercial License is wrong",
  "Arabic phonetic rendering of English name does not match",
  "Homepage is incorrect",
  "Duplicate POI",
  "Wrong Working Hours",
  "Different POI Image Exists",
  "Different POI's Picture is Mapped",
  "Different POI's Video is Mapped",
  "Business name is wrong",
  "Video is Unusable",
  "Interior Image is the Same as Exterior",
  "Video is not of Interior but Exterior",
  "Image Contains Multiple POIs",
  "Photo is of Menu QR, not Interior",
  "Another photo that appears to be of the same place",
  "Exterior and interior photo is mixed",
];

/* ═══════════ MEDIA ═══════════ */
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

/* ═══════════ IMPORT COLUMN MAPPING ═══════════ */
export const IMPORT_COL_MAP: Record<string, string> = {
  "GlobalID": "GlobalID", "Name (AR)": "Name_AR", "Name (EN)": "Name_EN", "Legal Name": "Legal_Name",
  "exterior photo URL": "Exterior_Photo_URL", "interior photo URL": "Interior_Photo_URL",
  "menu photo URL": "Menu_Photo_URL", "video": "Video_URL",
  "license photo URL": "License_Photo_URL", "additional photo URLs": "Additional_Photo_URLs",
  "Category": "Category", "Secondary Category": "Subcategory", "Category Level 3": "Category_Level_3",
  "Company Status": "Company_Status", "Latitude": "Latitude", "Longitude": "Longitude",
  "Google Map URL": "Google_Map_URL", "Building Number": "Building_Number", "Floor Number": "Floor_Number",
  "Entrance Location": "Entrance_Location", "Phone Number": "Phone_Number", "Email": "Email",
  "Website": "Website", "Social Media": "Social_Media", "Working Days": "Working_Days",
  "Working Hours for Each Day": "Working_Hours", "Break Time for Each Day": "Break_Time",
  "Holidays": "Holidays", "Menu Barcode URL": "Menu_Barcode_URL", "Language": "Language",
  "Cuisine": "Cuisine", "Accepted Payment Methods": "Payment_Methods",
  "Commercial License Number": "Commercial_License", "Menu": "Menu", "Drive Thru": "Drive_Thru",
  "Dine In": "Dine_In", "Only Delivery": "Only_Delivery", "Reservation": "Reservation",
  "Require Ticket": "Require_Ticket", "Order from Car": "Order_from_Car",
  "Pickup Point Exists": "Pickup_Point", "WiFi": "WiFi", "Music": "Music",
  "Valet Parking": "Valet_Parking", "Has Parking Lot": "Has_Parking_Lot",
  "Is Wheelchair Accessible": "Wheelchair_Accessible", "Has Family Seating": "Family_Seating",
  "Has a Waiting Area": "Waiting_Area", "Has Separate Rooms for Dining": "Private_Dining",
  "Has Smoking Area": "Smoking_Area", "Children Area": "Children_Area", "Shisha": "Shisha",
  "Live Sport Broadcasting": "Live_Sports", "Is Landmark": "Is_Landmark", "Is Trending": "Is_Trending",
  "Large Groups Can Be Seated": "Large_Groups", "Has Women-Only Prayer Room": "Women_Prayer_Room",
  "Provides Iftar Tent": "Iftar_Tent", "Offers Iftar Menu": "Iftar_Menu",
  "Is Open During Suhoor": "Open_Suhoor", "Is Free Entry": "Free_Entry",
  "Number of Menu Photos": "Num_Menu_Photos", "Number of Additional Photos": "Num_Additional_Photos",
  "District (AR)": "District_AR", "District (EN)": "District_EN",
  "Amenities": "Amenities", "Confidence": "Confidence", "Source": "Source", "All_Sources": "All_Sources",
  "Importance_Score": "Importance_Score", "QA_Score": "QA_Score",
  "Review_Flag": "Review_Flag", "Review_Notes": "Review_Notes", "Review_Status": "Review_Status",
};

/* ═══════════ YES/NO AMENITY FIELDS ═══════════ */
export const YES_NO_FIELDS = new Set([
  "Menu", "Drive_Thru", "Dine_In", "Only_Delivery", "Reservation", "Require_Ticket",
  "Order_from_Car", "Pickup_Point", "WiFi", "Music", "Valet_Parking", "Has_Parking_Lot",
  "Wheelchair_Accessible", "Family_Seating", "Waiting_Area", "Private_Dining",
  "Smoking_Area", "Children_Area", "Shisha", "Live_Sports", "Is_Landmark", "Is_Trending",
  "Large_Groups", "Women_Prayer_Room", "Iftar_Tent", "Iftar_Menu", "Open_Suhoor", "Free_Entry",
]);
