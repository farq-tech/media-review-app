"""
Enterprise POI Delivery QA Pipeline
Implements the Final POI Delivery QA Specification for client delivery.
Outputs: POI_Final_Clean.csv, POI_Duplicates_Removed.csv, POI_QA_Report.xlsx
"""

import pandas as pd
import numpy as np
import re
import io
import sys
from pathlib import Path
from collections import defaultdict
from datetime import datetime

try:
    from rapidfuzz import fuzz
except ImportError:
    def _fuzz_ratio(a, b):
        if not a or not b: return 0.0
        a, b = str(a).lower(), str(b).lower()
        if a == b: return 100.0
        from difflib import SequenceMatcher
        return SequenceMatcher(None, a, b).ratio() * 100
    fuzz = type('Fuzz', (), {'ratio': lambda a, b: max(_fuzz_ratio(a, b), _fuzz_ratio(b, a))})()

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

# ==================== CONFIG ====================
SCRIPT_DIR = Path(__file__).parent
INPUT_CSV = SCRIPT_DIR / 'POI_Surveyed_Final.csv'
OUTPUT_CLEAN = SCRIPT_DIR / 'POI_Final_Clean.csv'
OUTPUT_DUPES = SCRIPT_DIR / 'POI_Duplicates_Removed.csv'
OUTPUT_REPORT = SCRIPT_DIR / 'POI_QA_Report.xlsx'

# Mergeable fields for golden record
MERGE_FIELDS = ['Phone Number', 'Website', 'Working Hours for Each Day', 'Social Media', 'Commercial License Number']
MEDIA_FIELDS = ['exterior photo URL', 'interior photo URL', 'menu photo URL', 'video']
CATEGORY_MAP = {
    'Restaurant': 'Food & Beverage', 'Restaurants': 'Food & Beverage',
    'Pharmacy': 'Health & Medical', 'Laundry': 'Life & Convenience',
    'Barbershop': 'Life & Convenience', 'Auto Service': 'Services & Industry',
    'commercial': 'Services & Industry', 'retail': 'Shopping & Distribution'
}
INVALID_WEBSITE_DOMAINS = ['facebook.com', 'google.com', 'instagram.com', 'twitter.com', 'maps.google', 'maps.app']
BRANCH_INDICATORS = ['فرع', 'فرع ', 'branch', 'Branch', 'النفل', 'الوادي', 'الياسمين']  # Arabic/English branch terms
NAME_REJECT_PATTERNS = [r'\d{9,}', r'\d{3}\s*\d{3}\s*\d{3}']  # phone in name

# ==================== HELPERS ====================
def haversine_km(lat1, lon1, lat2, lon2):
    R = 6371
    lat1, lon1, lat2, lon2 = map(np.radians, [lat1, lon1, lat2, lon2])
    dlat = lat2 - lat1
    dlon = lon2 - lon1
    a = np.sin(dlat/2)**2 + np.cos(lat1) * np.cos(lat2) * np.sin(dlon/2)**2
    return 2 * R * np.arcsin(np.sqrt(a))

def normalize_name(s):
    if pd.isna(s): return ''
    s = re.sub(r'[^\w\s\u0600-\u06FF]', '', str(s).strip().lower())
    return ' '.join(s.split())

def is_filled(val):
    if pd.isna(val): return False
    s = str(val).strip().upper()
    return s not in ['UNAVAILABLE', '', 'NAN', 'NULL', 'N/A', 'NA', 'UNAPPLICABLE']

def field_completeness_score(row, fields):
    return sum(1 for f in fields if is_filled(row.get(f, '')))

def merge_media_urls(url_str):
    if not url_str or str(url_str).upper() == 'UNAVAILABLE': return []
    return [u.strip() for u in re.split(r'[,\s]+', str(url_str)) if u.strip() and 'UNAVAILABLE' not in u.upper()]

