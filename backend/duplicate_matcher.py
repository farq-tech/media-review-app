"""
Hybrid POI Duplicate Detection Engine.
Pure Python module — no Flask or DB dependency.

Combines spatial proximity, bilingual fuzzy name matching,
phone/license/website signals, and category validation
into a gated weighted score with hard rejection rules.

Key design principles:
- Category family incompatibility → hard reject
- Distance alone cannot rescue weak identity evidence
- Shared/common phones are weak evidence
- Name matching uses brand-core extraction, not just token overlap
- Contradiction detection before scoring
"""
import re
import math
import unicodedata
from collections import Counter

try:
    from rapidfuzz import fuzz
    HAS_RAPIDFUZZ = True
except ImportError:
    HAS_RAPIDFUZZ = False

# ─── Business Suffix Removal ───
_EN_SUFFIXES = [
    r'\bltd\.?\b', r'\bllc\.?\b', r'\binc\.?\b', r'\bcorp\.?\b',
    r'\bco\.?\b', r'\best\.?\b', r'\bcompany\b', r'\benterprise\b',
    r'\blimited\b', r'\bgroup\b', r'\bholding\b',
]
_AR_SUFFIXES = [
    'شركة', 'مؤسسة', 'مكتب', 'محل', 'مجموعة',
    'للتجارة', 'التجارية', 'للمقاولات',
]

# ─── Arabic Category Words (stripped from names before comparison) ───
_AR_CATEGORY_WORDS = {
    'مطعم', 'صيدلية', 'مقهى', 'مغسلة', 'بقالة', 'مسجد',
    'مدرسة', 'مستشفى', 'فندق', 'مقاولات', 'محل', 'كافيه',
    'بوفيه', 'بوفية', 'سوبرماركت', 'ماركت', 'صالون', 'حلاق',
}
_EN_CATEGORY_WORDS = {
    'restaurant', 'pharmacy', 'cafe', 'laundry', 'grocery', 'mosque',
    'school', 'hospital', 'hotel', 'shop', 'store', 'salon', 'barbershop',
    'supermarket', 'market', 'buffet', 'cafeteria', 'center', 'centre',
    'services', 'service',
}

# ─── Generic/Low-Value English Tokens ───
_EN_STOPWORDS = {
    'al', 'el', 'the', 'and', 'for', 'of', 'in', 'at', 'to',
    'mens', 'womens', 'women', 'men', 'male', 'female',
}

# ─── Arabic Character Normalization ───
_AR_CHAR_MAP = {
    '\u0623': '\u0627',  # أ → ا
    '\u0625': '\u0627',  # إ → ا
    '\u0622': '\u0627',  # آ → ا
    '\u0629': '\u0647',  # ة → ه
    '\u0649': '\u064a',  # ى → ي
}
_AR_DIACRITICS = re.compile(r'[\u064B-\u065F\u0670]')

# ─── Phonetic Transliteration Map (EN → AR) ───
_EN_TO_AR_MAP = [
    ('sh', '\u0634'), ('ch', '\u062a\u0634'), ('th', '\u062b'),
    ('kh', '\u062e'), ('ph', '\u0641'),
    ('tion', '\u0634\u0646'), ('oo', '\u0648'), ('ee', '\u064a'),
    ('ou', '\u0648'), ('ai', '\u064a'),
    ('a', '\u0627'), ('b', '\u0628'), ('c', '\u0643'), ('d', '\u062f'),
    ('e', '\u064a'), ('f', '\u0641'), ('g', '\u062c'), ('h', '\u0647'),
    ('i', '\u064a'), ('j', '\u062c'), ('k', '\u0643'), ('l', '\u0644'),
    ('m', '\u0645'), ('n', '\u0646'), ('o', '\u0648'), ('p', '\u0628'),
    ('q', '\u0643'), ('r', '\u0631'), ('s', '\u0633'), ('t', '\u062a'),
    ('u', '\u0648'), ('v', '\u0641'), ('w', '\u0648'), ('x', '\u0643\u0633'),
    ('y', '\u064a'), ('z', '\u0632'),
]

# ─── Bad Sentinel Values ───
_BAD_SENTINELS = {
    'n/a', 'na', 'none', 'null', '-', '--', '---', 'unknown', 'tbd',
    'not available', 'not applicable', 'nil', '.', '..', 'empty',
    'no data', 'unavailable',
}


# ═══════════════════════════════════════════
#  CATEGORY FAMILY TAXONOMY
# ═══════════════════════════════════════════

