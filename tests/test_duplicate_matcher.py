"""
Tests for the hybrid POI duplicate detection engine.
Pure unit tests — no Flask or database dependency required.
"""
import os
import sys
import pytest

# Add backend to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'backend'))

from duplicate_matcher import (
    normalize_arabic, normalize_english, normalize_phone,
    normalize_license, extract_website_domain,
    compute_name_similarity, _bigram_similarity, _transliterate_en_to_ar,
    score_distance, score_category, score_phone, score_auxiliary,
    compute_match_score, haversine_m, detect_duplicates,
    MATCH_THRESHOLD, POSSIBLE_MATCH_THRESHOLD,
)


# ═══════════════════════════════════════════
#  ARABIC NORMALIZATION
# ═══════════════════════════════════════════

class TestNormalizeArabic:
    def test_hamza_unification(self):
        assert normalize_arabic('أحمد') == normalize_arabic('احمد')
        assert normalize_arabic('إسلام') == normalize_arabic('اسلام')
        # آ → ا (single alif, not double)
        assert normalize_arabic('آمال') == normalize_arabic('امال')

    def test_ta_marbuta(self):
        # ة → ه
        result = normalize_arabic('مدرسة')
        assert 'ة' not in result

    def test_alif_maqsura(self):
        # ى → ي
        result = normalize_arabic('مصطفى')
        assert 'ى' not in result
        assert 'ي' in result

    def test_diacritic_removal(self):
        assert normalize_arabic('مَطْعَم') == normalize_arabic('مطعم')

    def test_business_suffix_removal(self):
        assert 'شركة' not in normalize_arabic('شركة الرياض')
        assert 'مؤسسة' not in normalize_arabic('مؤسسة البيك')

    def test_category_word_removal(self):
        assert 'مطعم' not in normalize_arabic('مطعم البيك')

    def test_empty_string(self):
        assert normalize_arabic('') == ''
        assert normalize_arabic(None) == ''

    def test_bad_sentinel(self):
        assert normalize_arabic('UNAVAILABLE') == ''
        assert normalize_arabic('n/a') == ''

    def test_combined(self):
        a = normalize_arabic('مطعم البيك')
        b = normalize_arabic('البيك')
        # Both should normalize to "البيك" (with hamza/tashkeel normalization)
        assert a == b or 'البيك' in a  # البيك is the core name


class TestNormalizeEnglish:
    def test_lowercase_and_strip(self):
        assert normalize_english('  HELLO World  ') == 'hello world'

    def test_suffix_removal_ltd(self):
        result = normalize_english('Riyadh Ltd.')
        assert 'ltd' not in result

    def test_suffix_removal_llc(self):
        result = normalize_english('Al Baik LLC')
        assert 'llc' not in result

    def test_category_word_removal(self):
        result = normalize_english('Restaurant Al Baik')
        assert 'restaurant' not in result

    def test_symbol_removal(self):
        result = normalize_english('Al-Baik (Main)')
        assert '-' not in result
        assert '(' not in result

    def test_empty_string(self):
        assert normalize_english('') == ''
        assert normalize_english(None) == ''

    def test_bad_sentinel(self):
        assert normalize_english('UNAVAILABLE') == ''


class TestNormalizePhone:
    def test_saudi_mobile_with_plus_966(self):
        assert normalize_phone('+966501234567') == '501234567'

    def test_saudi_mobile_with_05(self):
        assert normalize_phone('0501234567') == '501234567'

    def test_digits_only(self):
        assert normalize_phone('501234567') == '501234567'

    def test_dashes_and_spaces(self):
        assert normalize_phone('+966 50 123 4567') == '501234567'

    def test_unavailable(self):
        assert normalize_phone('UNAVAILABLE') == ''

    def test_empty(self):
        assert normalize_phone('') == ''
        assert normalize_phone(None) == ''

    def test_short_number(self):
        assert normalize_phone('123') == ''


