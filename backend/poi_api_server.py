"""
POI API Server — Flask backend for Render deployment.
Serves REST API for POI_FINAL_Review.html dashboard.
"""
import json
import csv
import io
import os
import sys
import uuid
import time
import threading
import urllib.request
import urllib.parse
import psycopg2
from psycopg2.extras import RealDictCursor, Json
from flask import Flask, jsonify, request, Response, Blueprint
from flask_cors import CORS

# Database connection via URL (Render provides DATABASE_URL)
DATABASE_URL = os.environ.get('DATABASE_URL')
if not DATABASE_URL:
    DATABASE_URL = 'postgresql://postgres:postgres@localhost:5432/poi_server'

# ===== ArcGIS Feature Layer Sync =====
ARCGIS_LAYER_URL = os.environ.get('ARCGIS_LAYER_URL',
    'https://services5.arcgis.com/pYlVm2T6SvR7ytZv/arcgis/rest/services/Farq_pilot_2_2_26/FeatureServer/0')
ARCGIS_USERNAME = os.environ.get('ARCGIS_USERNAME', 'nagadco0000')
ARCGIS_PASSWORD = os.environ.get('ARCGIS_PASSWORD', 'Nagad$1390')

_arcgis_sync_token = {'token': None, 'expires': 0}

def _get_sync_token():
    """Get or refresh ArcGIS token for Feature Layer sync."""
    now = int(time.time() * 1000)
    if _arcgis_sync_token['token'] and _arcgis_sync_token['expires'] > now + 60000:
        return _arcgis_sync_token['token']
    try:
        data = urllib.parse.urlencode({
            'username': ARCGIS_USERNAME,
            'password': ARCGIS_PASSWORD,
            'referer': 'https://media-review-app-1.vercel.app',
            'f': 'json'
        }).encode()
        req = urllib.request.Request('https://www.arcgis.com/sharing/rest/generateToken', data=data)
        resp = urllib.request.urlopen(req, timeout=15)
        result = json.loads(resp.read().decode())
        if 'token' in result:
            _arcgis_sync_token['token'] = result['token']
            _arcgis_sync_token['expires'] = result.get('expires', now + 3600000)
            return result['token']
    except Exception as e:
        print(f'[ArcGIS Sync] Token error: {e}')
    return None

def _arcgis_post(endpoint, params):
    """POST to ArcGIS Feature Layer endpoint."""
    token = _get_sync_token()
    if not token:
        print('[ArcGIS Sync] No token available')
        return None
    params['token'] = token
    params['f'] = 'json'
    data = urllib.parse.urlencode(params).encode()
    try:
        req = urllib.request.Request(f'{ARCGIS_LAYER_URL}/{endpoint}', data=data)
        resp = urllib.request.urlopen(req, timeout=30)
        return json.loads(resp.read().decode())
    except Exception as e:
        print(f'[ArcGIS Sync] POST {endpoint} error: {e}')
        return None

def _find_feature_oid(global_id_db):
    """Find OBJECTID in Feature Layer by GlobalID_DB field."""
    token = _get_sync_token()
    if not token:
        return None
    params = urllib.parse.urlencode({
        'where': f"GlobalID_DB = '{global_id_db}'",
        'outFields': 'OBJECTID',
        'returnGeometry': 'false',
        'f': 'json',
        'token': token
    })
    try:
        url = f'{ARCGIS_LAYER_URL}/query?{params}'
        resp = urllib.request.urlopen(url, timeout=15)
        result = json.loads(resp.read().decode())
        features = result.get('features', [])
        if features:
            return features[0]['attributes']['OBJECTID']
    except Exception as e:
        print(f'[ArcGIS Sync] Query error: {e}')
    return None