# Map each category to a broad family for compatibility checking
CATEGORY_FAMILY = {
    # Religious
    'Mosques': 'Religious',
    # Education
    'Education': 'Education',
    # Health & Medical
    'Hospitals': 'Health',
    'Pharmacies': 'Health',
    # Government & Public
    'Government Services': 'Government',
    'Public Services': 'Government',
    'Banks': 'Finance',
    # Food & Dining
    'Restaurants': 'Food',
    'Food and Beverages': 'Food',
    'Coffee Shops': 'Food',
    'Grocery': 'Food',
    # Retail & Shopping
    'Shopping': 'Retail',
    'Home Goods': 'Retail',
    # Personal Care
    'Beauty and Spa': 'PersonalCare',
    # Automotive
    'Automotive Services': 'Automotive',
    'Fuel Stations': 'Automotive',
    'Motorcycle': 'Automotive',
    # Services & Corporate
    'Corporate': 'Services',
    # Accommodation
    'Hotels and Accommodations': 'Accommodation',
    # Entertainment & Leisure
    'Entertainment': 'Leisure',
    'Sports': 'Leisure',
    'Public Parks': 'Leisure',
    # Culture
    'Cultural Sites': 'Culture',
    # Transportation
    'Transportation': 'Transport',
}

# Pairs of families that are HARD INCOMPATIBLE — never a valid duplicate
_HARD_INCOMPATIBLE_FAMILIES = {
    frozenset({'Religious', 'PersonalCare'}),
    frozenset({'Religious', 'Food'}),
    frozenset({'Religious', 'Retail'}),
    frozenset({'Religious', 'Automotive'}),
    frozenset({'Religious', 'Services'}),
    frozenset({'Religious', 'Leisure'}),
    frozenset({'Religious', 'Accommodation'}),
    frozenset({'Religious', 'Health'}),
    frozenset({'Education', 'PersonalCare'}),
    frozenset({'Education', 'Food'}),
    frozenset({'Education', 'Automotive'}),
    frozenset({'Government', 'PersonalCare'}),
    frozenset({'Government', 'Food'}),
    frozenset({'Government', 'Automotive'}),
    frozenset({'Health', 'PersonalCare'}),
    frozenset({'Health', 'Food'}),
    frozenset({'Health', 'Automotive'}),
    frozenset({'Health', 'Retail'}),
    frozenset({'Finance', 'Food'}),
    frozenset({'Finance', 'PersonalCare'}),
    frozenset({'Finance', 'Automotive'}),
}

# Families that are SOFT COMPATIBLE — related enough to possibly be duplicates
_SOFT_COMPATIBLE_FAMILIES = {
    frozenset({'Food', 'Food'}),
    frozenset({'Retail', 'Retail'}),
    frozenset({'Automotive', 'Automotive'}),
    frozenset({'Health', 'Health'}),
    frozenset({'Food', 'Retail'}),  # e.g., "Food and Beverages" vs "Shopping" for food shops
    frozenset({'Services', 'Retail'}),
    frozenset({'Services', 'Automotive'}),
    frozenset({'Services', 'Food'}),
    frozenset({'Leisure', 'Leisure'}),
}


def get_category_family(category):
    """Get the broad family for a category string."""
    if not category:
        return None
    return CATEGORY_FAMILY.get(category.strip(), None)


def category_compatibility(cat_a, cat_b):
    """Check category compatibility.
    Returns: 'same', 'compatible', 'incompatible', 'hard_reject', or 'unknown'.
    """
    if not cat_a or not cat_b:
        return 'unknown'
    ca = cat_a.strip().lower()
    cb = cat_b.strip().lower()
    if ca == cb:
        return 'same'

    fam_a = get_category_family(cat_a.strip())
    fam_b = get_category_family(cat_b.strip())

    if not fam_a or not fam_b:
        return 'unknown'
    if fam_a == fam_b:
        return 'compatible'
    pair = frozenset({fam_a, fam_b})
    if pair in _HARD_INCOMPATIBLE_FAMILIES:
        return 'hard_reject'
    if pair in _SOFT_COMPATIBLE_FAMILIES:
        return 'compatible'
    return 'incompatible'


# ─── Scoring Weights (rebalanced: name dominant, distance demoted) ───
WEIGHTS = {
    'name': 0.50,
    'distance': 0.15,
    'category': 0.15,
    'phone': 0.15,
    'auxiliary': 0.05,
}