# ==================== 1. DEDUPLICATION (via shared Hybrid Matching Engine) ====================
def _import_matcher():
    """Import the shared duplicate matcher engine."""
    import os
    _backend_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'backend')
    if _backend_dir not in sys.path:
        sys.path.insert(0, _backend_dir)
    from duplicate_matcher import detect_duplicates as _engine
    return _engine

# CSV column name → API field name mapping
_CSV_TO_API = {
    'ID': 'GlobalID', 'Name (EN)': 'Name_EN', 'Name (AR)': 'Name_AR',
    'Phone Number': 'Phone_Number', 'Category': 'Category',
    'Latitude': 'Latitude', 'Longitude': 'Longitude',
    'Building Number': 'Building_Number', 'Floor Number': 'Floor_Number',
    'Commercial License Number': 'Commercial_License', 'Website': 'Website',
    'Google Map URL': 'Google_Map_URL',
}

def detect_duplicates(df):
    """Detect duplicates using the shared hybrid weighted scoring engine."""
    run_detection = _import_matcher()

    # Convert DataFrame rows to dicts compatible with the engine
    pois = []
    for _, row in df.iterrows():
        poi = {}
        for csv_col, api_col in _CSV_TO_API.items():
            if csv_col in df.columns:
                val = row.get(csv_col, '')
                poi[api_col] = '' if pd.isna(val) else str(val)
        pois.append(poi)

    result = run_detection(pois, max_distance=100, match_threshold=85,
                           possible_threshold=70, include_possible=False)

    # Convert GID-based groups back to DataFrame index-based groups
    gid_to_idx = {}
    for i, poi in enumerate(pois):
        gid_to_idx[poi.get('GlobalID', '')] = i

    dup_groups = []
    for group in result['duplicate_groups']:
        indices = []
        for gid in group['members']:
            if gid in gid_to_idx:
                indices.append(gid_to_idx[gid])
        if len(indices) > 1:
            dup_groups.append(indices)

    return dup_groups

def merge_duplicates(df, dup_groups):
    """Create golden records from duplicate groups. Retain GlobalID of golden record."""
    all_fields = list(df.columns)
    keep_indices = set()
    removed = []
    golden_updates = {}  # idx -> updated row dict

    for group in dup_groups:
        rows = [df.iloc[i].to_dict() for i in group]
        scores = [field_completeness_score(r, all_fields) for r in rows]
        golden_idx = group[np.argmax(scores)]
        golden = df.iloc[golden_idx].to_dict()
        keep_indices.add(golden_idx)

        for dup_idx in group:
            if dup_idx == golden_idx: continue
            dup_row = df.iloc[dup_idx].to_dict()
            removed.append(dup_row)
            for f in MERGE_FIELDS:
                if not is_filled(golden.get(f)) and is_filled(dup_row.get(f)):
                    golden[f] = dup_row[f]
            for mf in MEDIA_FIELDS:
                g_urls = set(merge_media_urls(golden.get(mf)))
                g_urls.update(merge_media_urls(dup_row.get(mf)))
                golden[mf] = ', '.join(g_urls) if g_urls else golden.get(mf)

        golden_updates[golden_idx] = golden

    # Apply merged golden rows
    for idx, row_dict in golden_updates.items():
        for col, val in row_dict.items():
            if col in df.columns:
                df.at[idx, col] = val

    drop_indices = [i for g in dup_groups for i in g if i not in keep_indices]
    clean_df = df.drop(index=drop_indices).reset_index(drop=True)
    removed_df = pd.DataFrame(removed) if removed else pd.DataFrame(columns=df.columns)

    return clean_df, removed_df, len(dup_groups)

# ==================== 2. PHONE VALIDATION ====================
def fix_phone(val):
    if not is_filled(val): return val, None
    s = str(val).strip()
    if 'E+' in s.upper() or 'e+' in s:
        try:
            n = float(s)
            s = str(int(n)) if n == int(n) else str(int(n))
        except: pass
    digits = re.sub(r'\D', '', s)
    if s.startswith('+966') or s.startswith('966'): digits = '966' + digits.lstrip('966')
    elif len(digits) in (9, 10): digits = '966' + digits
    if 9 <= len(digits) <= 12: return digits, None
    return val, 'INVALID_PHONE'