# Fields that exist in the Feature Layer
_FL_FIELDS = {
    'GlobalID_DB','Name_AR','Name_EN','Legal_Name','Category','Subcategory',
    'Category_Level_3','Company_Status','District_AR','District_EN',
    'Building_Number','Floor_Number','Entrance_Location','Phone_Number',
    'Email','Website','Social_Media','Working_Days','Working_Hours',
    'Break_Time','Language','Cuisine','Payment_Methods','Commercial_License',
    'Menu_Barcode_URL','Delivery_Method','Exterior_Photo_URL','Interior_Photo_URL',
    'Menu_Photo_URL','Video_URL','Review_Status','Review_Notes','Review_Flag',
    'Menu','Drive_Thru','Dine_In','Only_Delivery','Reservation','WiFi','Music',
    'Valet_Parking','Has_Parking_Lot','Wheelchair_Accessible','Family_Seating',
    'Smoking_Area','Children_Area','Shisha','Live_Sports','Is_Landmark',
    'Is_Trending','Women_Prayer_Room','Iftar_Tent','Free_Entry'
}

def sync_to_arcgis(action, global_id, data=None):
    """Sync a POI change to ArcGIS Feature Layer (runs in background thread)."""
    def _sync():
        try:
            if action == 'create' and data:
                lat = float(data.get('Latitude', 0) or 0)
                lon = float(data.get('Longitude', 0) or 0)
                attrs = {'GlobalID_DB': global_id}
                for k, v in data.items():
                    if k in _FL_FIELDS and k != 'GlobalID_DB':
                        attrs[k] = str(v or '')
                feature = {
                    'geometry': {'x': lon, 'y': lat, 'spatialReference': {'wkid': 4326}},
                    'attributes': attrs
                }
                result = _arcgis_post('addFeatures', {'features': json.dumps([feature])})
                print(f'[ArcGIS Sync] Created: {result}')

            elif action == 'update' and data:
                oid = _find_feature_oid(global_id)
                if oid is None:
                    print(f'[ArcGIS Sync] OID not found for {global_id}, skipping update')
                    return
                attrs = {'OBJECTID': oid}
                geometry = None
                for k, v in data.items():
                    if k in _FL_FIELDS:
                        attrs[k] = str(v or '')
                    if k == 'Latitude' or k == 'Longitude':
                        geometry = True
                feature = {'attributes': attrs}
                if geometry:
                    lat = float(data.get('Latitude', 0) or 0)
                    lon = float(data.get('Longitude', 0) or 0)
                    if lat and lon:
                        feature['geometry'] = {'x': lon, 'y': lat, 'spatialReference': {'wkid': 4326}}
                result = _arcgis_post('updateFeatures', {'features': json.dumps([feature])})
                print(f'[ArcGIS Sync] Updated: {result}')

            elif action == 'delete':
                oid = _find_feature_oid(global_id)
                if oid is None:
                    print(f'[ArcGIS Sync] OID not found for {global_id}, skipping delete')
                    return
                result = _arcgis_post('deleteFeatures', {'objectIds': str(oid)})
                print(f'[ArcGIS Sync] Deleted: {result}')

        except Exception as e:
            print(f'[ArcGIS Sync] Error ({action}): {e}')

    threading.Thread(target=_sync, daemon=True).start()

app = Flask(__name__)
CORS(app)

api = Blueprint('api', __name__, url_prefix='/api')

def get_db():
    conn = psycopg2.connect(DATABASE_URL)
    conn.set_client_encoding('UTF8')
    return conn

# ===== API: Get all POIs =====
@api.route('/pois', methods=['GET'])
def get_pois():
    try:
        conn = get_db()
        cur = conn.cursor(cursor_factory=RealDictCursor)
        cur.execute('SELECT * FROM final_delivery ORDER BY "Name_EN";')
        rows = cur.fetchall()
        cur.close()
        conn.close()
        result = []
        for row in rows:
            d = {}
            for k, v in row.items():
                if k in ('created_at', 'updated_at', 'delivery_date'):
                    d[k] = str(v) if v else ''
                else:
                    d[k] = v if v is not None else ''
            result.append(d)
        return jsonify(result)
    except Exception as e:
        import traceback
        return jsonify({'error': str(e), 'traceback': traceback.format_exc()}), 500

# ===== API: Get single POI =====
@api.route('/pois/<globalid>', methods=['GET'])
def get_poi(globalid):
    conn = get_db()
    cur = conn.cursor(cursor_factory=RealDictCursor)
    cur.execute('SELECT * FROM final_delivery WHERE "GlobalID" = %s;', (globalid,))
    row = cur.fetchone()
    cur.close()
    conn.close()
    if not row:
        return jsonify({'error': 'Not found'}), 404
    d = {k: (str(v) if k in ('created_at', 'updated_at', 'delivery_date') else (v or '')) for k, v in row.items()}
    return jsonify(d)