# ─── Distance Scoring Tiers ───
DISTANCE_TIERS = [
    (10, 100),   # < 10m = 100
    (25, 90),    # 10-25m = 90
    (50, 75),    # 25-50m = 75
    (100, 50),   # 50-100m = 50
]
MAX_CANDIDATE_DISTANCE = 100  # meters

# ─── Decision Thresholds ───
MATCH_THRESHOLD = 85.0
POSSIBLE_MATCH_THRESHOLD = 70.0

# ─── Frequency Thresholds ───
PHONE_SHARED_THRESHOLD = 3  # phones appearing in 3+ POIs are weak evidence
LICENSE_SHARED_THRESHOLD = 3  # licenses appearing in 3+ POIs are contaminated data

# ─── Spatial Bin Size ───
BIN_SIZE_DEG = 0.001  # ~111m per bin


# ═══════════════════════════════════════════
#  NORMALIZATION FUNCTIONS
# ═══════════════════════════════════════════

def normalize_arabic(text):
    """Normalize Arabic text: hamza unification, ta-marbuta, alif-maqsura,
    diacritic removal, business suffix stripping, category word removal."""
    if not text or str(text).strip().lower() in _BAD_SENTINELS:
        return ''
    text = str(text).strip()
    # Remove diacritics/tashkeel
    text = _AR_DIACRITICS.sub('', text)
    # Character normalization
    for src, dst in _AR_CHAR_MAP.items():
        text = text.replace(src, dst)
    # Remove business suffixes
    for suffix in _AR_SUFFIXES:
        text = text.replace(suffix, '')
    # Remove category words
    for word in _AR_CATEGORY_WORDS:
        text = text.replace(word, '')
    # Remove non-word chars except spaces and Arabic
    text = re.sub(r'[^\w\s\u0600-\u06FF]', '', text)
    return ' '.join(text.split()).strip()


def normalize_english(text):
    """Normalize English text: lowercase, suffix removal, category word removal."""
    if not text or str(text).strip().lower() in _BAD_SENTINELS:
        return ''
    text = str(text).lower().strip()
    for pattern in _EN_SUFFIXES:
        text = re.sub(pattern, '', text, flags=re.IGNORECASE)
    # Remove category words
    words = text.split()
    words = [w for w in words if w not in _EN_CATEGORY_WORDS]
    text = ' '.join(words)
    # Remove non-word chars except spaces
    text = re.sub(r'[^\w\s]', '', text)
    return ' '.join(text.split()).strip()


def _extract_brand_core(en_text):
    """Extract brand-core tokens from English name, removing stopwords,
    category words, and low-value tokens. Returns list of significant tokens."""
    if not en_text:
        return []
    text = en_text.lower().strip()
    for pattern in _EN_SUFFIXES:
        text = re.sub(pattern, '', text, flags=re.IGNORECASE)
    text = re.sub(r'[^\w\s]', '', text)
    words = text.split()
    # Remove stopwords, category words
    significant = [w for w in words
                   if w not in _EN_CATEGORY_WORDS
                   and w not in _EN_STOPWORDS
                   and len(w) > 1]
    return significant


def normalize_phone(p):
    """Normalize phone: strip non-digits, remove Saudi prefix, take 9 digits."""
    if not p:
        return ''
    p_lower = str(p).strip().lower()
    if p_lower in _BAD_SENTINELS:
        return ''
    digits = re.sub(r'\D', '', str(p))
    digits = digits.lstrip('966').lstrip('0')
    return digits[:9] if len(digits) >= 7 else ''


def normalize_license(lic):
    """Normalize commercial license: digits only."""
    if not lic:
        return ''
    lic_lower = str(lic).strip().lower()
    if lic_lower in _BAD_SENTINELS:
        return ''
    return re.sub(r'\D', '', str(lic))


def extract_website_domain(url):
    """Extract domain from URL, stripping www prefix."""
    if not url:
        return ''
    url_lower = str(url).strip().lower()
    if url_lower in _BAD_SENTINELS:
        return ''
    url_lower = re.sub(r'^https?://', '', url_lower)
    url_lower = re.sub(r'^www\.', '', url_lower)
    domain = url_lower.split('/')[0].split('?')[0]
    return domain


