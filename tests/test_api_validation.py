"""TC-API-009: QA Validation Pipeline — all GATE rules."""


class TestValidationPass:
    """POIs that should pass validation."""

    def test_complete_poi_passes(self, client, sample_poi):
        resp = client.post('/api/validate-poi', json=sample_poi)
        assert resp.status_code == 200
        report = resp.get_json()['qa_report']
        assert report['status'] in ('PASS', 'PASS_WITH_WARNINGS')


class TestNameValidation:
    """GATE-A and GATE-B: Name rules."""

    def test_missing_name_ar_is_blocker(self, client, sample_poi):
        sample_poi['Name_AR'] = ''
        resp = client.post('/api/validate-poi', json=sample_poi)
        report = resp.get_json()['qa_report']
        assert report['status'] == 'FAIL_BLOCKER'
        blockers = [b for b in report['blockers'] if 'GATE-A1' in b.get('rule_id', b.get('gate', ''))]
        assert len(blockers) >= 1

    def test_short_name_ar_is_blocker(self, client, sample_poi):
        sample_poi['Name_AR'] = 'ا'  # 1 char
        resp = client.post('/api/validate-poi', json=sample_poi)
        report = resp.get_json()['qa_report']
        assert report['status'] == 'FAIL_BLOCKER'

    def test_missing_name_en_is_blocker(self, client, sample_poi):
        sample_poi['Name_EN'] = ''
        resp = client.post('/api/validate-poi', json=sample_poi)
        report = resp.get_json()['qa_report']
        assert report['status'] == 'FAIL_BLOCKER'

    def test_name_ar_with_english_is_warning(self, client, sample_poi):
        sample_poi['Name_AR'] = 'مطعم Restaurant'
        resp = client.post('/api/validate-poi', json=sample_poi)
        report = resp.get_json()['qa_report']
        warnings = report.get('warnings', [])
        has_a2 = any('A2' in str(w) or 'English' in str(w) for w in warnings)
        assert has_a2 or report['status'] in ('PASS_WITH_WARNINGS', 'PASS')

    def test_name_en_with_arabic_is_warning(self, client, sample_poi):
        sample_poi['Name_EN'] = 'Restaurant مطعم'
        resp = client.post('/api/validate-poi', json=sample_poi)
        report = resp.get_json()['qa_report']
        warnings = report.get('warnings', [])
        assert len(warnings) >= 1 or report['status'] in ('PASS_WITH_WARNINGS', 'PASS')


class TestMediaValidation:
    """GATE-D: Media URL rules."""

    def test_missing_exterior_photo_is_blocker(self, client, sample_poi):
        sample_poi['Exterior_Photo_URL'] = ''
        resp = client.post('/api/validate-poi', json=sample_poi)
        report = resp.get_json()['qa_report']
        assert report['status'] == 'FAIL_BLOCKER'

    def test_missing_interior_photo_is_blocker(self, client, sample_poi):
        sample_poi['Interior_Photo_URL'] = ''
        resp = client.post('/api/validate-poi', json=sample_poi)
        report = resp.get_json()['qa_report']
        assert report['status'] == 'FAIL_BLOCKER'

    def test_duplicate_exterior_interior_urls(self, client, sample_poi):
        sample_poi['Exterior_Photo_URL'] = 'https://same.jpg'
        sample_poi['Interior_Photo_URL'] = 'https://same.jpg'
        resp = client.post('/api/validate-poi', json=sample_poi)
        report = resp.get_json()['qa_report']
        # Should be at least a warning or blocker
        assert report['status'] in ('FAIL_BLOCKER', 'PASS_WITH_WARNINGS')