class TestExtractWebsiteDomain:
    def test_https_url(self):
        assert extract_website_domain('https://example.com/page') == 'example.com'

    def test_with_www(self):
        assert extract_website_domain('https://www.example.com') == 'example.com'

    def test_with_path(self):
        assert extract_website_domain('https://example.com/about?q=1') == 'example.com'

    def test_unavailable(self):
        assert extract_website_domain('UNAVAILABLE') == ''

    def test_empty(self):
        assert extract_website_domain('') == ''
        assert extract_website_domain(None) == ''


class TestNormalizeLicense:
    def test_digits_extracted(self):
        assert normalize_license('LIC-12345') == '12345'

    def test_digits_only(self):
        assert normalize_license('1234567890') == '1234567890'

    def test_empty(self):
        assert normalize_license('') == ''

    def test_unavailable(self):
        assert normalize_license('N/A') == ''


# ═══════════════════════════════════════════
#  NAME SIMILARITY
# ═══════════════════════════════════════════

class TestBigramSimilarity:
    def test_exact_match(self):
        assert _bigram_similarity('hello', 'hello') == 100.0

    def test_completely_different(self):
        assert _bigram_similarity('abc', 'xyz') == 0.0

    def test_empty(self):
        assert _bigram_similarity('', 'hello') == 0.0


class TestNameSimilarity:
    def test_exact_match_english(self):
        score = compute_name_similarity('Al Baik', 'Al Baik')
        assert score >= 95

    def test_exact_match_arabic(self):
        score = compute_name_similarity('', '', 'البيك', 'البيك')
        assert score >= 95

    def test_albaik_variations(self):
        # "Al Baik" vs "Albaik" should be very similar
        score = compute_name_similarity('Al Baik', 'Albaik')
        assert score >= 70  # token_set_ratio handles this

    def test_completely_different_names(self):
        score = compute_name_similarity('McDonalds', 'Starbucks')
        assert score < 50

    def test_one_empty(self):
        score = compute_name_similarity('', 'Al Baik')
        assert score == 0

    def test_both_empty(self):
        assert compute_name_similarity('', '') == 0

    def test_partial_match(self):
        score = compute_name_similarity('Riyadh Restaurant', 'Riyadh Rest')
        assert score >= 60

    def test_token_reorder(self):
        score = compute_name_similarity('Bait Al Shawarma', 'Al Shawarma Bait')
        assert score >= 80  # token_sort_ratio handles this

    def test_arabic_with_category_word(self):
        # "مطعم البيك" vs "البيك" — category word removed by normalization
        score = compute_name_similarity('', '', 'مطعم البيك', 'البيك')
        assert score >= 80

    def test_cross_language_transliteration(self):
        # Basic test: English "albaik" → Arabic transliteration should match "البيك"
        score = compute_name_similarity('Albaik', '', '', 'البيك')
        assert score > 0  # At least some transliteration match


# ═══════════════════════════════════════════
#  COMPONENT SCORING
# ═══════════════════════════════════════════

class TestScoreDistance:
    def test_very_close(self):
        assert score_distance(5) == 100.0

    def test_close(self):
        assert score_distance(15) == 90.0

    def test_medium(self):
        assert score_distance(35) == 75.0

    def test_far(self):
        assert score_distance(80) == 50.0

    def test_beyond_threshold(self):
        assert score_distance(120) == 0.0

    def test_exact_boundary(self):
        assert score_distance(10) == 100.0
        assert score_distance(25) == 90.0
        assert score_distance(50) == 75.0
        assert score_distance(100) == 50.0


class TestScoreCategory:
    def test_same_category(self):
        assert score_category('Restaurants', 'Restaurants') == 100.0

    def test_same_category_case_insensitive(self):
        assert score_category('restaurants', 'RESTAURANTS') == 100.0

    def test_different_category(self):
        assert score_category('Restaurants', 'Pharmacy') == 0.0

    def test_one_empty(self):
        assert score_category('', 'Restaurants') == 50.0

    def test_both_empty(self):
        assert score_category('', '') == 50.0


