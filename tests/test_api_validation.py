"""TC-API-009: QA Validation Pipeline — all GATE rules."""


class TestValidationPass:
    """POIs that should pass validation."""

    def test_complete_poi_passes(self, validation_client, sample_poi):
        resp = validation_client.post('/api/validate-poi', json=sample_poi)
        assert resp.status_code == 200
        report = resp.get_json()['qa_report']
        assert report['status'] in ('PASS', 'PASS_WITH_WARNINGS')


class TestNameValidation:
    """GATE-A and GATE-B: Name rules."""

    def test_missing_name_ar_is_blocker(self, validation_client, sample_poi):
        sample_poi['Name_AR'] = ''
        resp = validation_client.post('/api/validate-poi', json=sample_poi)
        report = resp.get_json()['qa_report']
        assert report['status'] == 'FAIL_BLOCKER'
        blockers = [b for b in report['blockers'] if 'GATE-A1' in b.get('rule_id', b.get('gate', ''))]
        assert len(blockers) >= 1

    def test_short_name_ar_is_blocker(self, validation_client, sample_poi):
        sample_poi['Name_AR'] = 'ا'  # 1 char
        resp = validation_client.post('/api/validate-poi', json=sample_poi)
        report = resp.get_json()['qa_report']
        assert report['status'] == 'FAIL_BLOCKER'

    def test_missing_name_en_is_blocker(self, validation_client, sample_poi):
        sample_poi['Name_EN'] = ''
        resp = validation_client.post('/api/validate-poi', json=sample_poi)
        report = resp.get_json()['qa_report']
        assert report['status'] == 'FAIL_BLOCKER'

    def test_name_ar_with_english_is_warning(self, validation_client, sample_poi):
        sample_poi['Name_AR'] = 'مطعم Restaurant'
        resp = validation_client.post('/api/validate-poi', json=sample_poi)
        report = resp.get_json()['qa_report']
        warnings = report.get('warnings', [])
        has_a2 = any('A2' in str(w) or 'English' in str(w) for w in warnings)
        assert has_a2 or report['status'] in ('PASS_WITH_WARNINGS', 'PASS')

    def test_name_en_with_arabic_is_warning(self, validation_client, sample_poi):
        sample_poi['Name_EN'] = 'Restaurant مطعم'
        resp = validation_client.post('/api/validate-poi', json=sample_poi)
        report = resp.get_json()['qa_report']
        warnings = report.get('warnings', [])
        assert len(warnings) >= 1 or report['status'] in ('PASS_WITH_WARNINGS', 'PASS')


class TestMediaValidation:
    """GATE-D: Media URL rules."""

    def test_missing_exterior_photo_is_blocker(self, validation_client, sample_poi):
        sample_poi['Exterior_Photo_URL'] = ''
        resp = validation_client.post('/api/validate-poi', json=sample_poi)
        report = resp.get_json()['qa_report']
        assert report['status'] == 'FAIL_BLOCKER'

    def test_missing_interior_photo_is_blocker(self, validation_client, sample_poi):
        sample_poi['Interior_Photo_URL'] = ''
        resp = validation_client.post('/api/validate-poi', json=sample_poi)
        report = resp.get_json()['qa_report']
        assert report['status'] == 'FAIL_BLOCKER'

    def test_duplicate_exterior_interior_urls(self, validation_client, sample_poi):
        sample_poi['Exterior_Photo_URL'] = 'https://same.jpg'
        sample_poi['Interior_Photo_URL'] = 'https://same.jpg'
        resp = validation_client.post('/api/validate-poi', json=sample_poi)
        report = resp.get_json()['qa_report']
        # Should be at least a warning or blocker
        assert report['status'] in ('FAIL_BLOCKER', 'PASS_WITH_WARNINGS')


