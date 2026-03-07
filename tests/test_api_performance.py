"""TC-PERF: Performance benchmarks."""
import time
import gzip
import json
from conftest import SAMPLE_POI_COMPLETE


class TestResponseTimes:
    """API response time targets."""

    def test_get_pois_under_3s(self, client):
        """GET /api/pois should respond under 3 seconds even with many POIs."""
        # Seed 50 POIs for a reasonable test
        for i in range(50):
            client.post('/api/pois', json={
                'Name_EN': f'Perf Test {i}',
                'Category': 'Restaurants',
            })
        start = time.time()
        resp = client.get('/api/pois', headers={'Accept-Encoding': 'gzip'})
        elapsed = time.time() - start
        assert resp.status_code == 200
        assert elapsed < 3.0, f'GET /api/pois took {elapsed:.2f}s (target: <3s)'

    def test_create_poi_under_1s(self, client):
        start = time.time()
        resp = client.post('/api/pois', json=SAMPLE_POI_COMPLETE)
        elapsed = time.time() - start
        assert resp.status_code == 201
        assert elapsed < 1.0, f'POST /api/pois took {elapsed:.2f}s (target: <1s)'

    def test_update_poi_under_1s(self, client, created_poi):
        start = time.time()
        resp = client.patch(f'/api/pois/{created_poi}', json={'Name_EN': 'Speed Test'})
        elapsed = time.time() - start
        assert resp.status_code == 200
        assert elapsed < 1.0, f'PATCH took {elapsed:.2f}s (target: <1s)'

    def test_validation_under_2s(self, client):
        start = time.time()
        resp = client.post('/api/validate-poi', json=SAMPLE_POI_COMPLETE)
        elapsed = time.time() - start
        assert resp.status_code == 200
        assert elapsed < 2.0, f'Validation took {elapsed:.2f}s (target: <2s)'


class TestCompression:
    """Gzip compression efficiency."""

    def test_gzip_compression_ratio(self, client):
        """Gzip should achieve at least 5:1 compression on JSON."""
        # Seed 20 POIs with full data
        for i in range(20):
            poi = SAMPLE_POI_COMPLETE.copy()
            poi['Name_EN'] = f'Compression Test {i}'
            client.post('/api/pois', json=poi)

        # Get uncompressed
        resp_raw = client.get('/api/pois')
        raw_size = len(resp_raw.data)

        # Get compressed
        resp_gz = client.get('/api/pois', headers={'Accept-Encoding': 'gzip'})
        gz_size = len(resp_gz.data)

        ratio = raw_size / gz_size if gz_size > 0 else 0
        assert ratio >= 5.0, f'Compression ratio {ratio:.1f}:1 (target: >=5:1)'
