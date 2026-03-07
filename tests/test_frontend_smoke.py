"""
Frontend smoke tests — verifies the HTML/JS structure is valid
and critical UI elements exist. Does not require a browser.
Parses the HTML file directly.
"""
import os
import re

HTML_PATH = os.path.join(os.path.dirname(__file__), '..', 'POI_FINAL_Review.html')


def _read_html():
    with open(HTML_PATH, 'r', encoding='utf-8') as f:
        return f.read()


class TestHTMLStructure:
    """Verify the HTML file has required elements."""

    def test_file_exists_and_not_empty(self):
        html = _read_html()
        assert len(html) > 1000, 'HTML file is too small — likely corrupted'

    def test_has_doctype(self):
        html = _read_html()
        assert html.strip().startswith('<!DOCTYPE html>')

    def test_has_all_view_divs(self):
        html = _read_html()
        required_views = [
            'cardView', 'excelView', 'auditView',
            'duplicatesView', 'mapView', 'arcgisView', 'invoiceView'
        ]
        for view_id in required_views:
            assert f'id="{view_id}"' in html, f'Missing view div: {view_id}'

    def test_has_login_overlay(self):
        html = _read_html()
        assert 'loginOverlay' in html or 'login-overlay' in html

    def test_has_media_assign_modal(self):
        html = _read_html()
        assert 'mediaAssignModal' in html

    def test_has_detail_panel(self):
        html = _read_html()
        assert 'detailPanel' in html or 'detail-panel' in html


class TestJSFunctions:
    """Verify critical JavaScript functions are defined."""

    def test_core_functions_exist(self):
        html = _read_html()
        required_functions = [
            'init', 'buildUI', 'renderTable', 'applyFilters',
            'openDetail', 'closeDetail', 'saveToDb', 'saveFieldsToDb',
            'switchView', 'validatePoi', 'exportCSV',
        ]
        for fn in required_functions:
            pattern = rf'(function\s+{fn}|{fn}\s*=\s*(async\s+)?function|const\s+{fn}\s*=)'
            assert re.search(pattern, html), f'Missing JS function: {fn}'

    def test_media_functions_exist(self):
        html = _read_html()
        media_functions = [
            'initArcGISMedia', 'buildMediaIndex', 'renderUnassignedMedia',
            'assignMedia', 'openMediaAssign', 'closeMediaAssign',
            'arcImg', 'arcVid', 'createPoiFromSurvey123',
        ]
        for fn in media_functions:
            assert fn in html, f'Missing media function: {fn}'

    def test_auth_functions_exist(self):
        html = _read_html()
        auth_functions = [
            'checkLoginState', 'doLogin', 'skipLogin',
            'logoutReviewer', 'showReviewerBadge',
        ]
        for fn in auth_functions:
            assert fn in html, f'Missing auth function: {fn}'

    def test_audit_functions_exist(self):
        html = _read_html()
        assert 'loadAuditLog' in html
        assert 'loadAuditStats' in html

    def test_duplicate_functions_exist(self):
        html = _read_html()
        assert 'findDuplicates' in html or 'detectDuplicates' in html or 'renderDuplicatesView' in html


class TestJSConstants:
    """Verify critical constants and config."""

    def test_view_map_defined(self):
        html = _read_html()
        assert 'VIEW_MAP' in html
        assert 'VIEW_IDS' in html

    def test_media_types_defined(self):
        html = _read_html()
        assert 'MEDIA_TYPES' in html
        assert 'MEDIA_DB_FIELDS' in html
        assert 'MEDIA_COLORS' in html

    def test_category_taxonomy_defined(self):
        html = _read_html()
        assert 'CATEGORY_TAXONOMY' in html

    def test_pricing_map_defined(self):
        html = _read_html()
        assert 'PRICING_MAP' in html

    def test_review_flags_defined(self):
        html = _read_html()
        assert 'REVIEW_FLAGS' in html


class TestAPIEndpoints:
    """Verify frontend references correct API endpoints."""

    def test_api_pois_endpoint(self):
        html = _read_html()
        assert "'/api/pois'" in html or '"/api/pois"' in html or "fetch('/api/pois" in html

    def test_api_login_endpoint(self):
        html = _read_html()
        assert '/api/login' in html

    def test_api_audit_log_endpoint(self):
        html = _read_html()
        assert '/api/audit-log' in html

    def test_api_validate_endpoint(self):
        html = _read_html()
        assert '/api/validate-poi' in html or 'validate' in html

    def test_catalogue_file_reference(self):
        html = _read_html()
        assert 'arc_catalogue_lite.json' in html


class TestCatalogueLite:
    """Verify the optimized catalogue file."""

    def test_catalogue_exists_and_valid_json(self):
        import json
        cat_path = os.path.join(os.path.dirname(__file__), '..', 'arc_catalogue_lite.json')
        with open(cat_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        assert '_urlBase' in data
        assert 'pois' in data
        assert len(data['pois']) > 0

    def test_catalogue_url_base_valid(self):
        import json
        cat_path = os.path.join(os.path.dirname(__file__), '..', 'arc_catalogue_lite.json')
        with open(cat_path) as f:
            data = json.load(f)
        assert data['_urlBase'].startswith('https://services5.arcgis.com/')
        assert 'FeatureServer' in data['_urlBase']

    def test_catalogue_poi_structure(self):
        import json
        cat_path = os.path.join(os.path.dirname(__file__), '..', 'arc_catalogue_lite.json')
        with open(cat_path) as f:
            data = json.load(f)
        poi = data['pois'][0]
        assert 'g' in poi, 'Missing GlobalID (g) field'
        assert 'a' in poi, 'Missing attachments (a) field'

    def test_catalogue_size_under_500kb(self):
        cat_path = os.path.join(os.path.dirname(__file__), '..', 'arc_catalogue_lite.json')
        size = os.path.getsize(cat_path)
        assert size < 500 * 1024, f'Catalogue is {size/1024:.0f}KB (target: <500KB)'
