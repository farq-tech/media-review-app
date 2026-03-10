"""
Tests for POI lifecycle state machine: transitions, auto-revert, flag overlay,
archive, reject, and approval checks.
"""
import pytest
import json


# ── Unit tests for lifecycle module (no DB needed) ──

class TestLifecycleModule:
    """Pure unit tests for lifecycle.py — no database required."""

    def test_valid_transitions_from_draft(self):
        from lifecycle import can_transition
        assert can_transition('Draft', 'Reviewed')
        assert can_transition('Draft', 'Archived')
        assert can_transition('Draft', 'Rejected')
        assert not can_transition('Draft', 'Draft')  # No self-transition

    def test_valid_transitions_from_reviewed(self):
        from lifecycle import can_transition
        assert can_transition('Reviewed', 'Draft')
        assert can_transition('Reviewed', 'Archived')
        assert can_transition('Reviewed', 'Rejected')

    def test_rejected_is_terminal(self):
        from lifecycle import can_transition, validate_transition
        assert not can_transition('Rejected', 'Draft')
        assert not can_transition('Rejected', 'Reviewed')
        assert not can_transition('Rejected', 'Archived')
        ok, msg = validate_transition('Rejected', 'Draft')
        assert not ok
        assert 'terminal' in msg.lower()

    def test_archived_can_restore_to_draft(self):
        from lifecycle import can_transition
        assert can_transition('Archived', 'Draft')
        assert not can_transition('Archived', 'Reviewed')

    def test_empty_status_treated_as_draft(self):
        from lifecycle import can_transition
        assert can_transition('', 'Reviewed')
        assert can_transition('', 'Draft')

    def test_approval_blockers_missing_fields(self):
        from lifecycle import get_approval_blockers
        blockers = get_approval_blockers({
            'Name_EN': '', 'Category': '', 'Latitude': '0', 'Longitude': '0'
        })
        assert len(blockers) >= 2
        assert any('Name_EN' in b for b in blockers)
        assert any('Category' in b for b in blockers)

    def test_approval_blockers_rejected(self):
        from lifecycle import get_approval_blockers
        blockers = get_approval_blockers({
            'Review_Status': 'Rejected',
            'Name_EN': 'Test', 'Category': 'Restaurants',
            'Latitude': '24.7', 'Longitude': '46.6'
        })
        assert any('rejected' in b.lower() for b in blockers)

    def test_approval_blockers_pass(self):
        from lifecycle import get_approval_blockers
        blockers = get_approval_blockers({
            'Review_Status': 'Draft',
            'Name_EN': 'Good Place', 'Category': 'Restaurants',
            'Latitude': '24.7136', 'Longitude': '46.6753'
        })
        assert len(blockers) == 0

    def test_should_auto_revert_major_edit(self):
        from lifecycle import should_auto_revert
        assert should_auto_revert('Reviewed', {'Name_EN'})
        assert should_auto_revert('Reviewed', {'Category', 'Review_Notes'})

    def test_should_not_revert_minor_edit(self):
        from lifecycle import should_auto_revert
        assert not should_auto_revert('Reviewed', {'Review_Notes'})
        assert not should_auto_revert('Reviewed', {'Review_Flag'})

    def test_should_not_revert_if_not_reviewed(self):
        from lifecycle import should_auto_revert
        assert not should_auto_revert('Draft', {'Name_EN'})
        assert not should_auto_revert('Archived', {'Category'})

    def test_major_fields_count(self):
        from lifecycle import MAJOR_FIELDS
        assert len(MAJOR_FIELDS) >= 50  # Should be ~62 fields

    def test_low_qa_score_blocks_approval(self):
        from lifecycle import get_approval_blockers
        poi = {'Review_Status': 'Draft', 'Name_EN': 'Test', 'Name_AR': 'اختبار',
               'Category': 'Banks', 'Latitude': '24.7', 'Longitude': '46.6',
               'QA_Score': '80'}
        blockers = get_approval_blockers(poi)
        assert any('QA score' in b for b in blockers)

    def test_high_qa_score_no_blocker(self):
        from lifecycle import get_approval_blockers
        poi = {'Review_Status': 'Draft', 'Name_EN': 'Test', 'Name_AR': 'اختبار',
               'Category': 'Banks', 'Latitude': '24.7', 'Longitude': '46.6',
               'QA_Score': '98'}
        blockers = get_approval_blockers(poi)
        assert not any('QA score' in b for b in blockers)


# ── Integration tests (require DB) ──

