"""TC-API-008: Authentication and reviewer management."""


class TestLogin:
    """POST /api/login"""

    def test_valid_login(self, client):
        resp = client.post('/api/login', json={
            'username': 'waleed',
            'password': 'waleed123',
        })
        assert resp.status_code == 200
        data = resp.get_json()
        assert data['ok'] is True
        assert data['username'] == 'waleed'
        assert data['display_name'] == 'Waleed'
        assert data['role'] == 'reviewer'

    def test_all_seeded_reviewers_can_login(self, client):
        reviewers = ['waleed', 'fadhel', 'ruwaida', 'abdulrhman', 'naver', 'annivation']
        for name in reviewers:
            resp = client.post('/api/login', json={
                'username': name,
                'password': f'{name}123',
            })
            assert resp.status_code == 200, f'Login failed for {name}'

    def test_wrong_password(self, client):
        resp = client.post('/api/login', json={
            'username': 'waleed',
            'password': 'wrong',
        })
        assert resp.status_code == 401

    def test_unknown_user(self, client):
        resp = client.post('/api/login', json={
            'username': 'nobody',
            'password': 'test',
        })
        assert resp.status_code == 401

    def test_missing_password(self, client):
        resp = client.post('/api/login', json={'username': 'waleed'})
        assert resp.status_code == 401

    def test_missing_username(self, client):
        resp = client.post('/api/login', json={'password': 'waleed123'})
        assert resp.status_code == 401

    def test_empty_body(self, client):
        resp = client.post('/api/login', json={})
        assert resp.status_code == 401

    def test_case_sensitive_username(self, client):
        resp = client.post('/api/login', json={
            'username': 'Waleed',  # capital W
            'password': 'waleed123',
        })
        # Should fail — usernames are lowercase in DB
        assert resp.status_code == 401


class TestListReviewers:
    """GET /api/reviewers"""

    def test_returns_all_reviewers(self, client):
        resp = client.get('/api/reviewers')
        assert resp.status_code == 200
        data = resp.get_json()
        assert len(data) == 6
        usernames = {r['username'] for r in data}
        assert 'waleed' in usernames
        assert 'fadhel' in usernames

    def test_reviewer_fields(self, client):
        resp = client.get('/api/reviewers')
        reviewer = resp.get_json()[0]
        assert 'id' in reviewer
        assert 'username' in reviewer
        assert 'display_name' in reviewer
        assert 'role' in reviewer
        # Password hash should NOT be exposed
        assert 'password_hash' not in reviewer
