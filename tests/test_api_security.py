"""TC-SEC: Security tests — injection, XSS, auth bypass."""


class TestSQLInjection:
    """Verify parameterized queries prevent SQL injection."""

    def test_globalid_injection(self, client, created_poi):
        """Try SQL injection via GlobalID path parameter."""
        malicious = "'; DROP TABLE final_delivery; --"
        resp = client.get(f'/api/pois/{malicious}')
        assert resp.status_code == 404
        # Table should still exist
        resp2 = client.get('/api/pois')
        assert resp2.status_code == 200

    def test_name_injection_on_create(self, client):
        resp = client.post('/api/pois', json={
            'Name_EN': "'; DROP TABLE final_delivery; --",
            'Name_AR': "اختبار",
        })
        assert resp.status_code == 201
        # Verify data stored as literal string, not executed
        gid = resp.get_json()['GlobalID']
        poi = client.get(f'/api/pois/{gid}').get_json()
        assert "DROP TABLE" in poi['Name_EN']

    def test_update_injection(self, client, created_poi):
        resp = client.patch(f'/api/pois/{created_poi}', json={
            'Name_EN': "Robert'; DROP TABLE final_delivery;--"
        })
        assert resp.status_code == 200
        # Table still works
        assert client.get('/api/pois').status_code == 200

    def test_search_injection_in_audit(self, client):
        resp = client.get("/api/audit-log?reviewer=' OR 1=1--")
        assert resp.status_code == 200


class TestXSS:
    """Verify HTML/script injection stored safely."""

    def test_xss_in_name(self, client):
        xss = '<script>alert("xss")</script>'
        resp = client.post('/api/pois', json={
            'Name_EN': xss,
            'Name_AR': xss,
        })
        assert resp.status_code == 201
        gid = resp.get_json()['GlobalID']
        poi = client.get(f'/api/pois/{gid}').get_json()
        # Data stored as-is (frontend must escape on render)
        assert poi['Name_EN'] == xss

    def test_xss_in_url_fields(self, client, created_poi):
        xss_url = 'javascript:alert(1)'
        client.patch(f'/api/pois/{created_poi}', json={
            'Website': xss_url
        })
        poi = client.get(f'/api/pois/{created_poi}').get_json()
        assert poi['Website'] == xss_url  # Stored as-is


class TestAuthSecurity:
    """Authentication edge cases."""

    def test_no_auth_required_for_read(self, client, created_poi):
        """Read endpoints don't require auth (design decision)."""
        assert client.get('/api/pois').status_code == 200
        assert client.get(f'/api/pois/{created_poi}').status_code == 200
        assert client.get('/api/stats').status_code == 200

    def test_password_not_in_response(self, client):
        """Login response must not expose password hash."""
        resp = client.post('/api/login', json={
            'username': 'waleed', 'password': 'waleed123'
        })
        data = resp.get_json()
        assert 'password' not in data
        assert 'password_hash' not in data
        assert 'hash' not in data

    def test_reviewer_list_no_passwords(self, client):
        resp = client.get('/api/reviewers')
        for reviewer in resp.get_json():
            assert 'password_hash' not in reviewer
            assert 'password' not in reviewer
