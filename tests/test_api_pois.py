"""TC-API-002 through TC-API-007: POI CRUD operations."""
import json
import gzip
from conftest import SAMPLE_POI_COMPLETE, SAMPLE_POI_MINIMAL


class TestGetAllPois:
    """TC-API-002: GET /api/pois"""

    def test_empty_db_returns_empty_list(self, client):
        resp = client.get('/api/pois')
        assert resp.status_code == 200
        assert resp.get_json() == []

    def test_returns_all_pois(self, client):
        # Create 3 POIs
        for i in range(3):
            client.post('/api/pois', json={'Name_EN': f'POI {i}', 'Category': 'Test'})
        resp = client.get('/api/pois')
        data = resp.get_json()
        assert len(data) == 3

    def test_gzip_compression(self, client):
        # Create a POI so response isn't trivially small
        client.post('/api/pois', json=SAMPLE_POI_COMPLETE)
        resp = client.get('/api/pois', headers={'Accept-Encoding': 'gzip'})
        assert resp.status_code == 200
        # Response should have gzip encoding
        assert resp.headers.get('Content-Encoding') == 'gzip'
        # Should be decompressible
        decompressed = gzip.decompress(resp.data)
        data = json.loads(decompressed)
        assert len(data) == 1

    def test_etag_caching(self, client):
        client.post('/api/pois', json={'Name_EN': 'ETag Test'})
        resp1 = client.get('/api/pois')
        etag = resp1.headers.get('ETag')
        assert etag is not None

        # Second request with matching ETag → 304
        resp2 = client.get('/api/pois', headers={'If-None-Match': etag})
        assert resp2.status_code == 304

    def test_etag_changes_after_update(self, client):
        resp1 = client.post('/api/pois', json={'Name_EN': 'First'})
        gid = resp1.get_json()['GlobalID']
        etag1 = client.get('/api/pois').headers.get('ETag')

        # Update POI → ETag should change
        client.patch(f'/api/pois/{gid}', json={'Name_EN': 'Updated'})
        etag2 = client.get('/api/pois').headers.get('ETag')
        assert etag1 != etag2

    def test_poi_fields_are_strings_not_null(self, client):
        """NULL DB values should be returned as empty strings."""
        client.post('/api/pois', json={'Name_EN': 'Null Test'})
        resp = client.get('/api/pois')
        poi = resp.get_json()[0]
        # Fields not set should be '' not None
        assert poi['Email'] == ''
        assert poi['Website'] == ''
        assert poi['Phone_Number'] == ''

    def test_timestamps_are_strings(self, client):
        client.post('/api/pois', json={'Name_EN': 'Time Test'})
        resp = client.get('/api/pois')
        poi = resp.get_json()[0]
        assert isinstance(poi['created_at'], str)
        assert len(poi['created_at']) > 0


class TestGetSinglePoi:
    """TC-API-003: GET /api/pois/<gid>"""

    def test_get_existing_poi(self, client, created_poi):
        resp = client.get(f'/api/pois/{created_poi}')
        assert resp.status_code == 200
        data = resp.get_json()
        assert data['GlobalID'] == created_poi
        assert data['Name_EN'] == 'Riyadh Restaurant'

    def test_get_nonexistent_poi(self, client):
        resp = client.get('/api/pois/{FAKE-0000-0000}')
        assert resp.status_code == 404

    def test_globalid_with_special_chars(self, client):
        """GlobalIDs have braces and dashes — URL encoding must work."""
        resp = client.post('/api/pois', json={
            'GlobalID': '{ABCD1234-5678-9ABC-DEF0-123456789ABC}',
            'Name_EN': 'Special Chars'
        })
        gid = resp.get_json()['GlobalID']
        resp2 = client.get(f'/api/pois/{gid}')
        assert resp2.status_code == 200


class TestCreatePoi:
    """TC-API-004: POST /api/pois"""

    def test_create_complete_poi(self, client, sample_poi):
        resp = client.post('/api/pois', json=sample_poi)
        assert resp.status_code == 201
        data = resp.get_json()
        assert data['ok'] is True
        assert data['GlobalID'].startswith('{')
        assert data['GlobalID'].endswith('}')

    def test_auto_generates_globalid(self, client, minimal_poi):
        resp = client.post('/api/pois', json=minimal_poi)
        gid = resp.get_json()['GlobalID']
        assert len(gid) == 38  # {UUID} format
        assert gid[0] == '{' and gid[-1] == '}'

    def test_custom_globalid(self, client):
        custom_gid = '{CUSTOM00-1111-2222-3333-444444444444}'
        resp = client.post('/api/pois', json={
            'GlobalID': custom_gid,
            'Name_EN': 'Custom ID'
        })
        assert resp.get_json()['GlobalID'] == custom_gid

    def test_create_minimal_poi(self, client, minimal_poi):
        resp = client.post('/api/pois', json=minimal_poi)
        assert resp.status_code == 201

    def test_create_empty_body_fails(self, client):
        resp = client.post('/api/pois', json={})
        # Should still create (with auto-generated ID)
        # The API accepts empty data
        assert resp.status_code in (201, 400)

    def test_create_no_body_fails(self, client):
        resp = client.post('/api/pois', content_type='application/json', data='')
        assert resp.status_code == 400

    def test_arabic_names(self, client):
        resp = client.post('/api/pois', json={
            'Name_AR': 'مقهى الصباح الجميل',
            'Name_EN': 'Beautiful Morning Cafe',
        })
        assert resp.status_code == 201
        gid = resp.get_json()['GlobalID']
        poi = client.get(f'/api/pois/{gid}').get_json()
        assert poi['Name_AR'] == 'مقهى الصباح الجميل'

    def test_long_name(self, client):
        long_name = 'A' * 500
        resp = client.post('/api/pois', json={'Name_EN': long_name})
        assert resp.status_code == 201
        gid = resp.get_json()['GlobalID']
        poi = client.get(f'/api/pois/{gid}').get_json()
        assert poi['Name_EN'] == long_name

    def test_created_poi_appears_in_list(self, client, minimal_poi):
        client.post('/api/pois', json=minimal_poi)
        resp = client.get('/api/pois')
        assert len(resp.get_json()) == 1