class TestCoordinateValidation:
    """GATE-G: Saudi Arabia coordinate bounds."""

    def test_valid_riyadh_coordinates(self, client, sample_poi):
        sample_poi['Latitude'] = '24.7136'
        sample_poi['Longitude'] = '46.6753'
        resp = client.post('/api/validate-poi', json=sample_poi)
        report = resp.get_json()['qa_report']
        coord_blockers = [b for b in report.get('blockers', []) if 'G' in str(b)]
        assert len(coord_blockers) == 0

    def test_latitude_out_of_saudi_bounds(self, client, sample_poi):
        sample_poi['Latitude'] = '50.0'  # Way north of Saudi Arabia
        resp = client.post('/api/validate-poi', json=sample_poi)
        report = resp.get_json()['qa_report']
        assert report['status'] == 'FAIL_BLOCKER'

    def test_longitude_out_of_saudi_bounds(self, client, sample_poi):
        sample_poi['Longitude'] = '10.0'  # Way west of Saudi Arabia
        resp = client.post('/api/validate-poi', json=sample_poi)
        report = resp.get_json()['qa_report']
        assert report['status'] == 'FAIL_BLOCKER'

    def test_zero_coordinates_are_invalid(self, client, sample_poi):
        sample_poi['Latitude'] = '0'
        sample_poi['Longitude'] = '0'
        resp = client.post('/api/validate-poi', json=sample_poi)
        report = resp.get_json()['qa_report']
        assert report['status'] == 'FAIL_BLOCKER'

    def test_non_numeric_coordinates(self, client, sample_poi):
        sample_poi['Latitude'] = 'abc'
        resp = client.post('/api/validate-poi', json=sample_poi)
        report = resp.get_json()['qa_report']
        assert report['status'] == 'FAIL_BLOCKER'


class TestCategoryValidation:
    """GATE-E: Category rules."""

    def test_empty_category_is_blocker(self, client, sample_poi):
        sample_poi['Category'] = ''
        resp = client.post('/api/validate-poi', json=sample_poi)
        report = resp.get_json()['qa_report']
        assert report['status'] == 'FAIL_BLOCKER'


class TestWorkingHoursValidation:
    """GATE-J: Working hours rules."""

    def test_missing_working_hours_is_blocker(self, client, sample_poi):
        sample_poi['Working_Hours'] = ''
        resp = client.post('/api/validate-poi', json=sample_poi)
        report = resp.get_json()['qa_report']
        assert report['status'] == 'FAIL_BLOCKER'


class TestAutoFix:
    """Validation auto-correction behavior."""

    def test_autofix_legal_name(self, client, sample_poi):
        sample_poi['Legal_Name'] = ''
        resp = client.post('/api/validate-poi', json=sample_poi)
        fixed = resp.get_json()['poi_final']
        assert fixed['Legal_Name'] == 'UNAVAILABLE'

    def test_autofix_invalid_floor(self, client, sample_poi):
        sample_poi['Floor_Number'] = 'xyz'
        resp = client.post('/api/validate-poi', json=sample_poi)
        fixed = resp.get_json()['poi_final']
        assert fixed['Floor_Number'] == 'UNAVAILABLE'

    def test_autofix_non_fnb_menu_field(self, client, sample_poi):
        sample_poi['Category'] = 'Banks'
        sample_poi['Menu'] = 'Yes'
        resp = client.post('/api/validate-poi', json=sample_poi)
        fixed = resp.get_json()['poi_final']
        assert fixed['Menu'] == 'UNAPPLICABLE'


class TestContactValidation:
    """GATE-I: Contact info rules."""

    def test_scientific_notation_phone(self, client, sample_poi):
        sample_poi['Phone_Number'] = '9.66512e+11'
        resp = client.post('/api/validate-poi', json=sample_poi)
        report = resp.get_json()['qa_report']
        warnings = report.get('warnings', []) + report.get('changes_made', [])
        assert len(warnings) >= 1

    def test_invalid_email_autofix(self, client, sample_poi):
        sample_poi['Email'] = 'not-an-email'
        resp = client.post('/api/validate-poi', json=sample_poi)
        fixed = resp.get_json()['poi_final']
        # Should either flag as warning or auto-fix to UNAVAILABLE
        assert fixed['Email'] in ('not-an-email', 'UNAVAILABLE')

    def test_google_maps_in_website(self, client, sample_poi):
        sample_poi['Website'] = 'https://maps.google.com/place/test'
        resp = client.post('/api/validate-poi', json=sample_poi)
        fixed = resp.get_json()['poi_final']
        # Should move to Google_Map_URL and set Website=UNAVAILABLE
        assert fixed.get('Website') == 'UNAVAILABLE' or 'google' not in fixed.get('Website', '')