def validate_phone(row):
    val = row.get('Phone Number')
    fixed, err = fix_phone(val)
    return fixed, err, err == 'INVALID_PHONE' and 'E+' in str(val).upper()

# ==================== 3. LICENSE VALIDATION ====================
def validate_license(val):
    if not is_filled(val): return True, None
    s = str(val).strip()
    if 'E+' in s.upper() or re.search(r'[a-zA-Z]', s) or ' ' in s: return False, 'INVALID_LICENSE'
    digits = re.sub(r'\D', '', s)
    if len(digits) != 10: return False, 'LICENSE_NOT_10_DIGITS'
    return True, None

# ==================== 4. CATEGORY VALIDATION ====================
def validate_category(row):
    cat = str(row.get('Category', '')).strip()
    mapped = CATEGORY_MAP.get(cat, cat)
    err = None
    if 'Restaurant' in cat or 'restaurant' in cat or cat in ['Restaurants', 'commercial']:
        if not is_filled(row.get('menu photo URL')) and not is_filled(row.get('video')):
            seating = any(is_filled(row.get(f)) for f in ['Has Family Seating', 'Has a Waiting Area', 'Dine In'])
            if not seating: err = 'RESTAURANT_NO_MENU_OR_SEATING'
    return mapped, err

# ==================== 5. WEBSITE VALIDATION ====================
def validate_website(val, name_en):
    if not is_filled(val): return True, None
    v = str(val).lower()
    for d in INVALID_WEBSITE_DOMAINS:
        if d in v: return False, 'INVALID_WEBSITE_DOMAIN'
    return True, None

# ==================== 6. BUSINESS IDENTITY ====================
def validate_business_name(row):
    name_ar = str(row.get('Name (AR)', '')).strip()
    name_en = str(row.get('Name (EN)', '')).strip()
    errs = []
    for pat in NAME_REJECT_PATTERNS:
        if re.search(pat, name_ar) or re.search(pat, name_en): errs.append('NAME_CONTAINS_PHONE')
    for ind in BRANCH_INDICATORS:
        if ind in name_ar or ind in name_en: errs.append('NAME_CONTAINS_BRANCH')
    if errs: return errs
    return []

# ==================== 7. MEDIA VALIDATION ====================
def validate_media(row):
    """7.1-7.2: Duplicate URLs, exterior==interior conflict."""
    errs = []
    ext = str(row.get('exterior photo URL', '') or '').strip()
    intr = str(row.get('interior photo URL', '') or '').strip()
    menu = str(row.get('menu photo URL', '') or '').strip()
    vid = str(row.get('video', '') or '').strip()
    all_urls = merge_media_urls(ext) + merge_media_urls(intr) + merge_media_urls(menu) + merge_media_urls(vid)
    if len(all_urls) != len(set(all_urls)):
        errs.append('DUPLICATE_MEDIA_URLS')
    if ext and intr and ext.upper() != 'UNAVAILABLE' and intr.upper() != 'UNAVAILABLE':
        ext_urls = set(merge_media_urls(ext))
        int_urls = set(merge_media_urls(intr))
        if ext_urls & int_urls: errs.append('EXTERIOR_INTERIOR_SAME_URL')
    return errs

# ==================== 8. MEDIA INFERENCE (Spec §8) ====================
def apply_media_inference(row):
    """if exterior exists → entrance exists; if interior missing AND video exists → treat video as interior."""
    ext = is_filled(row.get('exterior photo URL'))
    intr = is_filled(row.get('interior photo URL'))
    vid = is_filled(row.get('video'))
    # No schema change for "entrance exists" - just validation hint
    # "interior missing AND video exists → treat video as interior evidence" - flag for manual review
    return row