def _transliterate_en_to_ar(en_text):
    """Phonetic transliteration from English to approximate Arabic."""
    result = ''
    en_lower = en_text.lower()
    i = 0
    while i < len(en_lower):
        matched = False
        for length in (4, 3, 2, 1):
            chunk = en_lower[i:i + length]
            for en, ar in _EN_TO_AR_MAP:
                if len(en) == length and chunk == en:
                    result += ar
                    i += length
                    matched = True
                    break
            if matched:
                break
        if not matched:
            if en_lower[i] == ' ':
                result += ' '
            i += 1
    return result


# ═══════════════════════════════════════════
#  SIMILARITY FUNCTIONS
# ═══════════════════════════════════════════

def _bigram_similarity(a, b):
    """Dice coefficient on character bigrams. Returns 0-100."""
    a = a.replace(' ', '')
    b = b.replace(' ', '')
    if not a or not b:
        return 0.0
    if len(a) < 2 or len(b) < 2:
        return 100.0 if a == b else 0.0
    bg1 = {a[i:i + 2] for i in range(len(a) - 1)}
    bg2 = {b[i:i + 2] for i in range(len(b) - 1)}
    inter = len(bg1 & bg2)
    return (2 * inter / (len(bg1) + len(bg2))) * 100


def _brand_core_similarity(name_en_a, name_en_b):
    """Compare brand-core tokens between two English names.
    Returns 0-100 based on Jaccard-like overlap of significant tokens.
    Penalizes when overlap is only generic/family-name tokens."""
    tokens_a = _extract_brand_core(name_en_a)
    tokens_b = _extract_brand_core(name_en_b)

    if not tokens_a or not tokens_b:
        return 0.0

    set_a = set(tokens_a)
    set_b = set(tokens_b)
    overlap = set_a & set_b
    union = set_a | set_b

    if not union:
        return 0.0

    # Jaccard similarity
    jaccard = len(overlap) / len(union)

    # If short name is fully contained in long name, it's suspicious
    # (e.g. "Al Husaini" is in "Asmaa Oudah Al Husaini")
    # Only count as strong match if the shorter name IS the overlap
    shorter = tokens_a if len(tokens_a) <= len(tokens_b) else tokens_b
    longer = tokens_b if len(tokens_a) <= len(tokens_b) else tokens_a

    if len(shorter) > 0 and set(shorter).issubset(set(longer)):
        # Shorter name fully contained in longer name
        # Score based on how much of the longer name is covered
        coverage = len(shorter) / len(longer)
        if coverage < 0.5:
            # "Al Husaini" (2 tokens) in "Asmaa Oudah Al Husaini" (4 tokens) = 50% coverage
            # This is weak — partial overlap
            return jaccard * 100 * 0.6  # penalize
    return jaccard * 100


def compute_name_similarity(name_en_a, name_en_b, name_ar_a='', name_ar_b=''):
    """Multi-metric bilingual name similarity. Returns 0-100.
    Uses rapidfuzz metrics, brand-core analysis, and cross-language transliteration.
    Uses weighted combination rather than just max to reduce false positives."""
    scores = []

    # English name comparison
    en_a = normalize_english(name_en_a)
    en_b = normalize_english(name_en_b)
    if en_a and en_b:
        if HAS_RAPIDFUZZ:
            # Use ratio (strict) and token_sort_ratio (reorder-tolerant)
            # Avoid token_set_ratio and partial_ratio which are too permissive
            ratio_score = fuzz.ratio(en_a, en_b)
            token_sort = fuzz.token_sort_ratio(en_a, en_b)
            # token_set_ratio is permissive; weight it down
            token_set = fuzz.token_set_ratio(en_a, en_b)
            # Use weighted average instead of max to avoid single-metric inflation
            fuzzy_avg = ratio_score * 0.4 + token_sort * 0.35 + token_set * 0.25
            scores.append(fuzzy_avg)
        else:
            scores.append(_bigram_similarity(en_a, en_b))

        # Brand-core similarity as a separate signal
        brand_sim = _brand_core_similarity(name_en_a, name_en_b)
        if brand_sim > 0:
            scores.append(brand_sim)

    # Arabic name comparison
    ar_a = normalize_arabic(name_ar_a)
    ar_b = normalize_arabic(name_ar_b)
    if ar_a and ar_b:
        if HAS_RAPIDFUZZ:
            ratio_score = fuzz.ratio(ar_a, ar_b)
            token_sort = fuzz.token_sort_ratio(ar_a, ar_b)
            token_set = fuzz.token_set_ratio(ar_a, ar_b)
            fuzzy_avg = ratio_score * 0.4 + token_sort * 0.35 + token_set * 0.25
            scores.append(fuzzy_avg)
        else:
            scores.append(_bigram_similarity(ar_a, ar_b))

    # Cross-language: transliterate EN→AR and compare
    if en_a and ar_b:
        translit = _transliterate_en_to_ar(en_a)
        if translit:
            scores.append(_bigram_similarity(
                translit.replace(' ', ''),
                ar_b.replace(' ', '')
            ))
    if en_b and ar_a:
        translit = _transliterate_en_to_ar(en_b)
        if translit:
            scores.append(_bigram_similarity(
                translit.replace(' ', ''),
                ar_a.replace(' ', '')
            ))

    return max(scores) if scores else 0.0


