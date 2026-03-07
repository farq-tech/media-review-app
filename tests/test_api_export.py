"""TC-API-012: CSV export and statistics."""


class TestCSVExport:
    """GET /api/pois/export"""

    def test_export_csv_format(self, client, created_poi):
        resp = client.get('/api/pois/export')
        assert resp.status_code == 200
        assert 'text/csv' in resp.content_type
        csv_text = resp.data.decode('utf-8-sig')
        lines = csv_text.strip().split('\n')
        assert len(lines) == 2  # header + 1 POI
        header = lines[0]
        assert 'GlobalID' in header
        assert 'Name_EN' in header
        assert 'Name_AR' in header

    def test_export_csv_escapes_commas(self, client):
        client.post('/api/pois', json={
            'Name_EN': 'Test, with commas',
            'Name_AR': 'اختبار',
        })
        resp = client.get('/api/pois/export')
        csv_text = resp.data.decode('utf-8-sig')
        # Name with comma should be quoted
        assert '"Test, with commas"' in csv_text

    def test_export_csv_arabic_preserved(self, client):
        client.post('/api/pois', json={
            'Name_AR': 'مطعم الرياض الجميل',
            'Name_EN': 'Test',
        })
        resp = client.get('/api/pois/export')
        csv_text = resp.data.decode('utf-8-sig')
        assert 'مطعم الرياض الجميل' in csv_text

    def test_export_empty_db(self, client):
        resp = client.get('/api/pois/export')
        assert resp.status_code == 200
        csv_text = resp.data.decode('utf-8-sig')
        lines = csv_text.strip().split('\n')
        assert len(lines) == 1  # header only


class TestStatistics:
    """GET /api/stats"""

    def test_stats_empty_db(self, client):
        resp = client.get('/api/stats')
        assert resp.status_code == 200
        data = resp.get_json()
        assert data['total'] == 0
        assert data['reviewed'] == 0
        assert data['flagged'] == 0

    def test_stats_counts(self, client):
        # 3 POIs: 1 reviewed, 1 flagged, 1 plain
        r1 = client.post('/api/pois', json={'Name_EN': 'POI 1'}).get_json()
        r2 = client.post('/api/pois', json={'Name_EN': 'POI 2'}).get_json()
        r3 = client.post('/api/pois', json={'Name_EN': 'POI 3'}).get_json()

        client.patch(f'/api/pois/{r1["GlobalID"]}', json={'Review_Status': 'Reviewed'})
        client.patch(f'/api/pois/{r2["GlobalID"]}', json={'Review_Flag': 'Duplicate detected'})

        resp = client.get('/api/stats')
        data = resp.get_json()
        assert data['total'] == 3
        assert data['reviewed'] == 1
        assert data['flagged'] == 1

    def test_stats_avg_qa(self, client):
        r1 = client.post('/api/pois', json={'Name_EN': 'QA1'}).get_json()
        r2 = client.post('/api/pois', json={'Name_EN': 'QA2'}).get_json()
        client.patch(f'/api/pois/{r1["GlobalID"]}', json={'QA_Score': '80'})
        client.patch(f'/api/pois/{r2["GlobalID"]}', json={'QA_Score': '100'})

        resp = client.get('/api/stats')
        data = resp.get_json()
        assert data['avg_qa'] == 90.0
