"""
POI API Server — Flask backend for Render deployment.
Serves REST API for POI_FINAL_Review.html dashboard.
"""
import json
import csv
import io
import os
import sys
import psycopg2
from psycopg2.extras import RealDictCursor
from flask import Flask, jsonify, request, Response, Blueprint
from flask_cors import CORS

# Database connection via URL (Render provides DATABASE_URL)
DATABASE_URL = os.environ.get('DATABASE_URL')
if not DATABASE_URL:
    DATABASE_URL = 'postgresql://postgres:postgres@localhost:5432/poi_server'

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
