"""
Shared pytest fixtures for POI Review Dashboard backend tests.
Uses a real PostgreSQL test database for integration accuracy.

Frontend smoke tests (test_frontend_smoke.py) do NOT require a database.
Backend API tests require PostgreSQL with a 'poi_test' database.
"""
import os
import sys
import pytest

# Add backend to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'backend'))

# Use test database (set via env or default to local)
TEST_DB_URL = os.environ.get(
    'TEST_DATABASE_URL',
    'postgresql://postgres:postgres@localhost:5432/poi_test'
)

def _db_available():
    """Check if test database is reachable."""
    try:
        import psycopg2
        conn = psycopg2.connect(TEST_DB_URL)
        conn.close()
        return True
    except Exception:
        return False

# Skip DB-dependent fixtures when no database is available
_has_db = _db_available()


@pytest.fixture(scope='session')
def setup_test_db():
    """Create test database schema once per session."""
    if not _has_db:
        pytest.skip('PostgreSQL test database not available')
    import psycopg2
    conn = psycopg2.connect(TEST_DB_URL)
    conn.autocommit = True
    cur = conn.cursor()

    # Create main table
    cur.execute("""
        CREATE TABLE IF NOT EXISTS final_delivery (
            "GlobalID" TEXT PRIMARY KEY NOT NULL,
            "Name_AR" TEXT DEFAULT '',
            "Name_EN" TEXT DEFAULT '',
            "Legal_Name" TEXT DEFAULT '',
            "Category" TEXT DEFAULT '',
            "Subcategory" TEXT DEFAULT '',
            "Category_Level_3" TEXT DEFAULT '',
            "Company_Status" TEXT DEFAULT '',
            "Latitude" TEXT DEFAULT '',
            "Longitude" TEXT DEFAULT '',
            "Google_Map_URL" TEXT DEFAULT '',
            "Building_Number" TEXT DEFAULT '',
            "Floor_Number" TEXT DEFAULT '',
            "Entrance_Location" TEXT DEFAULT '',
            "Phone_Number" TEXT DEFAULT '',
            "Email" TEXT DEFAULT '',
            "Website" TEXT DEFAULT '',
            "Social_Media" TEXT DEFAULT '',
            "Working_Days" TEXT DEFAULT '',
            "Working_Hours" TEXT DEFAULT '',
            "Break_Time" TEXT DEFAULT '',
            "Holidays" TEXT DEFAULT '',
            "Menu_Barcode_URL" TEXT DEFAULT '',
            "Language" TEXT DEFAULT '',
            "Cuisine" TEXT DEFAULT '',
            "Payment_Methods" TEXT DEFAULT '',
            "Commercial_License" TEXT DEFAULT '',
            "Exterior_Photo_URL" TEXT DEFAULT '',
            "Interior_Photo_URL" TEXT DEFAULT '',
            "Menu_Photo_URL" TEXT DEFAULT '',
            "Video_URL" TEXT DEFAULT '',
            "License_Photo_URL" TEXT DEFAULT '',
            "Additional_Photo_URLs" TEXT DEFAULT '',
            "Amenities" TEXT DEFAULT '',
            "District_AR" TEXT DEFAULT '',
            "District_EN" TEXT DEFAULT '',
            "Delivery_Method" TEXT DEFAULT '',
            "Menu" TEXT DEFAULT '',
            "Drive_Thru" TEXT DEFAULT '',
            "Dine_In" TEXT DEFAULT '',
            "Only_Delivery" TEXT DEFAULT '',
            "Reservation" TEXT DEFAULT '',
            "Require_Ticket" TEXT DEFAULT '',
            "Order_from_Car" TEXT DEFAULT '',
            "Pickup_Point" TEXT DEFAULT '',
            "WiFi" TEXT DEFAULT '',
            "Music" TEXT DEFAULT '',
            "Valet_Parking" TEXT DEFAULT '',
            "Has_Parking_Lot" TEXT DEFAULT '',
            "Wheelchair_Accessible" TEXT DEFAULT '',
            "Family_Seating" TEXT DEFAULT '',
            "Waiting_Area" TEXT DEFAULT '',
            "Private_Dining" TEXT DEFAULT '',
            "Smoking_Area" TEXT DEFAULT '',
            "Children_Area" TEXT DEFAULT '',
            "Shisha" TEXT DEFAULT '',
            "Live_Sports" TEXT DEFAULT '',
            "Is_Landmark" TEXT DEFAULT '',
            "Is_Trending" TEXT DEFAULT '',
            "Large_Groups" TEXT DEFAULT '',
            "Women_Prayer_Room" TEXT DEFAULT '',
            "Iftar_Tent" TEXT DEFAULT '',
            "Iftar_Menu" TEXT DEFAULT '',
            "Open_Suhoor" TEXT DEFAULT '',
            "Free_Entry" TEXT DEFAULT '',
            "Num_Menu_Photos" TEXT DEFAULT '',
            "Num_Additional_Photos" TEXT DEFAULT '',
            "Confidence" TEXT DEFAULT '',
            "Source" TEXT DEFAULT '',
            "All_Sources" TEXT DEFAULT '',
            "Importance_Score" TEXT DEFAULT '',
            "QA_Score" TEXT DEFAULT '',
            "Review_Flag" TEXT DEFAULT '',
            "Review_Notes" TEXT DEFAULT '',
            "Review_Status" TEXT DEFAULT '',
            "created_at" TIMESTAMP DEFAULT NOW(),
            "updated_at" TIMESTAMP DEFAULT NOW(),
            "delivery_date" TIMESTAMP
        );
    """)
    cur.close()
    conn.close()
    yield
    # Teardown: drop test tables
    conn = psycopg2.connect(TEST_DB_URL)
    conn.autocommit = True
    cur = conn.cursor()
    for t in ['poi_audit_log', 'reviewers', 'poi_updates', 'final_delivery']:
        cur.execute(f'DROP TABLE IF EXISTS {t} CASCADE;')
    cur.close()
    conn.close()