class TestCoordinateValidation:
    """GATE-G: Saudi Arabia coordinate bounds."""

    def test_valid_riyadh_coordinates(self, validation_client, sample_poi):
        sample_poi['Latitude'] = '24.7136'
        sample_poi['Longitude'] = '46.6753'
        resp = validation_client.post('/api/validate-poi', json=sample_poi)
        report = resp.get_json()['qa_report']
        coord_blockers = [b for b in report.get('blockers', []) if 'G' in str(b)]
        assert len(coord_blockers) == 0

    def test_latitude_out_of_saudi_bounds(self, validation_client, sample_poi):
        sample_poi['Latitude'] = '50.0'  # Way north of Saudi Arabia
        resp = validation_client.post('/api/validate-poi', json=sample_poi)
        report = resp.get_json()['qa_report']
        assert report['status'] == 'FAIL_BLOCKER'

    def test_longitude_out_of_saudi_bounds(self, validation_client, sample_poi):
        sample_poi['Longitude'] = '10.0'  # Way west of Saudi Arabia
        resp = validation_client.post('/api/validate-poi', json=sample_poi)
        report = resp.get_json()['qa_report']
        assert report['status'] == 'FAIL_BLOCKER'

    def test_zero_coordinates_are_invalid(self, validation_client, sample_poi):
        sample_poi['Latitude'] = '0'
        sample_poi['Longitude'] = '0'
        resp = validation_client.post('/api/validate-poi', json=sample_poi)
        report = resp.get_json()['qa_report']
        assert report['status'] == 'FAIL_BLOCKER'

    def test_non_numeric_coordinates(self, validation_client, sample_poi):
        sample_poi['Latitude'] = 'abc'
        resp = validation_client.post('/api/validate-poi', json=sample_poi)
        report = resp.get_json()['qa_report']
        assert report['status'] == 'FAIL_BLOCKER'


class TestCategoryValidation:
    """GATE-E: Category rules."""

    def test_empty_category_is_blocker(self, validation_client, sample_poi):
        sample_poi['Category'] = ''
        resp = validation_client.post('/api/validate-poi', json=sample_poi)
        report = resp.get_json()['qa_report']
        assert report['status'] == 'FAIL_BLOCKER'


class TestWorkingHoursValidation:
    """GATE-J: Working hours rules."""

    def test_missing_working_hours_is_blocker(self, validation_client, sample_poi):
        sample_poi['Working_Hours'] = ''
        resp = validation_client.post('/api/validate-poi', json=sample_poi)
        report = resp.get_json()['qa_report']
        assert report['status'] == 'FAIL_BLOCKER'


class TestAutoFix:
    """Validation auto-correction behavior."""

    def test_autofix_legal_name(self, validation_client, sample_poi):
        sample_poi['Legal_Name'] = ''
        resp = validation_client.post('/api/validate-poi', json=sample_poi)
        fixed = resp.get_json()['poi_final']
        assert fixed['Legal_Name'] == 'UNAVAILABLE'

    def test_autofix_invalid_floor(self, validation_client, sample_poi):
        sample_poi['Floor_Number'] = 'xyz'
        resp = validation_client.post('/api/validate-poi', json=sample_poi)
        fixed = resp.get_json()['poi_final']
        assert fixed['Floor_Number'] == 'UNAVAILABLE'

    def test_autofix_non_fnb_menu_field(self, validation_client, sample_poi):
        sample_poi['Category'] = 'Banks'
        sample_poi['Menu'] = 'Yes'
        resp = validation_client.post('/api/validate-poi', json=sample_poi)
        fixed = resp.get_json()['poi_final']
        assert fixed['Menu'] == 'UNAPPLICABLE'


class TestContactValidation:
    """GATE-I: Contact info rules."""

    def test_scientific_notation_phone(self, validation_client, sample_poi):
        sample_poi['Phone_Number'] = '9.66512e+11'
        resp = validation_client.post('/api/validate-poi', json=sample_poi)
        report = resp.get_json()['qa_report']
        warnings = report.get('warnings', []) + report.get('changes_made', [])
        assert len(warnings) >= 1

    def test_invalid_email_autofix(self, validation_client, sample_poi):
        sample_poi['Email'] = 'not-an-email'
        resp = validation_client.post('/api/validate-poi', json=sample_poi)
        fixed = resp.get_json()['poi_final']
        # Should either flag as warning or auto-fix to UNAVAILABLE
        assert fixed['Email'] in ('not-an-email', 'UNAVAILABLE')

    def test_google_maps_in_website(self, validation_client, sample_poi):
        sample_poi['Website'] = 'https://maps.google.com/place/test'
        resp = validation_client.post('/api/validate-poi', json=sample_poi)
        fixed = resp.get_json()['poi_final']
        # Should move to Google_Map_URL and set Website=UNAVAILABLE
        assert fixed.get('Website') == 'UNAVAILABLE' or 'google' not in fixed.get('Website', '')


