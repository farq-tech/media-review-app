"""
Tests for optimistic concurrency (version conflict detection).
"""
import pytest


class TestConflictDetection:
    """API integration tests for 409 conflict scenarios."""

    def _create_poi(self, client, **overrides):
        data = {
            'Name_EN': 'Conflict Test', 'Name_AR': 'اختبار',
            'Category': 'Restaurants', 'Latitude': '24.7', 'Longitude': '46.6',
        }
        data.update(overrides)
        resp = client.post('/api/pois', json=data)
        return resp.get_json().get('GlobalID')

    def test_save_without_version_succeeds(self, client):
        """Backward compat: no _expected_version = always succeeds."""
        gid = self._create_poi(client)
        resp = client.patch(f'/api/pois/{gid}', json={'Review_Notes': 'edit'})
        assert resp.get_json()['ok']

    def test_save_with_correct_version_succeeds(self, client):
        gid = self._create_poi(client)
        # Get current version
        poi = client.get(f'/api/pois/{gid}').get_json()
        version = poi.get('review_version', 0)
        resp = client.patch(f'/api/pois/{gid}', json={
            'Review_Notes': 'edit',
            '_expected_version': version
        })
        assert resp.get_json()['ok']

    def test_save_with_stale_version_returns_409(self, client):
        gid = self._create_poi(client)
        # Make an edit to bump version
        client.patch(f'/api/pois/{gid}', json={'Review_Notes': 'edit 1'})
        # Try with stale version 0
        resp = client.patch(f'/api/pois/{gid}', json={
            'Review_Notes': 'edit 2',
            '_expected_version': 0
        })
        assert resp.status_code == 409
        d = resp.get_json()
        assert d['error_code'] == 'CONFLICT'
        assert 'current_version' in d.get('error_details', {})

    def test_version_increments_on_each_update(self, client):
        gid = self._create_poi(client)
        versions = []
        for i in range(3):
            resp = client.patch(f'/api/pois/{gid}', json={'Review_Notes': f'edit {i}'})
            versions.append(resp.get_json().get('review_version', 0))
        assert versions[0] < versions[1] < versions[2]

    def test_bulk_update_with_conflicts(self, client):
        gid1 = self._create_poi(client, Name_EN='POI A')
        gid2 = self._create_poi(client, Name_EN='POI B')
        # Bump version on gid1
        client.patch(f'/api/pois/{gid1}', json={'Review_Notes': 'bump'})
        # Bulk update: gid1 with stale version, gid2 without version
        resp = client.patch('/api/pois/bulk', json=[
            {'GlobalID': gid1, 'Review_Notes': 'bulk 1', '_expected_version': 0},
            {'GlobalID': gid2, 'Review_Notes': 'bulk 2'},
        ])
        d = resp.get_json()
        assert d['ok']
        assert d['updated'] == 1  # Only gid2 updated
        assert len(d.get('conflicts', [])) == 1
        assert d['conflicts'][0]['GlobalID'] == gid1

    def test_response_includes_new_version(self, client):
        gid = self._create_poi(client)
        resp = client.patch(f'/api/pois/{gid}', json={'Review_Notes': 'test'})
        d = resp.get_json()
        assert 'review_version' in d
        assert d['review_version'] >= 1
