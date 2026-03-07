"""TC-API-011: Audit log and statistics."""


class TestAuditLog:
    """GET /api/audit-log"""

    def test_empty_audit_log(self, client):
        resp = client.get('/api/audit-log')
        assert resp.status_code == 200
        data = resp.get_json()
        assert data['logs'] == []
        assert data['total'] == 0

    def test_audit_entry_created_on_update(self, client, created_poi):
        client.patch(f'/api/pois/{created_poi}', json={
            'Name_EN': 'Audit Test',
            '_reviewer': 'waleed',
        })
        resp = client.get('/api/audit-log')
        data = resp.get_json()
        assert data['total'] >= 1
        log = data['logs'][0]
        assert log['global_id'] == created_poi
        assert log['reviewer'] == 'waleed'
        assert log['field_name'] == 'Name_EN'
        assert log['old_value'] == 'Riyadh Restaurant'
        assert log['new_value'] == 'Audit Test'

    def test_multiple_field_changes_create_multiple_entries(self, client, created_poi):
        client.patch(f'/api/pois/{created_poi}', json={
            'Name_EN': 'New Name',
            'Category': 'Cafes',
            '_reviewer': 'fadhel',
        })
        resp = client.get('/api/audit-log')
        data = resp.get_json()
        # Should have entries for both Name_EN and Category
        fields = {log['field_name'] for log in data['logs']}
        assert 'Name_EN' in fields
        assert 'Category' in fields

    def test_filter_by_reviewer(self, client, created_poi):
        client.patch(f'/api/pois/{created_poi}', json={
            'Name_EN': 'By Waleed', '_reviewer': 'waleed',
        })
        client.patch(f'/api/pois/{created_poi}', json={
            'Name_EN': 'By Fadhel', '_reviewer': 'fadhel',
        })
        resp = client.get('/api/audit-log?reviewer=waleed')
        logs = resp.get_json()['logs']
        assert all(log['reviewer'] == 'waleed' for log in logs)

    def test_filter_by_global_id(self, client, created_poi):
        client.patch(f'/api/pois/{created_poi}', json={
            'Name_EN': 'Changed', '_reviewer': 'waleed',
        })
        resp = client.get(f'/api/audit-log?global_id={created_poi}')
        logs = resp.get_json()['logs']
        assert all(log['global_id'] == created_poi for log in logs)

    def test_pagination(self, client, created_poi):
        # Create 5 audit entries
        for i in range(5):
            client.patch(f'/api/pois/{created_poi}', json={
                'Name_EN': f'Change {i}', '_reviewer': 'waleed',
            })
        resp = client.get('/api/audit-log?limit=2&offset=0')
        data = resp.get_json()
        assert len(data['logs']) == 2
        assert data['total'] == 5

        resp2 = client.get('/api/audit-log?limit=2&offset=2')
        data2 = resp2.get_json()
        assert len(data2['logs']) == 2

    def test_no_audit_for_unchanged_fields(self, client, created_poi):
        """Updating a field to the same value should not create audit entry."""
        client.patch(f'/api/pois/{created_poi}', json={
            'Name_EN': 'Riyadh Restaurant',  # same as original
            '_reviewer': 'waleed',
        })
        resp = client.get('/api/audit-log')
        data = resp.get_json()
        # Should have 0 entries since value didn't change
        name_logs = [l for l in data['logs'] if l['field_name'] == 'Name_EN']
        assert len(name_logs) == 0


class TestAuditStats:
    """GET /api/audit-log/stats"""

    def test_stats_empty(self, client):
        resp = client.get('/api/audit-log/stats')
        assert resp.status_code == 200
        assert resp.get_json() == []

    def test_stats_per_reviewer(self, client, created_poi):
        for i in range(3):
            client.patch(f'/api/pois/{created_poi}', json={
                'Name_EN': f'W{i}', '_reviewer': 'waleed',
            })
        client.patch(f'/api/pois/{created_poi}', json={
            'Category': 'Cafes', '_reviewer': 'fadhel',
        })

        resp = client.get('/api/audit-log/stats')
        stats = resp.get_json()
        waleed = next(s for s in stats if s['reviewer'] == 'waleed')
        fadhel = next(s for s in stats if s['reviewer'] == 'fadhel')
        assert waleed['total_changes'] == 3
        assert fadhel['total_changes'] == 1