# ═══════════════════════════════════════════
#  COMPONENT SCORING
# ═══════════════════════════════════════════

def score_distance(distance_m):
    """Distance to 0-100 score using tiered lookup."""
    if distance_m > MAX_CANDIDATE_DISTANCE:
        return 0.0
    for threshold, score in DISTANCE_TIERS:
        if distance_m <= threshold:
            return float(score)
    return 0.0


def score_category(cat_a, cat_b):
    """Category match score. 100=same, 0=different, 50=unknown."""
    if not cat_a or not cat_b:
        return 50.0
    return 100.0 if cat_a.strip().lower() == cat_b.strip().lower() else 0.0


def score_phone(phone_a, phone_b):
    """Phone match: 100 if exact normalized match, 0 otherwise."""
    pa = normalize_phone(phone_a)
    pb = normalize_phone(phone_b)
    if not pa or not pb:
        return 0.0
    return 100.0 if pa == pb else 0.0


def score_auxiliary(poi_a, poi_b):
    """Auxiliary signals: license, website domain, building/floor, Google Maps.
    Returns 0-100 (average of available signals)."""
    signals = []

    # Commercial license
    lic_a = normalize_license(poi_a.get('Commercial_License', ''))
    lic_b = normalize_license(poi_b.get('Commercial_License', ''))
    if lic_a and lic_b:
        signals.append(100.0 if lic_a == lic_b else 0.0)

    # Website domain
    dom_a = extract_website_domain(poi_a.get('Website', ''))
    dom_b = extract_website_domain(poi_b.get('Website', ''))
    if dom_a and dom_b:
        signals.append(100.0 if dom_a == dom_b else 0.0)

    # Google Maps URL
    gmap_a = (poi_a.get('Google_Map_URL', '') or '').strip()
    gmap_b = (poi_b.get('Google_Map_URL', '') or '').strip()
    if gmap_a and gmap_b and gmap_a.lower() not in _BAD_SENTINELS and gmap_b.lower() not in _BAD_SENTINELS:
        signals.append(100.0 if gmap_a == gmap_b else 0.0)

    # Building + floor match
    bldg_a = f"{poi_a.get('Building_Number', '') or ''}|{poi_a.get('Floor_Number', '') or ''}"
    bldg_b = f"{poi_b.get('Building_Number', '') or ''}|{poi_b.get('Floor_Number', '') or ''}"
    if bldg_a != '|' and bldg_b != '|':
        signals.append(100.0 if bldg_a == bldg_b else 0.0)

    return (sum(signals) / len(signals)) if signals else 0.0


# ═══════════════════════════════════════════
#  COMPOSITE SCORING & DECISION
# ═══════════════════════════════════════════