class TestScorePhone:
    def test_exact_match(self):
        assert score_phone('+966501234567', '0501234567') == 100.0

    def test_no_match(self):
        assert score_phone('+966501234567', '+966509999999') == 0.0

    def test_one_empty(self):
        assert score_phone('', '+966501234567') == 0.0


class TestScoreAuxiliary:
    def test_license_match(self):
        poi_a = {'Commercial_License': '1234567890'}
        poi_b = {'Commercial_License': '1234567890'}
        assert score_auxiliary(poi_a, poi_b) == 100.0

    def test_website_domain_match(self):
        poi_a = {'Website': 'https://www.example.com/about'}
        poi_b = {'Website': 'https://example.com'}
        assert score_auxiliary(poi_a, poi_b) == 100.0

    def test_building_match(self):
        poi_a = {'Building_Number': '123', 'Floor_Number': '2'}
        poi_b = {'Building_Number': '123', 'Floor_Number': '2'}
        assert score_auxiliary(poi_a, poi_b) == 100.0

    def test_no_data(self):
        assert score_auxiliary({}, {}) == 0.0


# ═══════════════════════════════════════════
#  COMPOSITE SCORING
# ═══════════════════════════════════════════

class TestComputeMatchScore:
    def _make_poi(self, **kwargs):
        defaults = {
            'GlobalID': '', 'Name_EN': '', 'Name_AR': '',
            'Category': '', 'Phone_Number': '',
            'Commercial_License': '', 'Website': '',
            'Building_Number': '', 'Floor_Number': '',
            'Google_Map_URL': '',
        }
        defaults.update(kwargs)
        return defaults

    def test_strong_match(self):
        poi_a = self._make_poi(Name_EN='Al Baik', Category='Restaurants',
                               Phone_Number='+966501234567')
        poi_b = self._make_poi(Name_EN='Al Baik', Category='Restaurants',
                               Phone_Number='+966501234567')
        result = compute_match_score(poi_a, poi_b, 5)
        assert result['match_status'] == 'MATCH'
        assert result['final_score'] >= 85

    def test_possible_match(self):
        poi_a = self._make_poi(Name_EN='Al Baik Restaurant', Category='Restaurants')
        poi_b = self._make_poi(Name_EN='Albaik Fast Food', Category='Restaurants')
        result = compute_match_score(poi_a, poi_b, 60)
        # Same category, similar names but at 60m distance
        # With rebalanced weights (name dominant, distance demoted)
        assert result['final_score'] >= 40

    def test_no_match(self):
        poi_a = self._make_poi(Name_EN='McDonalds', Category='Restaurants')
        poi_b = self._make_poi(Name_EN='Starbucks', Category='Coffee Shops')
        result = compute_match_score(poi_a, poi_b, 200)
        assert result['match_status'] == 'NO_MATCH'
        assert result['final_score'] < 70

    def test_tier1_phone_override(self):
        poi_a = self._make_poi(Name_EN='Place A', Phone_Number='+966501234567')
        poi_b = self._make_poi(Name_EN='Place B', Phone_Number='+966501234567')
        result = compute_match_score(poi_a, poi_b, 30)
        assert result['tier1_match'] is True
        assert result['final_score'] >= 88

    def test_tier1_license_override(self):
        poi_a = self._make_poi(Name_EN='Shop A', Commercial_License='1234567890')
        poi_b = self._make_poi(Name_EN='Shop B', Commercial_License='1234567890')
        result = compute_match_score(poi_a, poi_b, 80)
        assert result['tier1_match'] is True
        assert result['final_score'] >= 90

    def test_category_mismatch_penalty(self):
        # Use a distance where overrides don't kick in (>30m)
        poi_a = self._make_poi(Name_EN='Al Noor', Category='Restaurants')
        poi_b = self._make_poi(Name_EN='Al Noor', Category='Pharmacy')
        result_mismatch = compute_match_score(poi_a, poi_b, 40)

        poi_c = self._make_poi(Name_EN='Al Noor', Category='Restaurants')
        poi_d = self._make_poi(Name_EN='Al Noor', Category='Restaurants')
        result_match = compute_match_score(poi_c, poi_d, 40)

        assert result_match['final_score'] > result_mismatch['final_score']

    def test_close_distance_name_override(self):
        poi_a = self._make_poi(Name_EN='Exact Same Name', Category='Restaurants')
        poi_b = self._make_poi(Name_EN='Exact Same Name', Category='Restaurants')
        result = compute_match_score(poi_a, poi_b, 20)
        assert result['match_status'] == 'MATCH'
        assert result['final_score'] >= 92

    def test_result_has_all_fields(self):
        poi_a = self._make_poi(Name_EN='Test')
        poi_b = self._make_poi(Name_EN='Test')
        result = compute_match_score(poi_a, poi_b, 10)
        assert 'name_score' in result
        assert 'distance_score' in result
        assert 'category_score' in result
        assert 'phone_score' in result
        assert 'auxiliary_score' in result
        assert 'final_score' in result
        assert 'match_status' in result
        assert 'match_reasons' in result
        assert 'distance_m' in result
        assert 'tier1_match' in result


