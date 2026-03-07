"""TC-API-010 + TC-API-015: Survey123 webhook and POI creation."""


class TestSurvey123Webhook:
    """POST /webhook/survey123"""

    def test_create_new_poi_from_webhook(self, client):
        payload = {
            'feature': {
                'attributes': {
                    'poi_name_en': 'Survey POI',
                    'poi_name_ar': 'نقطة مسح',
                    'category': 'Restaurants',
                    'phone_number': '+966512345678',
                    'working_hours': '09:00-22:00',
                },
                'geometry': {
                    'x': 46.6753,
                    'y': 24.7136,
                }
            }
        }
        resp = client.post('/webhook/survey123', json=payload)
        assert resp.status_code == 201
        data = resp.get_json()
        assert data['ok'] is True
        assert data['action'] == 'created'
        assert data['GlobalID'].startswith('{')

    def test_update_existing_poi_from_webhook(self, client):
        # Create POI first
        client.post('/api/pois', json={
            'Name_EN': 'Existing Place',
            'Category': 'Restaurants',
        })
        # Webhook with matching name → should update
        payload = {
            'attributes': {
                'poi_name_en': 'Existing Place',
                'phone_number': '+966509999999',
            }
        }
        resp = client.post('/webhook/survey123', json=payload)
        data = resp.get_json()
        assert data['ok'] is True
        assert data['action'] == 'updated'

    def test_webhook_extracts_geometry(self, client):
        payload = {
            'feature': {
                'attributes': {
                    'poi_name_en': 'Geo POI',
                    'category': 'Hotels',
                },
                'geometry': {'x': 46.123, 'y': 24.456}
            }
        }
        resp = client.post('/webhook/survey123', json=payload)
        gid = resp.get_json()['GlobalID']
        poi = client.get(f'/api/pois/{gid}').get_json()
        assert poi['Latitude'] == '24.456'
        assert poi['Longitude'] == '46.123'

    def test_webhook_flat_payload(self, client):
        """Test direct attribute payload (no feature wrapper)."""
        payload = {
            'poi_name_en': 'Flat POI',
            'poi_name_ar': 'نقطة مسطحة',
            'category': 'Cafes',
        }
        resp = client.post('/webhook/survey123', json=payload)
        assert resp.status_code == 201

    def test_webhook_empty_payload(self, client):
        resp = client.post('/webhook/survey123', json={})
        assert resp.status_code == 400

    def test_webhook_no_body(self, client):
        resp = client.post('/webhook/survey123')
        assert resp.status_code == 400


class TestRecentUpdates:
    """GET /api/pois/recent-updates + POST /api/pois/recent-updates/ack"""

    def test_recent_updates_after_webhook(self, client):
        client.post('/webhook/survey123', json={
            'feature': {
                'attributes': {
                    'poi_name_en': 'Update Tracker',
                    'category': 'Test',
                }
            }
        })
        resp = client.get('/api/pois/recent-updates')
        assert resp.status_code == 200
        data = resp.get_json()
        assert len(data) >= 1
        assert data[0]['poi_name'] == 'Update Tracker'

    def test_acknowledge_updates(self, client):
        client.post('/webhook/survey123', json={
            'feature': {'attributes': {'poi_name_en': 'Ack Test'}}
        })
        updates = client.get('/api/pois/recent-updates').get_json()
        ids = [u['id'] for u in updates]

        resp = client.post('/api/pois/recent-updates/ack', json={'ids': ids})
        assert resp.status_code == 200
        assert resp.get_json()['ok'] is True

        # After ack, should be empty
        updates2 = client.get('/api/pois/recent-updates').get_json()
        assert len(updates2) == 0