# ===== API: Update POI fields =====
@api.route('/pois/<globalid>', methods=['PATCH'])
def update_poi(globalid):
    data = request.get_json()
    if not data:
        return jsonify({'error': 'No data'}), 400

    conn = get_db()
    cur = conn.cursor()

    sets = []
    vals = []
    for field, value in data.items():
        if field in ('GlobalID', 'created_at', 'updated_at', 'delivery_date'):
            continue
        sets.append(f'"{field}" = %s')
        vals.append(value)

    if not sets:
        cur.close()
        conn.close()
        return jsonify({'error': 'No valid fields'}), 400

    sets.append('"updated_at" = NOW()')
    vals.append(globalid)

    sql = f'UPDATE final_delivery SET {", ".join(sets)} WHERE "GlobalID" = %s'
    cur.execute(sql, vals)
    updated = cur.rowcount
    conn.commit()
    cur.close()
    conn.close()

    if updated == 0:
        return jsonify({'error': 'Not found'}), 404
    sync_to_arcgis('update', globalid, data)
    return jsonify({'ok': True, 'updated': updated, 'globalid': globalid})

# ===== API: Bulk update =====
@api.route('/pois/bulk', methods=['PATCH'])
def bulk_update():
    data = request.get_json()
    if not data or not isinstance(data, list):
        return jsonify({'error': 'Expected array of {GlobalID, ...fields}'}), 400

    conn = get_db()
    cur = conn.cursor()
    updated = 0

    for item in data:
        gid = item.get('GlobalID')
        if not gid:
            continue
        sets = []
        vals = []
        for field, value in item.items():
            if field in ('GlobalID', 'created_at', 'updated_at', 'delivery_date'):
                continue
            sets.append(f'"{field}" = %s')
            vals.append(value)
        if not sets:
            continue
        sets.append('"updated_at" = NOW()')
        vals.append(gid)
        cur.execute(f'UPDATE final_delivery SET {", ".join(sets)} WHERE "GlobalID" = %s', vals)
        updated += cur.rowcount

    conn.commit()
    cur.close()
    conn.close()
    return jsonify({'ok': True, 'updated': updated})

# ===== API: Export as CSV =====
@api.route('/pois/export', methods=['GET'])
def export_csv_api():
    conn = get_db()
    cur = conn.cursor(cursor_factory=RealDictCursor)
    cur.execute('SELECT * FROM final_delivery ORDER BY "Name_EN";')
    rows = cur.fetchall()
    cur.close()
    conn.close()

    if not rows:
        return Response('No data', mimetype='text/plain')

    output = io.StringIO()
    skip = {'created_at', 'updated_at', 'delivery_date'}
    fieldnames = [k for k in rows[0].keys() if k not in skip]
    writer = csv.DictWriter(output, fieldnames=fieldnames)
    writer.writeheader()
    for row in rows:
        writer.writerow({k: (row[k] or '') for k in fieldnames})

    return Response(
        '\ufeff' + output.getvalue(),
        mimetype='text/csv; charset=utf-8',
        headers={'Content-Disposition': 'attachment; filename=POI_FINAL_from_DB.csv'}
    )

# ===== API: Stats =====
@api.route('/stats', methods=['GET'])
def get_stats():
    conn = get_db()
    cur = conn.cursor()
    cur.execute('SELECT COUNT(*) FROM final_delivery;')
    total = cur.fetchone()[0]
    cur.execute('SELECT COUNT(*) FROM final_delivery WHERE "Review_Status" = %s;', ('Reviewed',))
    reviewed = cur.fetchone()[0]
    cur.execute("SELECT COUNT(*) FROM final_delivery WHERE \"Review_Flag\" IS NOT NULL AND \"Review_Flag\" != '';")
    flagged = cur.fetchone()[0]
    cur.execute("SELECT AVG(NULLIF(\"QA_Score\",'')::numeric) FROM final_delivery;")
    avg_qa = cur.fetchone()[0]
    cur.close()
    conn.close()
    return jsonify({
        'total': total, 'reviewed': reviewed, 'flagged': flagged,
        'avg_qa': round(float(avg_qa or 0), 1)
    })