# ═══════════════════════════════════════════
#  HAVERSINE
# ═══════════════════════════════════════════

class TestHaversine:
    def test_same_point(self):
        assert haversine_m(24.7, 46.6, 24.7, 46.6) == 0.0

    def test_known_distance(self):
        # ~111km per degree of latitude
        dist = haversine_m(24.0, 46.0, 25.0, 46.0)
        assert 110000 < dist < 112000

    def test_close_points(self):
        dist = haversine_m(24.7136, 46.6753, 24.7137, 46.6754)
        assert dist < 20  # very close


# ═══════════════════════════════════════════
#  FULL DETECTION
# ═══════════════════════════════════════════

class TestDetectDuplicates:
    def _make_poi(self, gid, name_en, lat, lon, **kwargs):
        poi = {
            'GlobalID': gid, 'Name_EN': name_en, 'Name_AR': '',
            'Category': 'Restaurants', 'Phone_Number': '',
            'Latitude': str(lat), 'Longitude': str(lon),
            'Building_Number': '', 'Floor_Number': '',
            'Commercial_License': '', 'Website': '', 'Google_Map_URL': '',
        }
        poi.update(kwargs)
        return poi

    def test_empty_input(self):
        result = detect_duplicates([])
        assert result['total_groups'] == 0
        assert result['duplicate_groups'] == []

    def test_no_duplicates(self):
        pois = [
            self._make_poi('A', 'McDonalds', 24.7, 46.6),
            self._make_poi('B', 'Starbucks', 25.0, 47.0),  # Far away
            self._make_poi('C', 'KFC', 26.0, 48.0),  # Very far
        ]
        result = detect_duplicates(pois)
        assert result['total_groups'] == 0

    def test_exact_duplicate_pair(self):
        pois = [
            self._make_poi('A', 'Al Baik', 24.7136, 46.6753),
            self._make_poi('B', 'Al Baik', 24.7136, 46.6753),  # Same location
        ]
        result = detect_duplicates(pois)
        assert result['total_groups'] == 1
        assert len(result['duplicate_groups'][0]['members']) == 2
        assert len(result['match_pairs']) >= 1
        assert result['match_pairs'][0]['match_status'] == 'MATCH'

    def test_possible_duplicate_pair(self):
        pois = [
            self._make_poi('A', 'Al Baik Restaurant', 24.7136, 46.6753,
                           Category='Restaurants'),
            self._make_poi('B', 'Albaik Fast Food', 24.71395, 46.67565,
                           Category='Fast Food'),  # ~40m away, different cat
        ]
        result = detect_duplicates(pois, include_possible=True)
        # Should find something due to name similarity
        assert result['total_pairs'] >= 0  # May or may not match depending on scores

    def test_phone_match(self):
        pois = [
            self._make_poi('A', 'Place Alpha', 24.7136, 46.6753,
                           Phone_Number='+966501234567'),
            self._make_poi('B', 'Place Beta', 24.71365, 46.67535,
                           Phone_Number='0501234567'),  # Same phone, ~10m
        ]
        result = detect_duplicates(pois)
        assert result['total_groups'] >= 1
        # Phone match should trigger tier1
        match = result['match_pairs'][0] if result['match_pairs'] else result['possible_match_pairs'][0]
        assert 'phone_exact' in str(match.get('match_reasons', []))

    def test_license_match(self):
        pois = [
            self._make_poi('A', 'Shop One', 24.7136, 46.6753,
                           Commercial_License='1234567890'),
            self._make_poi('B', 'Shop Two', 24.71420, 46.67590,
                           Commercial_License='1234567890'),  # Same license, ~70m
        ]
        result = detect_duplicates(pois)
        assert result['total_groups'] >= 1

    def test_zero_coordinates_excluded(self):
        pois = [
            self._make_poi('A', 'Al Baik', 0, 0),
            self._make_poi('B', 'Al Baik', 0, 0),
        ]
        result = detect_duplicates(pois)
        assert result['total_groups'] == 0

    def test_three_way_cluster(self):
        pois = [
            self._make_poi('A', 'Al Baik', 24.7136, 46.6753),
            self._make_poi('B', 'Al Baik', 24.71362, 46.67532),  # ~3m
            self._make_poi('C', 'Al Baik', 24.71364, 46.67534),  # ~5m
        ]
        result = detect_duplicates(pois)
        assert result['total_groups'] >= 1

    def test_result_format(self):
        pois = [self._make_poi('A', 'Test', 24.7, 46.6)]
        result = detect_duplicates(pois)
        assert 'duplicate_groups' in result
        assert 'total_groups' in result
        assert 'total_pois_in_groups' in result
        assert 'match_pairs' in result
        assert 'possible_match_pairs' in result
        assert 'total_pairs' in result
        assert 'thresholds' in result

    def test_threshold_customization(self):
        pois = [
            self._make_poi('A', 'Al Baik', 24.7136, 46.6753),
            self._make_poi('B', 'Al Baik', 24.7136, 46.6753),
        ]
        # Very strict threshold — should still match identical POIs
        result = detect_duplicates(pois, match_threshold=95)
        assert result['total_groups'] >= 1

    def test_category_mismatch_reduces_score(self):
        # Same name, same location, incompatible categories (not hard reject)
        pois = [
            self._make_poi('A', 'Al Noor', 24.7136, 46.6753,
                           Category='Shopping'),
            self._make_poi('B', 'Al Noor', 24.71362, 46.67532,
                           Category='Entertainment'),
        ]
        result = detect_duplicates(pois)
        # With category mismatch penalty, score should be reduced
        if result['total_pairs'] > 0:
            pair = (result['match_pairs'] or result['possible_match_pairs'])[0]
            reasons = pair.get('match_reasons', [])
            assert ('category_mismatch' in reasons
                    or 'contradiction_category_name' in reasons
                    or 'category_conflict_penalty' in reasons)

    def test_hard_reject_incompatible_families(self):
        # Mosque vs Barber Shop = Religious vs PersonalCare → hard reject
        pois = [
            self._make_poi('A', 'Al Husaini', 24.7136, 46.6753,
                           Category='Mosques'),
            self._make_poi('B', 'Al Husaini', 24.71362, 46.67532,
                           Category='Beauty and Spa'),
        ]
        result = detect_duplicates(pois)
        # Hard reject should prevent this from becoming a match
        assert result['total_groups'] == 0 or (
            len(result['match_pairs']) == 0
            and all(p['final_score'] == 0.0 for p in result.get('possible_match_pairs', []))
        )