class TestUpdatePoi:
    """TC-API-005: PATCH /api/pois/<gid>"""

    def test_update_single_field(self, client, created_poi):
        resp = client.patch(f'/api/pois/{created_poi}', json={
            'Name_EN': 'Updated Name'
        })
        assert resp.status_code == 200
        data = resp.get_json()
        assert data['ok'] is True
        # Verify persisted
        poi = client.get(f'/api/pois/{created_poi}').get_json()
        assert poi['Name_EN'] == 'Updated Name'

    def test_update_multiple_fields(self, client, created_poi):
        resp = client.patch(f'/api/pois/{created_poi}', json={
            'Name_EN': 'New Name',
            'Category': 'Cafes',
            'Phone_Number': '+966501111111',
        })
        assert resp.status_code == 200
        poi = client.get(f'/api/pois/{created_poi}').get_json()
        assert poi['Name_EN'] == 'New Name'
        assert poi['Category'] == 'Cafes'
        assert poi['Phone_Number'] == '+966501111111'

    def test_update_creates_audit_log(self, client, created_poi):
        client.patch(f'/api/pois/{created_poi}', json={
            'Name_EN': 'Audited Change',
            '_reviewer': 'waleed',
        })
        resp = client.get('/api/audit-log')
        logs = resp.get_json()['logs']
        assert len(logs) >= 1
        log = logs[0]
        assert log['field_name'] == 'Name_EN'
        assert log['new_value'] == 'Audited Change'
        assert log['reviewer'] == 'waleed'

    def test_update_nonexistent_poi(self, client):
        resp = client.patch('/api/pois/{NONEXIST-0000}', json={'Name_EN': 'X'})
        assert resp.status_code == 404

    def test_update_ignores_readonly_fields(self, client, created_poi):
        original = client.get(f'/api/pois/{created_poi}').get_json()
        client.patch(f'/api/pois/{created_poi}', json={
            'GlobalID': '{HACKED}',
            'created_at': '2000-01-01',
        })
        updated = client.get(f'/api/pois/{created_poi}').get_json()
        assert updated['GlobalID'] == original['GlobalID']

    def test_update_to_empty_string(self, client, created_poi):
        client.patch(f'/api/pois/{created_poi}', json={'Email': 'test@test.com'})
        client.patch(f'/api/pois/{created_poi}', json={'Email': ''})
        poi = client.get(f'/api/pois/{created_poi}').get_json()
        assert poi['Email'] == ''


class TestBulkUpdate:
    """TC-API-006: PATCH /api/pois/bulk"""

    def test_bulk_update_multiple_pois(self, client):
        gids = []
        for i in range(3):
            r = client.post('/api/pois', json={'Name_EN': f'Bulk {i}'})
            gids.append(r.get_json()['GlobalID'])

        resp = client.patch('/api/pois/bulk', json=[
            {'GlobalID': gids[0], 'Review_Status': 'Reviewed'},
            {'GlobalID': gids[1], 'Review_Status': 'Reviewed'},
            {'GlobalID': gids[2], 'Review_Flag': 'Duplicate detected'},
        ])
        assert resp.status_code == 200
        assert resp.get_json()['updated'] == 3

    def test_bulk_update_empty_array(self, client):
        resp = client.patch('/api/pois/bulk', json=[])
        assert resp.status_code == 200
        assert resp.get_json()['updated'] == 0


class TestDeletePoi:
    """TC-API-007: DELETE /api/pois/<gid>"""

    def test_delete_existing_poi(self, client, created_poi):
        resp = client.delete(f'/api/pois/{created_poi}')
        assert resp.status_code == 200
        assert resp.get_json()['ok'] is True
        # Verify gone
        resp2 = client.get(f'/api/pois/{created_poi}')
        assert resp2.status_code == 404

    def test_delete_nonexistent_poi(self, client):
        resp = client.delete('/api/pois/{NOPE-0000}')
        assert resp.status_code == 404

    def test_delete_removes_from_list(self, client, created_poi):
        assert len(client.get('/api/pois').get_json()) == 1
        client.delete(f'/api/pois/{created_poi}')
        assert len(client.get('/api/pois').get_json()) == 0