class TestLifecycleAPI:
    """API integration tests for lifecycle endpoints."""

    def _create_poi(self, client, **overrides):
        data = {
            'Name_EN': 'Test POI', 'Name_AR': 'اختبار',
            'Category': 'Restaurants', 'Subcategory': 'Fast Food',
            'Latitude': '24.7136', 'Longitude': '46.6753',
        }
        data.update(overrides)
        resp = client.post('/api/pois', json=data)
        d = resp.get_json()
        return d.get('GlobalID') or d.get('data', {}).get('GlobalID')

    def test_archive_from_draft(self, client):
        gid = self._create_poi(client)
        resp = client.post(f'/api/pois/{gid}/archive', json={'reason': 'Duplicate'})
        d = resp.get_json()
        assert d['ok']
        assert d['status'] == 'Archived'
        # Verify in DB
        check = client.get(f'/api/pois/{gid}')
        assert check.get_json()['Review_Status'] == 'Archived'

    def test_archive_sets_reason(self, client):
        gid = self._create_poi(client)
        client.post(f'/api/pois/{gid}/archive', json={'reason': 'Closed permanently'})
        poi = client.get(f'/api/pois/{gid}').get_json()
        assert poi['archived_reason'] == 'Closed permanently'

    def test_reject_requires_reason(self, client):
        gid = self._create_poi(client)
        resp = client.post(f'/api/pois/{gid}/reject', json={'reason': ''})
        assert resp.status_code == 400
        assert 'reason' in resp.get_json().get('error', '').lower()

    def test_reject_success(self, client):
        gid = self._create_poi(client)
        resp = client.post(f'/api/pois/{gid}/reject', json={'reason': 'Bad data'})
        d = resp.get_json()
        assert d['ok']
        assert d['status'] == 'Rejected'

    def test_reject_already_rejected(self, client):
        gid = self._create_poi(client)
        client.post(f'/api/pois/{gid}/reject', json={'reason': 'Bad'})
        resp = client.post(f'/api/pois/{gid}/reject', json={'reason': 'Again'})
        assert resp.status_code == 400

    def test_rejected_cannot_transition(self, client):
        gid = self._create_poi(client)
        client.post(f'/api/pois/{gid}/reject', json={'reason': 'Bad'})
        # Try to set status back to Draft
        resp = client.patch(f'/api/pois/{gid}', json={'Review_Status': 'Draft'})
        assert resp.status_code == 422

    def test_flag_preserves_status(self, client):
        gid = self._create_poi(client)
        # Approve first
        client.patch(f'/api/pois/{gid}', json={'Review_Status': 'Reviewed'})
        # Flag it
        resp = client.patch(f'/api/pois/{gid}/flag', json={'flagged': True, 'flag_reason': 'Check photos'})
        d = resp.get_json()
        assert d['ok']
        # Status should still be Reviewed
        poi = client.get(f'/api/pois/{gid}').get_json()
        assert poi['Review_Status'] == 'Reviewed'
        assert poi['flagged'] == True

    def test_unflag_preserves_status(self, client):
        gid = self._create_poi(client)
        client.patch(f'/api/pois/{gid}/flag', json={'flagged': True, 'flag_reason': 'Check'})
        client.patch(f'/api/pois/{gid}/flag', json={'flagged': False})
        poi = client.get(f'/api/pois/{gid}').get_json()
        assert poi['flagged'] == False

    def test_major_edit_reverts_reviewed_to_draft(self, client):
        gid = self._create_poi(client)
        client.patch(f'/api/pois/{gid}', json={'Review_Status': 'Reviewed'})
        # Major edit
        resp = client.patch(f'/api/pois/{gid}', json={'Name_EN': 'Changed Name'})
        assert resp.get_json()['ok']
        poi = client.get(f'/api/pois/{gid}').get_json()
        assert poi['Review_Status'] == 'Draft'
        assert poi['draft_reason'] == 'modified'

    def test_minor_edit_keeps_reviewed(self, client):
        gid = self._create_poi(client)
        client.patch(f'/api/pois/{gid}', json={'Review_Status': 'Reviewed'})
        # Minor edit (Review_Notes is not in MAJOR_FIELDS)
        client.patch(f'/api/pois/{gid}', json={'Review_Notes': 'Looks good'})
        poi = client.get(f'/api/pois/{gid}').get_json()
        assert poi['Review_Status'] == 'Reviewed'

    def test_approval_check_pass(self, client):
        gid = self._create_poi(client)
        resp = client.get(f'/api/pois/{gid}/approval-check')
        d = resp.get_json()
        assert d['can_approve'] == True
        assert d['blockers'] == []

    def test_approval_check_blocked(self, client):
        gid = self._create_poi(client, Name_EN='', Category='')
        resp = client.get(f'/api/pois/{gid}/approval-check')
        d = resp.get_json()
        assert d['can_approve'] == False
        assert len(d['blockers']) > 0

    def test_version_increments_on_update(self, client):
        gid = self._create_poi(client)
        resp = client.patch(f'/api/pois/{gid}', json={'Review_Notes': 'edit 1'})
        v1 = resp.get_json().get('review_version', 0)
        resp2 = client.patch(f'/api/pois/{gid}', json={'Review_Notes': 'edit 2'})
        v2 = resp2.get_json().get('review_version', 0)
        assert v2 > v1

    def test_conflict_detection(self, client):
        gid = self._create_poi(client)
        # First update
        resp1 = client.patch(f'/api/pois/{gid}', json={'Review_Notes': 'edit 1'})
        # Try with stale version
        resp2 = client.patch(f'/api/pois/{gid}', json={
            'Review_Notes': 'edit 2',
            '_expected_version': 0  # Stale version
        })
        assert resp2.status_code == 409