# ===== API: Delete POI =====
@api.route('/pois/<globalid>', methods=['DELETE'])
def delete_poi(globalid):
    conn = get_db()
    cur = conn.cursor()
    cur.execute('DELETE FROM final_delivery WHERE "GlobalID" = %s;', (globalid,))
    deleted = cur.rowcount
    conn.commit()
    cur.close()
    conn.close()
    if deleted == 0:
        return jsonify({'error': 'Not found'}), 404
    sync_to_arcgis('delete', globalid)
    return jsonify({'ok': True, 'deleted': deleted})

# ===== API: ArcGIS Token Proxy =====
@api.route('/arcgis-token', methods=['GET'])
def arcgis_token():
    import requests as req
    username = os.environ.get('ARCGIS_USERNAME', 'nagadco0000')
    password = os.environ.get('ARCGIS_PASSWORD', 'Nagad$1390')
    referer = os.environ.get('ARCGIS_REFERER', 'https://media-review-app.vercel.app')
    try:
        r = req.post('https://www.arcgis.com/sharing/rest/generateToken', data={
            'username': username, 'password': password,
            'client': 'referer', 'referer': referer,
            'expiration': 120, 'f': 'json'
        }, timeout=30)
        d = r.json()
        if 'token' in d:
            return jsonify({'token': d['token']})
        return jsonify({'error': d.get('error', {}).get('message', 'Unknown error')}), 401
    except Exception as e:
        return jsonify({'error': str(e)}), 500

# ===== API: ArcGIS Image Proxy (HEIC → JPEG conversion) =====
_agol_token_cache = {'token': None, 'expires': 0}

def _get_agol_token():
    import requests as req, time
    now = time.time() * 1000
    if _agol_token_cache['token'] and _agol_token_cache['expires'] > now + 60000:
        return _agol_token_cache['token']
    username = os.environ.get('ARCGIS_USERNAME', 'nagadco0000')
    password = os.environ.get('ARCGIS_PASSWORD', 'Nagad$1390')
    referer = os.environ.get('ARCGIS_REFERER', 'https://media-review-app.vercel.app')
    r = req.post('https://www.arcgis.com/sharing/rest/generateToken', data={
        'username': username, 'password': password,
        'client': 'referer', 'referer': referer,
        'expiration': 120, 'f': 'json'
    }, timeout=30)
    d = r.json()
    if 'token' in d:
        _agol_token_cache['token'] = d['token']
        _agol_token_cache['expires'] = d.get('expires', now + 7200000)
        return d['token']
    return None

@api.route('/arcgis-image', methods=['GET'])
def arcgis_image_proxy():
    """Proxy ArcGIS attachment URLs, converting HEIC to JPEG for browser display."""
    import requests as req
    url = request.args.get('url', '')
    if not url or 'arcgis.com' not in url:
        return 'Bad URL', 400

    token = _get_agol_token()
    if not token:
        return 'Token failed', 500

    try:
        r = req.get(url, params={'token': token}, timeout=30, stream=True)
        ct = r.headers.get('Content-Type', '').lower()

        if 'heic' in ct or 'heif' in ct:
            import pillow_heif
            from PIL import Image
            heif_file = pillow_heif.read_heif(r.content)
            img = Image.frombytes(heif_file.mode, heif_file.size, heif_file.data, 'raw')
            buf = io.BytesIO()
            img.save(buf, format='JPEG', quality=85)
            buf.seek(0)
            return Response(buf.read(), mimetype='image/jpeg',
                          headers={'Cache-Control': 'public, max-age=3600'})
        else:
            return Response(r.content, mimetype=ct or 'application/octet-stream',
                          headers={'Cache-Control': 'public, max-age=3600'})
    except Exception as e:
        return f'Proxy error: {e}', 500