def compute_match_score(poi_a, poi_b, distance_m, name_sim=None,
                        phone_freq_a=1, phone_freq_b=1,
                        license_freq_a=1, license_freq_b=1):
    """Compute the final weighted match score between two POIs.

    Implements a gated scoring pipeline:
    1. Hard rejection (category family incompatibility)
    2. Identity gate (require minimum evidence before distance helps)
    3. Phone frequency suppression (shared phones ≠ unique identity)
    4. Weighted composite score
    5. Tier overrides with contradiction guards

    Returns detailed result dict with component scores and decision."""

    # Component scores
    if name_sim is None:
        name_sim = compute_name_similarity(
            poi_a.get('Name_EN', ''), poi_b.get('Name_EN', ''),
            poi_a.get('Name_AR', ''), poi_b.get('Name_AR', ''),
        )
    dist_score = score_distance(distance_m)
    cat_score = score_category(poi_a.get('Category', ''), poi_b.get('Category', ''))
    phone_sc = score_phone(poi_a.get('Phone_Number', ''), poi_b.get('Phone_Number', ''))
    aux_score = score_auxiliary(poi_a, poi_b)

    reasons = []
    tier1_match = False
    tier1_reasons = []

    cat_a = (poi_a.get('Category', '') or '').strip()
    cat_b = (poi_b.get('Category', '') or '').strip()
    cat_compat = category_compatibility(cat_a, cat_b)
    has_category_conflict = cat_compat in ('incompatible', 'hard_reject')

    # ── STAGE 1: Hard rejection — category family incompatibility ──
    if cat_compat == 'hard_reject':
        reasons.append('hard_reject_category_family')
        reasons.append('category_mismatch')
        return {
            'name_score': round(name_sim, 1),
            'distance_score': round(dist_score, 1),
            'category_score': 0.0,
            'phone_score': round(phone_sc, 1),
            'auxiliary_score': round(aux_score, 1),
            'final_score': 0.0,
            'match_status': 'NO_MATCH',
            'match_reasons': reasons,
            'distance_m': round(distance_m, 1),
            'tier1_match': False,
        }

    # ── STAGE 2: Phone frequency suppression ──
    phone_is_shared = False
    effective_phone_sc = phone_sc
    if phone_sc == 100:
        max_freq = max(phone_freq_a, phone_freq_b)
        if max_freq >= PHONE_SHARED_THRESHOLD:
            phone_is_shared = True
            # Reduce phone score for shared numbers
            effective_phone_sc = 30.0  # shared phone = weak evidence
            reasons.append(f'phone_shared_freq_{max_freq}')

    # ── STAGE 3: Identity gate — distance cannot rescue weak identity ──
    has_identity_evidence = (
        name_sim >= 60
        or (effective_phone_sc == 100 and not phone_is_shared)
        or aux_score >= 50  # license or website match
    )

    # Gate distance: if no identity evidence, cap distance contribution
    effective_dist_score = dist_score
    if not has_identity_evidence:
        effective_dist_score = dist_score * 0.3  # severely reduce distance reward
        if dist_score > 0:
            reasons.append('distance_gated_weak_identity')

    # ── STAGE 4: Category-aware scoring ──
    if cat_compat == 'same':
        effective_cat_score = 100.0
    elif cat_compat == 'compatible':
        effective_cat_score = 60.0  # related but not same
    elif cat_compat == 'incompatible':
        effective_cat_score = 0.0
    elif cat_compat == 'unknown':
        effective_cat_score = 40.0
    else:
        effective_cat_score = cat_score

    # ── STAGE 5: Weighted final score ──
    final = (
        WEIGHTS['name'] * name_sim +
        WEIGHTS['distance'] * effective_dist_score +
        WEIGHTS['category'] * effective_cat_score +
        WEIGHTS['phone'] * effective_phone_sc +
        WEIGHTS['auxiliary'] * aux_score
    )

    # ── Tier 1 overrides: deterministic key matches ──
    lic_a = normalize_license(poi_a.get('Commercial_License', ''))
    lic_b = normalize_license(poi_b.get('Commercial_License', ''))
    license_is_shared = max(license_freq_a, license_freq_b) >= LICENSE_SHARED_THRESHOLD
    if lic_a and lic_b and lic_a == lic_b:
        if license_is_shared:
            # Shared/contaminated license — not a reliable signal
            reasons.append(f'license_shared_freq_{max(license_freq_a, license_freq_b)}')
            # Don't set tier1_match for shared licenses
        else:
            tier1_match = True
            tier1_reasons.append('license_exact')
            # License match is strong — but still respect category
            if not has_category_conflict:
                final = max(final, 90.0)
            else:
                final = max(final, 70.0)  # different category dampens license

    pa = normalize_phone(poi_a.get('Phone_Number', ''))
    pb = normalize_phone(poi_b.get('Phone_Number', ''))
    if pa and pb and pa == pb and distance_m <= 50:
        tier1_match = True
        tier1_reasons.append('phone_exact_near')
        if not phone_is_shared and not has_category_conflict and name_sim >= 40:
            final = max(final, 85.0)
        elif not phone_is_shared and not has_category_conflict:
            final = max(final, 75.0)
        # If phone is shared or categories conflict, no boost

    dom_a = extract_website_domain(poi_a.get('Website', ''))
    dom_b = extract_website_domain(poi_b.get('Website', ''))
    if dom_a and dom_b and dom_a == dom_b and distance_m <= 100:
        tier1_match = True
        tier1_reasons.append('website_domain')
        if not has_category_conflict:
            final = max(final, 85.0)

    # ── STAGE 6: Contradiction penalties ──
    if has_category_conflict:
        if name_sim < 85:
            # Incompatible categories + weak name → heavy penalty
            final *= 0.5
            reasons.append('contradiction_category_name')
        else:
            # Incompatible categories but strong name → moderate penalty
            final *= 0.7
            reasons.append('category_conflict_penalty')

    # ── Strong match overrides (Tier 2) ──
    # Only when there is strong multi-signal agreement
    if (distance_m <= 20 and name_sim >= 90 and not has_category_conflict
            and cat_compat in ('same', 'compatible')):
        final = max(final, 92.0)
    if (effective_phone_sc == 100 and not phone_is_shared
            and distance_m <= 30 and not has_category_conflict
            and name_sim >= 60):
        final = max(final, 88.0)

    # ── Decision ──
    if final >= MATCH_THRESHOLD:
        status = 'MATCH'
    elif final >= POSSIBLE_MATCH_THRESHOLD:
        status = 'POSSIBLE_MATCH'
    else:
        status = 'NO_MATCH'

    # Build reasons list
    if name_sim >= 90:
        reasons.append(f'name_{name_sim:.0f}pct')
    elif name_sim >= 75:
        reasons.append(f'name_fuzzy_{name_sim:.0f}pct')
    if phone_sc == 100 and not phone_is_shared:
        reasons.append('phone_exact')
    elif phone_sc == 100 and phone_is_shared:
        reasons.append('phone_exact_shared')
    for r in tier1_reasons:
        reasons.append(f'tier1_{r}')
    if cat_compat == 'same':
        reasons.append('same_category')
    elif cat_compat == 'compatible':
        reasons.append('compatible_category')
    elif has_category_conflict:
        reasons.append('category_mismatch')
    if aux_score > 0:
        reasons.append(f'aux_{aux_score:.0f}')

    return {
        'name_score': round(name_sim, 1),
        'distance_score': round(dist_score, 1),
        'category_score': round(effective_cat_score, 1),
        'phone_score': round(effective_phone_sc, 1),
        'auxiliary_score': round(aux_score, 1),
        'final_score': round(final, 1),
        'match_status': status,
        'match_reasons': reasons,
        'distance_m': round(distance_m, 1),
        'tier1_match': tier1_match,
    }