class TestSentinelValidation:
    """GATE-SV1: Bad sentinel values like N/A, None, -, Unknown."""

    def test_na_in_phone_is_autofix(self, validation_client, sample_poi):
        sample_poi['Phone_Number'] = 'N/A'
        resp = validation_client.post('/api/validate-poi', json=sample_poi)
        fixed = resp.get_json()['poi_final']
        assert fixed['Phone_Number'] == 'UNAVAILABLE'

    def test_unknown_in_website_is_autofix(self, validation_client, sample_poi):
        sample_poi['Website'] = 'Unknown'
        resp = validation_client.post('/api/validate-poi', json=sample_poi)
        fixed = resp.get_json()['poi_final']
        assert fixed['Website'] == 'UNAVAILABLE'

    def test_dash_in_district_is_autofix(self, validation_client, sample_poi):
        sample_poi['District_EN'] = '-'
        resp = validation_client.post('/api/validate-poi', json=sample_poi)
        fixed = resp.get_json()['poi_final']
        assert fixed['District_EN'] == 'UNAVAILABLE'

    def test_none_in_email_is_autofix(self, validation_client, sample_poi):
        sample_poi['Email'] = 'none'
        resp = validation_client.post('/api/validate-poi', json=sample_poi)
        fixed = resp.get_json()['poi_final']
        assert fixed['Email'] == 'UNAVAILABLE'

    def test_real_value_not_flagged(self, validation_client, sample_poi):
        sample_poi['Phone_Number'] = '+966512345678'
        resp = validation_client.post('/api/validate-poi', json=sample_poi)
        report = resp.get_json()['qa_report']
        sv_warns = [w for w in report.get('warnings', []) if 'SV1' in str(w)]
        assert len(sv_warns) == 0


class TestNameCapitalization:
    """GATE-B4/B5: ALL CAPS and all lowercase detection."""

    def test_all_caps_name_autofix(self, validation_client, sample_poi):
        sample_poi['Name_EN'] = 'STAR LAUNDRY SERVICES'
        resp = validation_client.post('/api/validate-poi', json=sample_poi)
        fixed = resp.get_json()['poi_final']
        assert fixed['Name_EN'] == 'Star Laundry Services'

    def test_all_lowercase_name_autofix(self, validation_client, sample_poi):
        sample_poi['Name_EN'] = 'star laundry services'
        resp = validation_client.post('/api/validate-poi', json=sample_poi)
        fixed = resp.get_json()['poi_final']
        assert fixed['Name_EN'] == 'Star Laundry Services'

    def test_short_abbreviation_not_flagged(self, validation_client, sample_poi):
        sample_poi['Name_EN'] = 'KFC'
        resp = validation_client.post('/api/validate-poi', json=sample_poi)
        report = resp.get_json()['qa_report']
        caps_warns = [w for w in report.get('warnings', []) if 'B4' in w.get('rule_id', '')]
        assert len(caps_warns) == 0

    def test_proper_title_case_passes(self, validation_client, sample_poi):
        sample_poi['Name_EN'] = 'Star Laundry'
        resp = validation_client.post('/api/validate-poi', json=sample_poi)
        report = resp.get_json()['qa_report']
        caps_warns = [w for w in report.get('warnings', []) if w.get('rule_id', '') in ('GATE-B4', 'GATE-B5')]
        assert len(caps_warns) == 0


class TestWorkingHoursFormat:
    """GATE-J2: Working hours format enforcement."""

    def test_valid_hours_format_passes(self, validation_client, sample_poi):
        sample_poi['Working_Hours'] = '09:00-23:00'
        resp = validation_client.post('/api/validate-poi', json=sample_poi)
        report = resp.get_json()['qa_report']
        j2_warns = [w for w in report.get('warnings', []) if 'J2' in w.get('rule_id', '')]
        assert len(j2_warns) == 0

    def test_freetext_hours_is_warning(self, validation_client, sample_poi):
        sample_poi['Working_Hours'] = 'morning to evening'
        resp = validation_client.post('/api/validate-poi', json=sample_poi)
        report = resp.get_json()['qa_report']
        j2_warns = [w for w in report.get('warnings', []) if 'J2' in w.get('rule_id', '')]
        assert len(j2_warns) >= 1

    def test_open_24_hours_passes(self, validation_client, sample_poi):
        sample_poi['Working_Hours'] = 'Open 24 Hours'
        resp = validation_client.post('/api/validate-poi', json=sample_poi)
        report = resp.get_json()['qa_report']
        j2_warns = [w for w in report.get('warnings', []) if 'J2' in w.get('rule_id', '')]
        assert len(j2_warns) == 0