# ===== API: Search ArcGIS features by name and get attachments =====
@api.route('/arcgis-search', methods=['GET'])
def arcgis_search_features():
    """Search ArcGIS features by name and return matching features with attachments."""
    import requests as req
    q = request.args.get('q', '').strip()
    if not q or len(q) < 2:
        return jsonify({'error': 'Query too short (min 2 chars)'}), 400

    token = _get_agol_token()
    if not token:
        return jsonify({'error': 'Token failed'}), 500

    base = 'https://services5.arcgis.com/pYlVm2T6SvR7ytZv/arcgis/rest/services/survey123_1ed04c063d54418b893c165594e88840_results/FeatureServer/0'

    where_clause = f"poi_name_en LIKE '%{q}%' OR poi_name_ar LIKE '%{q}%' OR place_name LIKE '%{q}%'"
    try:
        r = req.get(f'{base}/query', params={
            'where': where_clause,
            'outFields': 'objectid,globalid,poi_name_en,poi_name_ar,place_name',
            'resultRecordCount': 50,
            'f': 'json',
            'token': token
        }, timeout=30)
        data = r.json()
        features = data.get('features', [])
    except Exception as e:
        return jsonify({'error': f'Query failed: {e}'}), 500

    if not features:
        return jsonify({'results': []})

    # Get attachments for matching features
    oids = [f['attributes']['objectid'] for f in features if f['attributes'].get('objectid')]
    att_map = {}
    for i in range(0, len(oids), 50):
        batch = oids[i:i+50]
        try:
            ar = req.get(f'{base}/queryAttachments', params={
                'objectIds': ','.join(str(o) for o in batch),
                'f': 'json', 'token': token
            }, timeout=30)
            ad = ar.json()
            for group in ad.get('attachmentGroups', []):
                pid = group['parentObjectId']
                att_map[pid] = group.get('attachmentInfos', [])
        except:
            pass

    results = []
    for f in features:
        a = f['attributes']
        oid = a.get('objectid')
        atts = att_map.get(oid, [])
        att_list = []
        for att in atts:
            url = f"{base}/{oid}/attachments/{att['id']}"
            name = (att.get('name', '') or '').lower()
            kw = (att.get('keywords', '') or '').lower()
            ct = (att.get('contentType', '') or '').lower()
            is_vid = 'video' in ct or name.endswith('.mov') or name.endswith('.mp4')

            mtype = 'other'
            if 'exterior' in kw or 'entrance' in kw or 'exterior' in name or 'entrance' in name:
                mtype = 'exterior'
            elif 'interior' in kw or 'walkthrough' in kw or 'interior' in name:
                mtype = 'interior'
            elif 'menu' in kw or 'menu' in name:
                mtype = 'menu'
            elif is_vid:
                mtype = 'video'
            elif 'license' in kw or 'licence' in kw or 'license' in name:
                mtype = 'license'

            att_list.append({
                'url': url,
                'name': att.get('name', ''),
                'contentType': ct,
                'size_kb': round((att.get('size', 0) or 0) / 1024, 1),
                'keywords': att.get('keywords', ''),
                'type': mtype
            })

        results.append({
            'objectid': oid,
            'globalid': a.get('globalid', ''),
            'name_en': a.get('poi_name_en', '') or a.get('place_name', ''),
            'name_ar': a.get('poi_name_ar', ''),
            'attachments': att_list,
            'att_count': len(att_list)
        })

    return jsonify({'results': results})

# ===== API: Create new POI =====
@api.route('/pois', methods=['POST'])
def create_poi():
    data = request.get_json()
    if not data:
        return jsonify({'error': 'No data'}), 400

    gid = data.get('GlobalID') or '{' + str(uuid.uuid4()).upper() + '}'

    conn = get_db()
    cur = conn.cursor()

    # Get column names from table
    cur.execute("SELECT column_name FROM information_schema.columns WHERE table_name = 'final_delivery' ORDER BY ordinal_position;")
    all_cols = [r[0] for r in cur.fetchall()]
    skip = {'created_at', 'updated_at', 'delivery_date'}

    cols = ['"GlobalID"']
    vals = [gid]
    placeholders = ['%s']

    for col in all_cols:
        if col in skip or col == 'GlobalID':
            continue
        if col in data:
            cols.append(f'"{col}"')
            vals.append(data[col])
            placeholders.append('%s')

    cols.append('"created_at"')
    placeholders.append('NOW()')
    cols.append('"updated_at"')
    placeholders.append('NOW()')

    sql = f'INSERT INTO final_delivery ({", ".join(cols)}) VALUES ({", ".join(placeholders)})'
    try:
        cur.execute(sql, vals)
        conn.commit()
    except Exception as e:
        conn.rollback()
        cur.close()
        conn.close()
        return jsonify({'error': str(e)}), 500

    cur.close()
    conn.close()
    data['GlobalID'] = gid
    sync_to_arcgis('create', gid, data)
    return jsonify({'ok': True, 'GlobalID': gid}), 201