# ═══════════════════════════════════════════
#  SPATIAL UTILITIES
# ═══════════════════════════════════════════

def haversine_m(lat1, lon1, lat2, lon2):
    """Distance in meters between two lat/lon points."""
    R = 6371000
    to_rad = math.pi / 180
    dLat = (lat2 - lat1) * to_rad
    dLon = (lon2 - lon1) * to_rad
    a = (math.sin(dLat / 2) ** 2 +
         math.cos(lat1 * to_rad) * math.cos(lat2 * to_rad) *
         math.sin(dLon / 2) ** 2)
    return 2 * R * math.asin(min(1, math.sqrt(a)))


# ═══════════════════════════════════════════
#  MAIN DETECTION ENTRY POINT
# ═══════════════════════════════════════════

def detect_duplicates(pois, max_distance=100, match_threshold=85,
                      possible_threshold=70, include_possible=True):
    """Detect duplicate POIs using hybrid weighted scoring with gated pipeline.

    Args:
        pois: List of POI dicts (must have GlobalID, Name_EN, Name_AR,
              Phone_Number, Category, Latitude, Longitude, etc.)
        max_distance: Maximum distance in meters for candidate generation.
        match_threshold: Score >= this → MATCH.
        possible_threshold: Score >= this → POSSIBLE_MATCH.
        include_possible: Whether to include POSSIBLE_MATCH in results.

    Returns:
        Dict with duplicate_groups, match_pairs, possible_match_pairs,
        total_groups, total_pois_in_groups, thresholds.
    """
    # Parse and pre-normalize all POIs
    parsed = []
    bins = {}
    phone_counter = Counter()  # count phone frequency across all POIs
    license_counter = Counter()  # count license frequency across all POIs

    for p in pois:
        try:
            lat = float(p.get('Latitude') or 0)
            lon = float(p.get('Longitude') or 0)
        except (ValueError, TypeError):
            lat = lon = 0

        phone_norm = normalize_phone(p.get('Phone_Number', ''))
        if phone_norm:
            phone_counter[phone_norm] += 1
        license_norm = normalize_license(p.get('Commercial_License', ''))
        if license_norm:
            license_counter[license_norm] += 1

        entry = {
            'poi': p,
            'lat': lat,
            'lon': lon,
            'phone_norm': phone_norm,
            'name_en_norm': normalize_english(p.get('Name_EN', '')),
            'name_ar_norm': normalize_arabic(p.get('Name_AR', '')),
            'license_norm': normalize_license(p.get('Commercial_License', '')),
        }
        parsed.append(entry)

        if lat != 0 or lon != 0:
            bk = (int(lat / BIN_SIZE_DEG), int(lon / BIN_SIZE_DEG))
            bins.setdefault(bk, []).append(len(parsed) - 1)

    # Detect duplicate pairs using spatial binning
    all_pairs = []
    used = set()
    groups = []

    min_threshold = possible_threshold if include_possible else match_threshold

    for i, pi in enumerate(parsed):
        if i in used or (pi['lat'] == 0 and pi['lon'] == 0):
            continue

        bLat = int(pi['lat'] / BIN_SIZE_DEG)
        bLon = int(pi['lon'] / BIN_SIZE_DEG)

        # Collect candidates from neighboring bins
        candidates = []
        for dl in (-1, 0, 1):
            for dm in (-1, 0, 1):
                candidates.extend(bins.get((bLat + dl, bLon + dm), []))

        group_members = [i]
        group_details = []

        for j in candidates:
            if j <= i or j in used:
                continue
            pj = parsed[j]
            if pj['lat'] == 0 and pj['lon'] == 0:
                continue

            # Quick distance filter
            try:
                dist = haversine_m(pi['lat'], pi['lon'], pj['lat'], pj['lon'])
            except Exception:
                continue
            if dist > max_distance:
                continue

            # Get phone and license frequencies for this pair
            pf_a = phone_counter.get(pi['phone_norm'], 0) if pi['phone_norm'] else 0
            pf_b = phone_counter.get(pj['phone_norm'], 0) if pj['phone_norm'] else 0
            lf_a = license_counter.get(pi['license_norm'], 0) if pi['license_norm'] else 0
            lf_b = license_counter.get(pj['license_norm'], 0) if pj['license_norm'] else 0

            # Compute full match score with frequency awareness
            result = compute_match_score(
                pi['poi'], pj['poi'], dist,
                phone_freq_a=pf_a, phone_freq_b=pf_b,
                license_freq_a=lf_a, license_freq_b=lf_b,
            )

            # Check if this pair qualifies
            qualifies = result['final_score'] >= min_threshold
            # Tier1 can still qualify if score is at least possible_threshold
            if not qualifies and result['tier1_match']:
                qualifies = result['final_score'] >= possible_threshold
            if not qualifies:
                continue

            # Build pair record
            pair = {
                'source_gid': pi['poi'].get('GlobalID', ''),
                'candidate_gid': pj['poi'].get('GlobalID', ''),
                'source_name': pi['poi'].get('Name_EN', '') or pi['poi'].get('Name_AR', ''),
                'candidate_name': pj['poi'].get('Name_EN', '') or pj['poi'].get('Name_AR', ''),
                'source_category': pi['poi'].get('Category', ''),
                'candidate_category': pj['poi'].get('Category', ''),
                'source_lat': pi['lat'],
                'source_lng': pi['lon'],
                'candidate_lat': pj['lat'],
                'candidate_lng': pj['lon'],
            }
            pair.update(result)
            all_pairs.append(pair)

            # Add to group
            group_members.append(j)
            used.add(j)
            group_details.append({
                'gid': pj['poi'].get('GlobalID', ''),
                **result,
            })

        if len(group_members) > 1:
            used.add(i)
            groups.append({
                'anchor': pi['poi'].get('GlobalID', ''),
                'members': [parsed[idx]['poi'].get('GlobalID', '') for idx in group_members],
                'match_details': group_details,
            })

    # Separate MATCH from POSSIBLE_MATCH
    match_pairs = [p for p in all_pairs if p['match_status'] == 'MATCH']
    possible_pairs = [p for p in all_pairs if p['match_status'] == 'POSSIBLE_MATCH']

    return {
        'duplicate_groups': groups,
        'total_groups': len(groups),
        'total_pois_in_groups': sum(len(g['members']) for g in groups),
        'match_pairs': match_pairs,
        'possible_match_pairs': possible_pairs if include_possible else [],
        'total_pairs': len(all_pairs),
        'thresholds': {
            'match': match_threshold,
            'possible_match': possible_threshold,
            'max_distance': max_distance,
        },
    }
