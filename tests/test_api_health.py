"""TC-API-001: Health check and basic server status."""


def test_health_check(client):
    """GET / returns status ok."""
    resp = client.get('/')
    assert resp.status_code == 200
    data = resp.get_json()
    assert data['status'] == 'ok'
    assert 'service' in data


def test_api_prefix_exists(client):
    """API routes are mounted under /api/."""
    resp = client.get('/api/stats')
    assert resp.status_code == 200