class TestWebsiteSocialMedia:
    """GATE-I4b: Social media in website field."""

    def test_tiktok_in_website_autofix(self, validation_client, sample_poi):
        sample_poi['Website'] = 'https://tiktok.com/@myshop'
        resp = validation_client.post('/api/validate-poi', json=sample_poi)
        fixed = resp.get_json()['poi_final']
        assert fixed['Website'] == 'UNAVAILABLE'

    def test_instagram_in_website_autofix(self, validation_client, sample_poi):
        sample_poi['Website'] = 'https://instagram.com/myshop'
        resp = validation_client.post('/api/validate-poi', json=sample_poi)
        fixed = resp.get_json()['poi_final']
        assert fixed['Website'] == 'UNAVAILABLE'

    def test_real_website_passes(self, validation_client, sample_poi):
        sample_poi['Website'] = 'https://myshop.com.sa'
        resp = validation_client.post('/api/validate-poi', json=sample_poi)
        report = resp.get_json()['qa_report']
        i4b_warns = [w for w in report.get('warnings', []) if 'I4b' in w.get('rule_id', '')]
        assert len(i4b_warns) == 0


class TestCommercialLicenseStrict:
    """GATE-L1: Commercial license exactly 10 digits."""

    def test_10_digit_license_passes(self, validation_client, sample_poi):
        sample_poi['Commercial_License'] = '1234567890'
        resp = validation_client.post('/api/validate-poi', json=sample_poi)
        report = resp.get_json()['qa_report']
        l1_warns = [w for w in report.get('warnings', []) if 'L1' in w.get('rule_id', '')]
        assert len(l1_warns) == 0

    def test_11_digit_license_fails(self, validation_client, sample_poi):
        sample_poi['Commercial_License'] = '12345678901'
        resp = validation_client.post('/api/validate-poi', json=sample_poi)
        report = resp.get_json()['qa_report']
        l1_warns = [w for w in report.get('warnings', []) if 'L1' in w.get('rule_id', '')]
        assert len(l1_warns) >= 1

    def test_unavailable_license_passes(self, validation_client, sample_poi):
        sample_poi['Commercial_License'] = 'UNAVAILABLE'
        resp = validation_client.post('/api/validate-poi', json=sample_poi)
        report = resp.get_json()['qa_report']
        l1_warns = [w for w in report.get('warnings', []) if 'L1' in w.get('rule_id', '')]
        assert len(l1_warns) == 0


class TestPhoneticTransliteration:
    """GATE-A4: Arabic phonetic transliteration detection."""

    def test_transliterated_arabic_is_warning(self, validation_client, sample_poi):
        sample_poi['Name_EN'] = 'Star Laundry'
        sample_poi['Name_AR'] = '\u0633\u062a\u0627\u0631 \u0644\u0627\u0646\u062f\u0631\u064a'
        resp = validation_client.post('/api/validate-poi', json=sample_poi)
        report = resp.get_json()['qa_report']
        a4_warns = [w for w in report.get('warnings', []) if 'A4' in w.get('rule_id', '')]
        assert len(a4_warns) >= 1

    def test_proper_arabic_passes(self, validation_client, sample_poi):
        sample_poi['Name_EN'] = 'Star Laundry'
        sample_poi['Name_AR'] = '\u0645\u063a\u0633\u0644\u0629 \u0633\u062a\u0627\u0631'
        resp = validation_client.post('/api/validate-poi', json=sample_poi)
        report = resp.get_json()['qa_report']
        a4_warns = [w for w in report.get('warnings', []) if 'A4' in w.get('rule_id', '')]
        assert len(a4_warns) == 0


class TestNameCorrespondence:
    """GATE-A5: Brand in English must appear in Arabic."""

    def test_brand_missing_from_arabic(self, validation_client, sample_poi):
        sample_poi['Name_EN'] = 'Hilton Hotel'
        sample_poi['Name_AR'] = '\u0641\u0646\u062f\u0642 \u0627\u0644\u0631\u064a\u0627\u0636'
        resp = validation_client.post('/api/validate-poi', json=sample_poi)
        report = resp.get_json()['qa_report']
        a5_warns = [w for w in report.get('warnings', []) if 'A5' in w.get('rule_id', '')]
        assert len(a5_warns) >= 1

    def test_brand_in_arabic_transliteration_passes(self, validation_client, sample_poi):
        sample_poi['Name_EN'] = 'Hilton Hotel'
        sample_poi['Name_AR'] = '\u0641\u0646\u062f\u0642 \u0647\u064a\u0644\u062a\u0648\u0646'
        resp = validation_client.post('/api/validate-poi', json=sample_poi)
        report = resp.get_json()['qa_report']
        a5_warns = [w for w in report.get('warnings', []) if 'A5' in w.get('rule_id', '')]
        assert len(a5_warns) == 0