@pytest.fixture(autouse=True)
def clean_db(request):
    """Clean POI data before each test (keep schema). Skips if no DB."""
    if not _has_db:
        return  # No DB → skip cleanup (frontend tests)
    # Also skip for frontend smoke tests explicitly
    if 'frontend_smoke' in request.node.nodeid:
        return
    import psycopg2
    conn = psycopg2.connect(TEST_DB_URL)
    conn.autocommit = True
    cur = conn.cursor()
    cur.execute('DELETE FROM final_delivery;')
    for t in ['poi_audit_log', 'poi_updates']:
        cur.execute(f'DELETE FROM {t};' if _table_exists(cur, t) else 'SELECT 1;')
    cur.close()
    conn.close()


def _table_exists(cur, table):
    cur.execute("SELECT EXISTS(SELECT 1 FROM information_schema.tables WHERE table_name=%s);", (table,))
    return cur.fetchone()[0]


@pytest.fixture
def app(setup_test_db):
    """Flask app configured for testing with mock ArcGIS sync."""
    if not _has_db:
        pytest.skip('PostgreSQL test database not available')
    from unittest.mock import patch
    with patch.dict(os.environ, {'DATABASE_URL': TEST_DB_URL}):
        # Mock ArcGIS sync to avoid external calls
        with patch('poi_api_server.sync_to_arcgis'):
            # Re-import to pick up test DB URL
            import importlib
            import poi_api_server
            importlib.reload(poi_api_server)
            poi_api_server.DATABASE_URL = TEST_DB_URL
            poi_api_server.app.config['TESTING'] = True
            # Ensure tables created
            with poi_api_server.app.app_context():
                poi_api_server.ensure_tables()
                poi_api_server._seed_reviewers()
            yield poi_api_server.app


@pytest.fixture
def client(app):
    """Flask test client."""
    return app.test_client()


# ── Sample Data Fixtures ──

SAMPLE_POI_COMPLETE = {
    'Name_AR': 'مطعم الرياض',
    'Name_EN': 'Riyadh Restaurant',
    'Legal_Name': 'Riyadh Restaurant LLC',
    'Category': 'Restaurants',
    'Subcategory': 'Fast Food',
    'Company_Status': 'Open',
    'Latitude': '24.7136',
    'Longitude': '46.6753',
    'District_EN': 'Al Olaya',
    'District_AR': 'العليا',
    'Phone_Number': '+966512345678',
    'Email': 'info@riyadhrest.com',
    'Website': 'https://riyadhrest.com',
    'Working_Days': 'Daily',
    'Working_Hours': '09:00-23:00',
    'Exterior_Photo_URL': 'https://example.com/exterior.jpg',
    'Interior_Photo_URL': 'https://example.com/interior.jpg',
    'Menu_Photo_URL': 'https://example.com/menu.jpg',
    'Video_URL': 'https://example.com/video.mp4',
    'WiFi': 'Yes',
    'Dine_In': 'Yes',
    'Menu': 'Yes',
}

SAMPLE_POI_MINIMAL = {
    'Name_EN': 'Test Place',
    'Name_AR': 'مكان اختبار',
    'Category': 'Restaurants',
}

SAMPLE_POI_INVALID = {
    'Name_EN': '',
    'Name_AR': '',
    'Category': '',
    'Latitude': '0',
    'Longitude': '0',
}


@pytest.fixture
def sample_poi():
    return SAMPLE_POI_COMPLETE.copy()


@pytest.fixture
def minimal_poi():
    return SAMPLE_POI_MINIMAL.copy()


@pytest.fixture
def created_poi(client, sample_poi):
    """Create a POI and return its GlobalID."""
    resp = client.post('/api/pois', json=sample_poi)
    data = resp.get_json()
    return data['GlobalID']