# ===== API: Survey123 Webhook =====
SURVEY123_FIELD_MAP = {
    'poi_name_en': 'Name_EN', 'poi_name_ar': 'Name_AR', 'legal_name': 'Legal_Name',
    'category': 'Category', 'secondary_category': 'Subcategory', 'category_level_3': 'Category_Level_3',
    'company_status': 'Company_Status', 'latitude': 'Latitude', 'longitude': 'Longitude',
    'building_number': 'Building_Number', 'floor_number': 'Floor_Number',
    'entrance_location': 'Entrance_Location', 'phone_number': 'Phone_Number',
    'email': 'Email', 'website': 'Website', 'social_media': 'Social_Media',
    'working_days': 'Working_Days', 'working_hours': 'Working_Hours',
    'break_time': 'Break_Time', 'holidays': 'Holidays',
    'menu_barcode_url': 'Menu_Barcode_URL', 'language': 'Language',
    'cuisine': 'Cuisine', 'payment_methods': 'Payment_Methods',
    'commercial_license': 'Commercial_License', 'district_en': 'District_EN',
    'district_ar': 'District_AR', 'place_name': 'Name_EN',
    'exterior_photo_url': 'Exterior_Photo_URL', 'interior_photo_url': 'Interior_Photo_URL',
    'menu_photo_url': 'Menu_Photo_URL', 'video_url': 'Video_URL',
}

def _ensure_updates_table(conn):
    cur = conn.cursor()
    cur.execute("""
        CREATE TABLE IF NOT EXISTS poi_updates (
            id SERIAL PRIMARY KEY,
            global_id TEXT,
            poi_name TEXT,
            source TEXT DEFAULT 'survey123',
            action TEXT DEFAULT 'update',
            changed_fields JSONB,
            created_at TIMESTAMP DEFAULT NOW(),
            acknowledged BOOLEAN DEFAULT FALSE
        );
    """)
    conn.commit()
    cur.close()