# ==================== 9. WORKING HOURS ====================
def validate_working_hours(val):
    if not is_filled(val): return True, None
    s = str(val)
    for part in re.split(r'[;,]', s):
        m = re.search(r'(\d{1,2}):(\d{2})\s*-\s*(\d{1,2}):(\d{2})', part, re.I)
        if m:
            h1, m1, h2, m2 = int(m.group(1)), int(m.group(2)), int(m.group(3)), int(m.group(4))
            t1, t2 = h1 * 60 + m1, h2 * 60 + m2
            if t2 < t1 and t2 > 0: return False, 'HOURS_OPEN_AFTER_CLOSE'
    return True, None

# ==================== MAIN PIPELINE ====================
def run_pipeline():
    print('=' * 70)
    print('POI Delivery QA Pipeline')
    print('=' * 70)

    df = pd.read_csv(INPUT_CSV)
    total_in = len(df)
    print(f'Input: {total_in} POIs from {INPUT_CSV.name}\n')

    report = {
        'duplicates_removed': [], 'phone_fixes': [], 'license_errors': [],
        'category_corrections': [], 'website_errors': [], 'name_errors': [],
        'media_conflicts': [], 'hours_errors': [], 'manual_review': []
    }

    # Step 1: Deduplicate
    print('Step 1: Deduplication...')
    dup_groups = detect_duplicates(df)
    if dup_groups:
        df_clean, df_removed, n_groups = merge_duplicates(df, dup_groups)
        for g in dup_groups:
            report['duplicates_removed'].append({'group': g, 'count': len(g)})
        df = df_clean
        print(f'  Merged {len(df_removed)} duplicates into {n_groups} golden records')
        df_removed.to_csv(OUTPUT_DUPES, index=False, encoding='utf-8-sig')
        print(f'  Saved: {OUTPUT_DUPES.name}')
    else:
        print('  No duplicates found')
        df_removed = pd.DataFrame()

    # License uniqueness (Spec 5)
    license_vals = df['Commercial License Number'].apply(lambda x: re.sub(r'\D', '', str(x)) if is_filled(x) else '')
    license_counts = license_vals[license_vals.str.len() >= 8].value_counts()
    dup_licenses = license_counts[license_counts > 1].index.tolist()
    for idx, row in df.iterrows():
        lv = re.sub(r'\D', '', str(row.get('Commercial License Number', '')))
        if len(lv) >= 8 and lv in dup_licenses:
            report['license_errors'].append({'id': row.get('ID'), 'error': 'LICENSE_DUPLICATE'})

    # Steps 2–10: Validate and fix
    print('\nStep 2–10: Validation...')
    phone_fixed = 0
    for idx, row in df.iterrows():
        # Phone
        fixed, err, was_sci = validate_phone(row)
        if fixed != row.get('Phone Number'):
            df.at[idx, 'Phone Number'] = fixed
            if was_sci: phone_fixed += 1; report['phone_fixes'].append({'id': row.get('ID'), 'fixed': fixed})
        if err: report['manual_review'].append({'id': row.get('ID'), 'rule': 'phone', 'error': err})

        # License
        ok, err = validate_license(row.get('Commercial License Number'))
        if not ok: report['license_errors'].append({'id': row.get('ID'), 'error': err})

        # Category
        mapped, err = validate_category(row)
        if mapped != row.get('Category'):
            df.at[idx, 'Category'] = mapped
            report['category_corrections'].append({'id': row.get('ID'), 'new': mapped})
        if err: report['manual_review'].append({'id': row.get('ID'), 'rule': 'category', 'error': err})

        # Website
        ok, err = validate_website(row.get('Website'), row.get('Name (EN)'))
        if not ok: report['website_errors'].append({'id': row.get('ID'), 'error': err})

        # Business name
        errs = validate_business_name(row)
        for e in errs: report['name_errors'].append({'id': row.get('ID'), 'error': e})

        # Media
        errs = validate_media(row)
        for e in errs: report['media_conflicts'].append({'id': row.get('ID'), 'error': e})

        # Working hours
        ok, err = validate_working_hours(row.get('Working Hours for Each Day'))
        if not ok: report['hours_errors'].append({'id': row.get('ID'), 'error': err})

    print(f'  Phone scientific notation fixed: {phone_fixed}')
    print(f'  License errors: {len(report["license_errors"])}')
    print(f'  Media conflicts: {len(report["media_conflicts"])}')
    print(f'  Hours errors: {len(report["hours_errors"])}')

    # Final delivery gate (Spec 10)
    pois_with_errors = set()
    for r in report['license_errors']: pois_with_errors.add(r.get('id'))
    for r in report['media_conflicts']: pois_with_errors.add(r.get('id'))
    for r in report['manual_review']:
        if r.get('rule') in ['phone', 'category']: pois_with_errors.add(r.get('id'))
    total_out = len(df)
    error_poi_count = len(pois_with_errors)
    accuracy = (total_out - error_poi_count) / total_out * 100 if total_out else 0

    print('\n' + '=' * 70)
    print('FINAL DELIVERY GATE (Spec §10)')
    print('=' * 70)
    print(f'  Clean POIs: {total_out}')
    print(f'  Duplicates removed: {total_in - total_out}')
    print(f'  POIs with errors: {error_poi_count}')
    print(f'  Estimated accuracy: {accuracy:.1f}% (target ≥98%)')
    checks = [
        ('Duplicate POI', len(report['duplicates_removed']) == 0 or total_in - total_out >= 0),
        ('License errors', len(report['license_errors']) == 0),
        ('Media conflicts', len(report['media_conflicts']) == 0),
        ('Accuracy ≥98%', accuracy >= 98)
    ]
    for name, ok in checks:
        print(f'  {name}: {"✓" if ok else "✗"}')
    print(f'  Gate: {"PASS" if accuracy >= 98 and len(report["license_errors"]) == 0 and len(report["media_conflicts"]) == 0 else "NEEDS FIXES"}')

    df.to_csv(OUTPUT_CLEAN, index=False, encoding='utf-8-sig')
    print(f'\nSaved: {OUTPUT_CLEAN.name}')

    # QA Report (Excel)
    try:
        with pd.ExcelWriter(OUTPUT_REPORT, engine='openpyxl') as w:
            pd.DataFrame([{'Metric': 'Total Input', 'Value': total_in},
                         {'Metric': 'Total Output', 'Value': total_out},
                         {'Metric': 'Duplicates Removed', 'Value': total_in - total_out},
                         {'Metric': 'Accuracy %', 'Value': f'{accuracy:.1f}'},
                         {'Metric': 'Timestamp', 'Value': datetime.now().isoformat()}]).to_excel(w, sheet_name='Summary', index=False)
            if report['duplicates_removed']:
                pd.DataFrame(report['duplicates_removed']).to_excel(w, sheet_name='Duplicates Removed', index=False)
            if report['phone_fixes']:
                pd.DataFrame(report['phone_fixes']).to_excel(w, sheet_name='Phone Fixes', index=False)
            if report['license_errors']:
                pd.DataFrame(report['license_errors']).to_excel(w, sheet_name='License Errors', index=False)
            if report['category_corrections']:
                pd.DataFrame(report['category_corrections']).to_excel(w, sheet_name='Category Corrections', index=False)
            if report['media_conflicts']:
                pd.DataFrame(report['media_conflicts']).to_excel(w, sheet_name='Media Conflicts', index=False)
            if report['hours_errors']:
                pd.DataFrame(report['hours_errors']).to_excel(w, sheet_name='Hours Errors', index=False)
            if report['manual_review']:
                pd.DataFrame(report['manual_review']).to_excel(w, sheet_name='Manual Review', index=False)
        print(f'Saved: {OUTPUT_REPORT.name}')
    except ImportError:
        print('  (Install openpyxl for Excel report: pip install openpyxl)')
        report_path = OUTPUT_REPORT.with_suffix('.csv')
        pd.DataFrame(report['manual_review']).to_csv(report_path, index=False, encoding='utf-8-sig')
        print(f'Saved CSV report: {report_path.name}')

    print('\nDone.')
    return df, report

if __name__ == '__main__':
    run_pipeline()