@api.route('/webhook/survey123', methods=['POST'])
def survey123_webhook():
    payload = request.get_json(silent=True)
    if not payload:
        return jsonify({'error': 'No data'}), 400

    # Survey123 webhook can send: { feature: { attributes: {...}, geometry: {...} } }
    # or direct attributes, or eventType + feature
    attrs = {}
    if 'feature' in payload:
        feat = payload['feature']
        attrs = feat.get('attributes', feat)
        geo = feat.get('geometry', {})
        if geo.get('x') and 'longitude' not in attrs:
            attrs['longitude'] = geo['x']
        if geo.get('y') and 'latitude' not in attrs:
            attrs['latitude'] = geo['y']
    elif 'attributes' in payload:
        attrs = payload['attributes']
    else:
        attrs = payload

    # Map Survey123 field names to DB field names
    mapped = {}
    for s_field, value in attrs.items():
        key = s_field.lower().replace(' ', '_')
        db_field = SURVEY123_FIELD_MAP.get(key)
        if db_field and value is not None:
            mapped[db_field] = str(value) if value is not None else ''
        elif s_field in ('Name_EN', 'Name_AR', 'Category', 'Latitude', 'Longitude'):
            mapped[s_field] = str(value) if value is not None else ''

    if not mapped:
        return jsonify({'error': 'No mappable fields'}), 400

    conn = get_db()
    _ensure_updates_table(conn)
    cur = conn.cursor(cursor_factory=RealDictCursor)

    # Try to find existing POI by name match
    name_en = mapped.get('Name_EN', '')
    name_ar = mapped.get('Name_AR', '')
    existing = None

    if name_en:
        cur.execute('SELECT "GlobalID", "Name_EN" FROM final_delivery WHERE "Name_EN" = %s LIMIT 1;', (name_en,))
        existing = cur.fetchone()
    if not existing and name_ar:
        cur.execute('SELECT "GlobalID", "Name_EN" FROM final_delivery WHERE "Name_AR" = %s LIMIT 1;', (name_ar,))
        existing = cur.fetchone()

    if existing:
        # UPDATE existing POI
        gid = existing['GlobalID']
        sets = []
        vals = []
        changed = {}
        for field, value in mapped.items():
            if field in ('GlobalID',):
                continue
            sets.append(f'"{field}" = %s')
            vals.append(value)
            changed[field] = value
        if sets:
            sets.append('"updated_at" = NOW()')
            vals.append(gid)
            cur.execute(f'UPDATE final_delivery SET {", ".join(sets)} WHERE "GlobalID" = %s', vals)

            # Log update
            cur.execute(
                'INSERT INTO poi_updates (global_id, poi_name, source, action, changed_fields) VALUES (%s, %s, %s, %s, %s)',
                (gid, name_en or name_ar, 'survey123', 'update', Json(changed))
            )
            conn.commit()
        cur.close()
        conn.close()
        sync_to_arcgis('update', gid, mapped)
        return jsonify({'ok': True, 'action': 'updated', 'GlobalID': gid, 'fields': len(changed)})
    else:
        # INSERT new POI
        gid = '{' + str(uuid.uuid4()).upper() + '}'
        mapped['GlobalID'] = gid

        cols = []
        vals = []
        placeholders = []
        for field, value in mapped.items():
            cols.append(f'"{field}"')
            vals.append(value)
            placeholders.append('%s')
        cols.append('"created_at"')
        placeholders.append('NOW()')
        cols.append('"updated_at"')
        placeholders.append('NOW()')

        try:
            cur.execute(f'INSERT INTO final_delivery ({", ".join(cols)}) VALUES ({", ".join(placeholders)})', vals)
            cur.execute(
                'INSERT INTO poi_updates (global_id, poi_name, source, action, changed_fields) VALUES (%s, %s, %s, %s, %s)',
                (gid, name_en or name_ar, 'survey123', 'create', Json(mapped))
            )
            conn.commit()
        except Exception as e:
            conn.rollback()
            cur.close()
            conn.close()
            return jsonify({'error': str(e)}), 500

        cur.close()
        conn.close()
        sync_to_arcgis('create', gid, mapped)
        return jsonify({'ok': True, 'action': 'created', 'GlobalID': gid}), 201

# ===== API: Recent updates (for notifications) =====
@api.route('/pois/recent-updates', methods=['GET'])
def recent_updates():
    conn = get_db()
    _ensure_updates_table(conn)
    cur = conn.cursor(cursor_factory=RealDictCursor)
    cur.execute("""
        SELECT id, global_id, poi_name, source, action, changed_fields,
               created_at::text as created_at, acknowledged
        FROM poi_updates
        WHERE acknowledged = FALSE
        ORDER BY created_at DESC
        LIMIT 50;
    """)
    rows = cur.fetchall()
    cur.close()
    conn.close()
    return jsonify(rows)

@api.route('/pois/recent-updates/ack', methods=['POST'])
def ack_updates():
    data = request.get_json()
    ids = data.get('ids', []) if data else []
    conn = get_db()
    cur = conn.cursor()
    if ids:
        cur.execute('UPDATE poi_updates SET acknowledged = TRUE WHERE id = ANY(%s)', (ids,))
    else:
        cur.execute('UPDATE poi_updates SET acknowledged = TRUE WHERE acknowledged = FALSE')
    conn.commit()
    count = cur.rowcount
    cur.close()
    conn.close()
    return jsonify({'ok': True, 'acknowledged': count})

# Register API blueprint
app.register_blueprint(api)

# Health check
@app.route('/')
def health():
    return jsonify({'status': 'ok', 'service': 'POI API Server'})

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 8080))
    print(f'POI API Server starting on port {port}')
    app.run(host='0.0.0.0', port=port, debug=False)
