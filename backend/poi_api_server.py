"""
POI API Server — Flask backend for Render deployment.
Serves REST API for POI_FINAL_Review.html dashboard.
"""
import json
import csv
import io
import os
import sys
import re
import uuid
import time
import datetime
import gzip
import hashlib
import threading
from concurrent.futures import ThreadPoolExecutor
import urllib.request
import urllib.parse
import psycopg2
from psycopg2.extras import RealDictCursor, Json
from flask import Flask, jsonify, request, Response, Blueprint, stream_with_context
from flask_cors import CORS
import requests as req_lib
from api_responses import (
    success as api_success, error as api_error,
    NOT_FOUND, VALIDATION_ERROR, CONFLICT, INVALID_TRANSITION, INTERNAL_ERROR
)
from lifecycle import (
    MAJOR_FIELDS, VALID_TRANSITIONS, can_transition, validate_transition,
    get_approval_blockers, should_auto_revert
)

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

    _arcgis_pool.submit(_sync)

# Bounded thread pool for ArcGIS sync (prevents unbounded thread/memory growth)
_arcgis_pool = ThreadPoolExecutor(max_workers=3, thread_name_prefix='arcgis')

app = Flask(__name__)

# Custom JSON provider for datetime objects (Flask 3.x)
from flask.json.provider import DefaultJSONProvider
class DateTimeJSONProvider(DefaultJSONProvider):
    def default(self, o):
        if isinstance(o, (datetime.datetime, datetime.date)):
            return o.isoformat()
        return super().default(o)
app.json_provider_class = DateTimeJSONProvider
app.json = DateTimeJSONProvider(app)

CORS(app)

api = Blueprint('api', __name__, url_prefix='/api')

def get_db():
    conn = psycopg2.connect(DATABASE_URL)
    conn.set_client_encoding('UTF8')
    return conn

# ===== Initialize audit log + reviewer tables =====
def _init_audit_tables(conn):
    cur = conn.cursor()
    cur.execute("""
        CREATE TABLE IF NOT EXISTS reviewers (
            id SERIAL PRIMARY KEY,
            username TEXT UNIQUE NOT NULL,
            display_name TEXT NOT NULL,
            password_hash TEXT NOT NULL,
            role TEXT DEFAULT 'reviewer',
            active BOOLEAN DEFAULT TRUE,
            created_at TIMESTAMP DEFAULT NOW()
        );
    """)
    cur.execute("""
        CREATE TABLE IF NOT EXISTS poi_audit_log (
            id SERIAL PRIMARY KEY,
            global_id TEXT NOT NULL,
            poi_name TEXT,
            reviewer TEXT,
            action TEXT DEFAULT 'update',
            field_name TEXT,
            old_value TEXT,
            new_value TEXT,
            created_at TIMESTAMP DEFAULT NOW()
        );
    """)
    cur.execute("CREATE INDEX IF NOT EXISTS idx_audit_global_id ON poi_audit_log(global_id);")
    cur.execute("CREATE INDEX IF NOT EXISTS idx_audit_reviewer ON poi_audit_log(reviewer);")
    cur.execute("CREATE INDEX IF NOT EXISTS idx_audit_created ON poi_audit_log(created_at DESC);")
    # Migrate: add 'action' column if table predates it
    cur.execute("""
        DO $$ BEGIN
            ALTER TABLE poi_audit_log ADD COLUMN action TEXT DEFAULT 'update';
        EXCEPTION WHEN duplicate_column THEN NULL;
        END $$;
    """)
    conn.commit()
    cur.close()

def _init_match_reviews_table(conn):
    """Create table for storing human match/no-match review decisions (ML training data)."""
    cur = conn.cursor()
    cur.execute("""
        CREATE TABLE IF NOT EXISTS match_reviews (
            id SERIAL PRIMARY KEY,
            source_gid TEXT NOT NULL,
            candidate_gid TEXT NOT NULL,
            source_name TEXT,
            candidate_name TEXT,
            reviewer TEXT NOT NULL,
            verdict TEXT NOT NULL CHECK (verdict IN ('MATCH', 'NOT_MATCH')),
            final_score REAL,
            name_score REAL,
            distance_score REAL,
            category_score REAL,
            phone_score REAL,
            auxiliary_score REAL,
            distance_m REAL,
            source_category TEXT,
            candidate_category TEXT,
            source_lat REAL,
            source_lng REAL,
            candidate_lat REAL,
            candidate_lng REAL,
            match_reasons TEXT,
            tier1_match BOOLEAN DEFAULT FALSE,
            notes TEXT,
            created_at TIMESTAMP DEFAULT NOW()
        );
    """)
    cur.execute("CREATE INDEX IF NOT EXISTS idx_mr_source ON match_reviews(source_gid);")
    cur.execute("CREATE INDEX IF NOT EXISTS idx_mr_candidate ON match_reviews(candidate_gid);")
    cur.execute("CREATE INDEX IF NOT EXISTS idx_mr_reviewer ON match_reviews(reviewer);")
    cur.execute("CREATE INDEX IF NOT EXISTS idx_mr_verdict ON match_reviews(verdict);")
    cur.execute("""
        CREATE UNIQUE INDEX IF NOT EXISTS idx_mr_pair_reviewer
        ON match_reviews(source_gid, candidate_gid, reviewer);
    """)
    conn.commit()
    cur.close()

def _init_draft_table(conn):
    cur = conn.cursor()
    cur.execute("""
        CREATE TABLE IF NOT EXISTS draft_pois (
            id SERIAL PRIMARY KEY,
            "GlobalID" TEXT UNIQUE NOT NULL,
            "Name_AR" TEXT, "Name_EN" TEXT, "Legal_Name" TEXT,
            "Category" TEXT, "Subcategory" TEXT, "Category_Level_3" TEXT,
            "Company_Status" TEXT,
            "Latitude" TEXT, "Longitude" TEXT, "Google_Map_URL" TEXT,
            "Building_Number" TEXT, "Floor_Number" TEXT, "Entrance_Location" TEXT,
            "Phone_Number" TEXT, "Email" TEXT, "Website" TEXT, "Social_Media" TEXT,
            "Working_Days" TEXT, "Working_Hours" TEXT, "Break_Time" TEXT, "Holidays" TEXT,
            "Menu_Barcode_URL" TEXT, "Language" TEXT, "Cuisine" TEXT,
            "Payment_Methods" TEXT, "Commercial_License" TEXT,
            "Exterior_Photo_URL" TEXT, "Interior_Photo_URL" TEXT,
            "Menu_Photo_URL" TEXT, "Video_URL" TEXT,
            "Amenities" TEXT, "District_AR" TEXT, "District_EN" TEXT,
            "Menu" TEXT, "Drive_Thru" TEXT, "Dine_In" TEXT, "Only_Delivery" TEXT,
            "Reservation" TEXT, "Require_Ticket" TEXT, "Order_from_Car" TEXT,
            "Pickup_Point" TEXT, "WiFi" TEXT, "Music" TEXT, "Valet_Parking" TEXT,
            "Has_Parking_Lot" TEXT, "Wheelchair_Accessible" TEXT, "Family_Seating" TEXT,
            "Waiting_Area" TEXT, "Private_Dining" TEXT, "Smoking_Area" TEXT,
            "Children_Area" TEXT, "Shisha" TEXT, "Live_Sports" TEXT,
            "Is_Landmark" TEXT, "Is_Trending" TEXT, "Large_Groups" TEXT,
            "Women_Prayer_Room" TEXT, "Iftar_Tent" TEXT, "Iftar_Menu" TEXT,
            "Open_Suhoor" TEXT, "Free_Entry" TEXT,
            "Source" TEXT, "QA_Score" TEXT,
            "Review_Flag" TEXT, "Review_Notes" TEXT, "Review_Status" TEXT,
            "Additional_Photo_URLs" TEXT, "License_Photo_URL" TEXT,
            "Draft_Status" TEXT DEFAULT 'pending',
            "Dup_Verdict" TEXT, "Dup_Score" TEXT,
            "Match_Type" TEXT, "Similarity" TEXT, "Distance_m" TEXT,
            "Matched_Name" TEXT, "Matched_GID" TEXT,
            "Original_Category" TEXT, "Original_Subcategory" TEXT,
            "Source_CSV" TEXT, "Import_Batch" TEXT,
            "QA_Blockers" INTEGER DEFAULT 0, "QA_Warnings" INTEGER DEFAULT 0,
            "Reviewed_By" TEXT, "Reviewed_At" TIMESTAMP,
            created_at TIMESTAMP DEFAULT NOW(),
            updated_at TIMESTAMP DEFAULT NOW()
        );
    """)
    cur.execute("CREATE INDEX IF NOT EXISTS idx_draft_status ON draft_pois(\"Draft_Status\");")
    cur.execute("CREATE INDEX IF NOT EXISTS idx_draft_verdict ON draft_pois(\"Dup_Verdict\");")
    conn.commit()
    cur.close()

def _migrate_lifecycle_columns(conn):
    """Add lifecycle columns to final_delivery if they don't exist."""
    cur = conn.cursor()
    migrations = [
        ('flagged',          'BOOLEAN DEFAULT FALSE'),
        ('flag_reason',      "TEXT DEFAULT ''"),
        ('draft_reason',     "TEXT DEFAULT ''"),
        ('archived_reason',  "TEXT DEFAULT ''"),
        ('rejected_reason',  "TEXT DEFAULT ''"),
        ('last_reviewed_at', 'TIMESTAMP'),
        ('last_reviewed_by', "TEXT DEFAULT ''"),
        ('review_version',   'INTEGER DEFAULT 0'),
    ]
    for col_name, col_type in migrations:
        try:
            cur.execute(f'ALTER TABLE final_delivery ADD COLUMN "{col_name}" {col_type};')
        except Exception:
            conn.rollback()
    # Backfill: migrate Review_Status='Flagged' to flagged boolean overlay
    try:
        cur.execute("""
            UPDATE final_delivery
            SET "flagged" = TRUE,
                "flag_reason" = COALESCE("Review_Flag", ''),
                "Review_Status" = 'Draft',
                "draft_reason" = 'modified'
            WHERE "Review_Status" = 'Flagged';
        """)
    except Exception:
        conn.rollback()
    # Backfill: set draft_reason for existing Drafts without one
    try:
        cur.execute("""
            UPDATE final_delivery
            SET "draft_reason" = 'new'
            WHERE ("Review_Status" IS NULL OR "Review_Status" = '' OR "Review_Status" = 'Draft')
              AND ("draft_reason" IS NULL OR "draft_reason" = '');
        """)
    except Exception:
        conn.rollback()
    conn.commit()
    cur.close()

_tables_initialized = False
def ensure_tables():
    global _tables_initialized
    if _tables_initialized:
        return
    try:
        conn = get_db()
        _init_audit_tables(conn)
        _init_match_reviews_table(conn)
        _init_draft_table(conn)
        _migrate_lifecycle_columns(conn)
        conn.close()
        _tables_initialized = True
    except Exception as e:
        print(f'Table init error: {e}')

import hashlib
def _hash_pw(pw):
    return hashlib.sha256(pw.encode()).hexdigest()

def _seed_reviewers():
    """Seed initial reviewer accounts."""
    conn = get_db()
    cur = conn.cursor()
    reviewers = [
        ('waleed', 'Waleed', 'waleed123'),
        ('fadhel', 'Fadhel', 'fadhel123'),
        ('ruwaida', 'Ruwaida', 'ruwaida123'),
        ('abdulrhman', 'Abdulrhman', 'abdulrhman123'),
        ('naver', 'Naver', 'naver123'),
        ('annivation', 'Annivation', 'annivation123'),
    ]
    for uname, dname, pw in reviewers:
        cur.execute("SELECT id FROM reviewers WHERE username = %s", (uname,))
        if not cur.fetchone():
            cur.execute(
                "INSERT INTO reviewers (username, display_name, password_hash) VALUES (%s, %s, %s)",
                (uname, dname, _hash_pw(pw))
            )
    conn.commit()
    cur.close()
    conn.close()

# MAJOR_FIELDS imported from lifecycle.py

# ===== Audit logging helper =====
def log_audit(conn, global_id, poi_name, reviewer, action, changes_dict,
              old_data=None, action_reason=None):
    """Log field-level changes + action-level event to poi_audit_log.

    action should be one of: edit, approve, reject, archive, unarchive, flag,
    unflag, bulk_edit, create, delete, auto_revert
    """
    cur = conn.cursor()
    # 1) Always insert an action-level row (no field_name) for non-edit actions
    if action != 'edit' and action != 'update':
        cur.execute(
            """INSERT INTO poi_audit_log
               (global_id, poi_name, reviewer, action, field_name, old_value, new_value)
               VALUES (%s, %s, %s, %s, %s, %s, %s)""",
            (global_id, poi_name or '', reviewer or 'unknown', action,
             None, None, action_reason or '')
        )
    # 2) Field-level diff rows
    for field, new_val in changes_dict.items():
        if field in ('GlobalID', 'created_at', 'updated_at', 'delivery_date'):
            continue
        old_val = ''
        if old_data:
            old_val = str(old_data.get(field, '') or '')
        new_val_str = str(new_val or '')
        if old_val == new_val_str:
            continue
        cur.execute(
            """INSERT INTO poi_audit_log (global_id, poi_name, reviewer, action, field_name, old_value, new_value)
               VALUES (%s, %s, %s, %s, %s, %s, %s)""",
            (global_id, poi_name or '', reviewer or 'unknown', action, field, old_val, new_val_str)
        )
    cur.close()

# ===== API: Get all POIs =====
@api.route('/pois', methods=['GET'])
def get_pois():
    try:
        conn = get_db()
        cur = conn.cursor(cursor_factory=RealDictCursor)

        # Optional server-side filtering (no params = return all for backward compat)
        where_clauses = []
        params = []
        status = request.args.get('status')
        if status:
            where_clauses.append('"Review_Status" = %s')
            params.append(status)
        flagged = request.args.get('flagged')
        if flagged and flagged.lower() == 'true':
            where_clauses.append('"flagged" = TRUE')
        elif flagged and flagged.lower() == 'false':
            where_clauses.append('("flagged" IS NULL OR "flagged" = FALSE)')
        ids = request.args.get('ids', '').strip()
        if ids:
            id_list = [i.strip() for i in ids.split(',') if i.strip()]
            if id_list:
                where_clauses.append('"GlobalID" = ANY(%s)')
                params.append(id_list)
        q = request.args.get('q', '').strip()
        if q:
            where_clauses.append('("Name_EN" ILIKE %s OR "Name_AR" ILIKE %s OR "GlobalID" ILIKE %s)')
            params.extend([f'%{q}%', f'%{q}%', f'%{q}%'])

        sql = 'SELECT * FROM final_delivery'
        if where_clauses:
            sql += ' WHERE ' + ' AND '.join(where_clauses)
        sql += ' ORDER BY "Name_EN"'

        # Optional pagination
        page = request.args.get('page')
        page_size = request.args.get('page_size', '50')
        if page is not None:
            try:
                offset = int(page) * int(page_size)
                sql += f' LIMIT {int(page_size)} OFFSET {offset}'
            except ValueError:
                pass

        cur.execute(sql, params)

        # Stream JSON row-by-row to avoid loading entire result set in memory
        def generate():
            yield '['
            first = True
            while True:
                row = cur.fetchone()
                if row is None:
                    break
                d = {}
                for k, v in row.items():
                    if v is None:
                        d[k] = ''
                    elif isinstance(v, (datetime.datetime, datetime.date)):
                        d[k] = v.isoformat()
                    else:
                        d[k] = v
                if not first:
                    yield ','
                first = False
                yield json.dumps(d, separators=(',', ':'))
            yield ']'
            cur.close()
            conn.close()

        resp = Response(stream_with_context(generate()), content_type='application/json')
        resp.headers['Cache-Control'] = 'no-cache'
        return resp
    except Exception as e:
        import traceback
        return api_error(str(e), 500, code=INTERNAL_ERROR, details=traceback.format_exc())

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
        return api_error('Not found', 404, code=NOT_FOUND)
    d = {k: (str(v) if k in ('created_at', 'updated_at', 'delivery_date') else (v or '')) for k, v in row.items()}
    return jsonify(d)

# ===== API: Update POI fields =====
@api.route('/pois/<globalid>', methods=['PATCH'])
def update_poi(globalid):
  try:
    data = request.get_json()
    if not data:
        return api_error('No data', 400, code=VALIDATION_ERROR)

    reviewer = data.pop('_reviewer', None) or request.headers.get('X-Reviewer', 'unknown')
    expected_version = data.pop('_expected_version', None)

    conn = get_db()
    ensure_tables()
    cur = conn.cursor(cursor_factory=RealDictCursor)

    # Fetch old values for audit
    cur.execute('SELECT * FROM final_delivery WHERE "GlobalID" = %s;', (globalid,))
    old_row = cur.fetchone()
    cur.close()

    if not old_row:
        conn.close()
        return api_error('Not found', 404, code=NOT_FOUND)

    # Optimistic concurrency check
    if expected_version is not None:
        current_version = old_row.get('review_version', 0) or 0
        if int(expected_version) != int(current_version):
            conn.close()
            return api_error('Modified by another user', 409, code=CONFLICT,
                           details={'current_version': current_version, 'expected_version': int(expected_version)})

    cur = conn.cursor()
    sets = []
    vals = []
    skip_keys = {'GlobalID', 'created_at', 'updated_at', 'delivery_date', '_reviewer', '_expected_version'}
    old_status = (old_row.get('Review_Status') or '').strip()

    # Validate status transition if Review_Status is being changed
    new_status = data.get('Review_Status')
    if new_status and new_status != old_status:
        ok, err_msg = validate_transition(old_status, new_status)
        if not ok:
            cur.close(); conn.close()
            return api_error(err_msg, 422, code=INVALID_TRANSITION)

    # Check if any MAJOR field has an actual value change
    editing_major = any(
        f in MAJOR_FIELDS and str(data[f] or '') != str(old_row.get(f, '') or '')
        for f in data.keys() if f not in skip_keys
    )

    for field, value in data.items():
        if field in ('GlobalID', 'created_at', 'updated_at', 'delivery_date'):
            continue
        sets.append(f'"{field}" = %s')
        vals.append(value)

    # Auto-revert: Reviewed + major edit → Draft (only if not explicitly setting status)
    if editing_major and old_status == 'Reviewed' and 'Review_Status' not in data:
        sets.append('"Review_Status" = %s')
        vals.append('Draft')
        sets.append('"draft_reason" = %s')
        vals.append('modified')

    # Approval metadata: when transitioning to Reviewed, set review tracking fields
    is_approving = data.get('Review_Status') == 'Reviewed' and old_status != 'Reviewed'
    if is_approving:
        sets.append('"last_reviewed_at" = NOW()')
        sets.append('"last_reviewed_by" = %s')
        vals.append(reviewer)
        sets.append('"review_version" = COALESCE("review_version", 0) + 1')
        # Only add draft_reason if not already in the payload (avoid duplicate SET)
        if 'draft_reason' not in data:
            sets.append('"draft_reason" = %s')
            vals.append('')

    if not sets:
        cur.close()
        conn.close()
        return api_error('No valid fields', 400, code=VALIDATION_ERROR)

    # Always bump version on update (unless approval already does it)
    if '"review_version" = COALESCE("review_version", 0) + 1' not in sets:
        sets.append('"review_version" = COALESCE("review_version", 0) + 1')

    sets.append('"updated_at" = NOW()')
    vals.append(globalid)

    sql = f'UPDATE final_delivery SET {", ".join(sets)} WHERE "GlobalID" = %s'
    cur.execute(sql, vals)
    updated = cur.rowcount

    # Determine action type for audit
    auto_reverted = (editing_major and old_status == 'Reviewed' and 'Review_Status' not in data)
    if data.get('Review_Status') == 'Reviewed' and old_status != 'Reviewed':
        audit_action = 'approve'
    elif auto_reverted:
        audit_action = 'auto_revert'
    else:
        audit_action = 'edit'

    # Log audit with action-level event
    poi_name = old_row.get('Name_EN') or old_row.get('Name_AR') or ''
    audit_changes = dict(data)
    if auto_reverted:
        audit_changes['Review_Status'] = 'Draft'
        audit_changes['draft_reason'] = 'modified'
    log_audit(conn, globalid, poi_name, reviewer, audit_action, audit_changes,
              old_data=old_row,
              action_reason='auto-revert: major field edited' if auto_reverted else None)

    conn.commit()

    # Get new version + status for frontend
    cur.execute('SELECT "review_version", "Review_Status", "draft_reason" FROM final_delivery WHERE "GlobalID" = %s', (globalid,))
    new_row = cur.fetchone()
    new_version = new_row[0] if new_row else 0
    new_status_val = new_row[1] if new_row else None
    new_draft_reason = new_row[2] if new_row else ''
    cur.close()
    conn.close()

    # Build enriched response
    changed_fields = [f for f in data.keys() if f not in skip_keys]
    response = {
        'updated': updated,
        'globalid': globalid,
        'review_version': new_version,
        'review_status': new_status_val,
        'changed_fields': changed_fields,
    }
    if auto_reverted:
        response['auto_reverted'] = True
        response['draft_reason'] = 'modified'

    sync_to_arcgis('update', globalid, data)
    return api_success(response)
  except Exception as e:
    import traceback
    return api_error(str(e), 500, code=INTERNAL_ERROR, details=traceback.format_exc())

# ===== API: Bulk update =====
@api.route('/pois/bulk', methods=['PATCH'])
def bulk_update():
    data = request.get_json()
    if not data or not isinstance(data, list):
        return api_error('Expected array of {GlobalID, ...fields}', 400, code=VALIDATION_ERROR)

    conn = get_db()
    cur = conn.cursor()
    updated = 0
    conflicts = []

    cur2 = conn.cursor(cursor_factory=RealDictCursor)
    for item in data:
        gid = item.get('GlobalID')
        if not gid:
            continue
        expected_version = item.pop('_expected_version', None)

        # Fetch current status for major/minor field check
        cur2.execute('SELECT "Review_Status", "review_version" FROM final_delivery WHERE "GlobalID" = %s', (gid,))
        current = cur2.fetchone()
        if not current:
            continue

        # Per-item optimistic concurrency check
        if expected_version is not None:
            current_version = current.get('review_version', 0) or 0
            if int(expected_version) != int(current_version):
                conflicts.append({'GlobalID': gid, 'current_version': current_version})
                continue

        old_status = (current.get('Review_Status') or '').strip()

        sets = []
        vals = []
        has_major = False
        skip_bulk = {'GlobalID', 'created_at', 'updated_at', 'delivery_date', '_reviewer', '_expected_version'}
        for field, value in item.items():
            if field in skip_bulk:
                continue
            sets.append(f'"{field}" = %s')
            vals.append(value)
            if field in MAJOR_FIELDS:
                has_major = True

        # Auto-revert: Reviewed + major edit → Draft
        if has_major and old_status == 'Reviewed' and 'Review_Status' not in item:
            sets.append('"Review_Status" = %s')
            vals.append('Draft')
            sets.append('"draft_reason" = %s')
            vals.append('modified')

        # Approval metadata
        if item.get('Review_Status') == 'Reviewed' and old_status != 'Reviewed':
            sets.append('"last_reviewed_at" = NOW()')
            sets.append('"draft_reason" = %s')
            vals.append('')

        if not sets:
            continue

        # Always bump version
        sets.append('"review_version" = COALESCE("review_version", 0) + 1')
        sets.append('"updated_at" = NOW()')
        vals.append(gid)
        cur.execute(f'UPDATE final_delivery SET {", ".join(sets)} WHERE "GlobalID" = %s', vals)
        updated += cur.rowcount
    cur2.close()

    conn.commit()
    cur.close()
    conn.close()
    result = {'updated': updated}
    if conflicts:
        result['conflicts'] = conflicts
    return api_success(result)

# ===== API: Export as CSV =====
@api.route('/pois/export', methods=['GET'])
def export_csv_api():
    conn = get_db()
    cur = conn.cursor(cursor_factory=RealDictCursor)
    skip = {'created_at', 'updated_at', 'delivery_date'}

    # Get column names from first row
    cur.execute('SELECT * FROM final_delivery ORDER BY "Name_EN" LIMIT 1;')
    first = cur.fetchone()
    if not first:
        cur.close()
        conn.close()
        return Response('No data', mimetype='text/plain')
    fieldnames = [k for k in first.keys() if k not in skip]

    # Stream CSV row-by-row
    cur.execute('SELECT * FROM final_delivery ORDER BY "Name_EN";')

    def generate():
        buf = io.StringIO()
        writer = csv.DictWriter(buf, fieldnames=fieldnames)
        # BOM + header
        buf.write('\ufeff')
        writer.writeheader()
        yield buf.getvalue()
        buf.seek(0)
        buf.truncate()
        while True:
            row = cur.fetchone()
            if row is None:
                break
            writer.writerow({k: (row[k] or '') for k in fieldnames})
            yield buf.getvalue()
            buf.seek(0)
            buf.truncate()
        cur.close()
        conn.close()

    return Response(
        stream_with_context(generate()),
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
    cur.execute("SELECT COUNT(*) FROM final_delivery WHERE \"Review_Status\" = 'Draft' OR \"Review_Status\" IS NULL OR \"Review_Status\" = '';")
    draft_count = cur.fetchone()[0]
    cur.execute('SELECT COUNT(*) FROM final_delivery WHERE "Review_Status" = %s;', ('Archived',))
    archived = cur.fetchone()[0]
    cur.execute('SELECT COUNT(*) FROM final_delivery WHERE "Review_Status" = %s;', ('Rejected',))
    rejected = cur.fetchone()[0]
    # Flagged is now a boolean overlay, not a status
    try:
        cur.execute('SELECT COUNT(*) FROM final_delivery WHERE "flagged" = TRUE;')
        flagged = cur.fetchone()[0]
    except Exception:
        conn.rollback()
        cur.execute("SELECT COUNT(*) FROM final_delivery WHERE \"Review_Flag\" IS NOT NULL AND \"Review_Flag\" != '';")
        flagged = cur.fetchone()[0]
    cur.execute("SELECT AVG(NULLIF(\"QA_Score\",'')::numeric) FROM final_delivery;")
    avg_qa = cur.fetchone()[0]
    cur.close()
    conn.close()
    return jsonify({
        'total': total, 'reviewed': reviewed, 'draft': draft_count,
        'archived': archived, 'rejected': rejected, 'flagged': flagged,
        'avg_qa': round(float(avg_qa or 0), 1)
    })

# ===== API: Queue Summary =====
@api.route('/queues/summary', methods=['GET'])
def queue_summary():
    conn = get_db()
    cur = conn.cursor()
    cur.execute("""
        SELECT
            COUNT(*) FILTER (WHERE ("Review_Status" = 'Draft' OR "Review_Status" IS NULL OR "Review_Status" = '')
                             AND ("flagged" IS NOT TRUE)) AS needs_approval,
            COUNT(*) FILTER (WHERE "flagged" = TRUE) AS flagged,
            COUNT(*) FILTER (WHERE "updated_at" >= NOW() - INTERVAL '24 hours') AS recently_updated,
            COUNT(*) FILTER (WHERE ("Exterior_Photo_URL" IS NULL OR "Exterior_Photo_URL" = '' OR "Exterior_Photo_URL" = 'UNAVAILABLE')
                             OR ("Interior_Photo_URL" IS NULL OR "Interior_Photo_URL" = '' OR "Interior_Photo_URL" = 'UNAVAILABLE')) AS needs_media,
            COUNT(*) FILTER (WHERE "Review_Status" = 'Reviewed') AS reviewed,
            COUNT(*) FILTER (WHERE "Review_Status" = 'Rejected') AS rejected,
            COUNT(*) FILTER (WHERE "Review_Status" = 'Archived') AS archived
        FROM final_delivery
    """)
    row = cur.fetchone()
    cur.close()
    conn.close()
    return jsonify({
        'needs_approval': row[0], 'flagged': row[1],
        'recently_updated': row[2], 'needs_media': row[3],
        'reviewed': row[4], 'rejected': row[5], 'archived': row[6]
    })

# ===== API: Safe Auto-Fix =====
@api.route('/pois/<globalid>/apply-safe-fixes', methods=['POST'])
def apply_safe_fixes(globalid):
    ensure_tables()
    conn = get_db()
    cur = conn.cursor(cursor_factory=RealDictCursor)
    cur.execute('SELECT * FROM final_delivery WHERE "GlobalID" = %s', (globalid,))
    row = cur.fetchone()
    if not row:
        cur.close()
        conn.close()
        return api_error('POI not found', 404, code=NOT_FOUND)

    reviewer = (request.json or {}).get('reviewer', 'system')
    fixes = []
    updates = {}

    # 1. Trim whitespace on text fields
    text_fields = ['Name_EN', 'Name_AR', 'Legal_Name', 'Phone_Number', 'Email', 'Website',
                   'Social_Media', 'District_EN', 'District_AR', 'Building_Number']
    for f in text_fields:
        v = row.get(f) or ''
        if isinstance(v, str) and v != v.strip() and v.strip():
            updates[f] = v.strip()
            fixes.append({'field': f, 'old': v, 'new': v.strip(), 'reason': 'trimmed whitespace'})

    # 2. Normalize boolean fields
    bool_fields = ['Menu', 'Drive_Thru', 'Dine_In', 'Only_Delivery', 'Reservation', 'Require_Ticket',
                   'Order_from_Car', 'Pickup_Point', 'WiFi', 'Music', 'Valet_Parking', 'Has_Parking_Lot',
                   'Wheelchair_Accessible', 'Family_Seating', 'Waiting_Area', 'Private_Dining',
                   'Smoking_Area', 'Children_Area', 'Shisha', 'Live_Sports', 'Is_Landmark', 'Is_Trending',
                   'Large_Groups', 'Women_Prayer_Room', 'Iftar_Tent', 'Iftar_Menu', 'Open_Suhoor', 'Free_Entry']
    for f in bool_fields:
        v = str(row.get(f) or '').strip()
        vl = v.lower()
        if vl in ('yes', 'y', 'true', '1') and v != 'Yes':
            updates[f] = 'Yes'
            fixes.append({'field': f, 'old': v, 'new': 'Yes', 'reason': 'normalized to Yes'})
        elif vl in ('no', 'n', 'false', '0') and v != 'No':
            updates[f] = 'No'
            fixes.append({'field': f, 'old': v, 'new': 'No', 'reason': 'normalized to No'})
        elif vl in ('n/a', 'na', 'unavailable', 'none', 'null', '') and v and v != 'UNAVAILABLE':
            updates[f] = 'UNAVAILABLE'
            fixes.append({'field': f, 'old': v, 'new': 'UNAVAILABLE', 'reason': 'normalized to UNAVAILABLE'})
        elif v and vl not in ('yes', 'no', 'unavailable', 'unapplicable', ''):
            updates[f] = 'UNAVAILABLE'
            fixes.append({'field': f, 'old': v, 'new': 'UNAVAILABLE', 'reason': 'invalid value set to UNAVAILABLE'})

    # 3. Move Google Maps URL from Website to Google_Map_URL
    website = str(row.get('Website') or '')
    gmap = str(row.get('Google_Map_URL') or '')
    if website and ('maps.google' in website.lower() or 'maps.app' in website.lower() or 'goo.gl/maps' in website.lower()):
        if not gmap or gmap == 'UNAVAILABLE':
            updates['Google_Map_URL'] = website
            fixes.append({'field': 'Google_Map_URL', 'old': gmap, 'new': website, 'reason': 'moved from Website'})
        updates['Website'] = 'UNAVAILABLE'
        fixes.append({'field': 'Website', 'old': website, 'new': 'UNAVAILABLE', 'reason': 'was Google Maps link'})

    # 4. Fix scientific notation phone
    phone = str(row.get('Phone_Number') or '')
    if phone and ('e+' in phone.lower() or 'E+' in phone):
        updates['Phone_Number'] = 'UNAVAILABLE'
        fixes.append({'field': 'Phone_Number', 'old': phone, 'new': 'UNAVAILABLE', 'reason': 'scientific notation'})

    # 5. Fix invalid email
    email_val = str(row.get('Email') or '')
    if email_val and email_val != 'UNAVAILABLE':
        if not re.match(r'^[^\s@]+@[^\s@]+\.[^\s@]+$', email_val):
            updates['Email'] = 'UNAVAILABLE'
            fixes.append({'field': 'Email', 'old': email_val, 'new': 'UNAVAILABLE', 'reason': 'invalid email format'})

    # 6. Fix invalid floor
    floor = str(row.get('Floor_Number') or '').strip()
    allowed_floors = ['G', 'B1', '1', '2', '3', '4', '5', 'UNAVAILABLE', 'UNAPPLICABLE', '']
    if floor and floor not in allowed_floors:
        updates['Floor_Number'] = 'UNAVAILABLE'
        fixes.append({'field': 'Floor_Number', 'old': floor, 'new': 'UNAVAILABLE', 'reason': 'invalid floor value'})

    # 7. Deduplicate media URLs
    media_fields = ['Exterior_Photo_URL', 'Interior_Photo_URL', 'Menu_Photo_URL', 'Video_URL', 'License_Photo_URL']
    seen_urls = {}
    for f in media_fields:
        v = str(row.get(f) or '')
        if v and v != 'UNAVAILABLE' and v.startswith('http'):
            if v in seen_urls:
                updates[f] = 'UNAVAILABLE'
                fixes.append({'field': f, 'old': v, 'new': 'UNAVAILABLE', 'reason': 'duplicate of ' + seen_urls[v]})
            else:
                seen_urls[v] = f

    if not fixes:
        cur.close()
        conn.close()
        return api_success({'applied': [], 'count': 0}, message='No safe fixes needed')

    # Apply updates
    set_clauses = ['"' + k + '" = %s' for k in updates.keys()]
    set_clauses.append('"review_version" = COALESCE("review_version", 0) + 1')
    set_clauses.append('"updated_at" = NOW()')
    vals = list(updates.values()) + [globalid]
    cur.execute('UPDATE final_delivery SET ' + ', '.join(set_clauses) + ' WHERE "GlobalID" = %s', vals)

    log_audit(conn, globalid, row.get('Name_EN') or row.get('Name_AR') or '',
              reviewer, 'auto_fix', updates, old_data=dict(row))
    conn.commit()
    cur.close()
    conn.close()

    return api_success({'applied': fixes, 'count': len(fixes)},
                       message=str(len(fixes)) + ' safe fixes applied')

# ===== API: Bulk Safe Auto-Fix =====
@api.route('/pois/bulk/apply-safe-fixes', methods=['POST'])
def bulk_apply_safe_fixes():
    data = request.json or {}
    globalids = data.get('globalids', [])
    reviewer = data.get('reviewer', 'system')
    if not globalids:
        return api_error('No globalids provided', 400, code=VALIDATION_ERROR)

    total_fixes = 0
    results = []
    for gid in globalids:
        with app.test_request_context(json={'reviewer': reviewer}):
            resp = apply_safe_fixes(gid)
            if isinstance(resp, tuple):
                resp_data = resp[0].get_json()
            else:
                resp_data = resp.get_json()
            count = resp_data.get('count', 0)
            total_fixes += count
            if count > 0:
                results.append({'globalid': gid, 'count': count})

    return api_success({'total_fixes': total_fixes, 'results': results},
                       message=str(total_fixes) + ' fixes applied across ' + str(len(results)) + ' POIs')

# ===== API: POI Timeline =====
@api.route('/pois/<globalid>/timeline', methods=['GET'])
def poi_timeline(globalid):
    """Return grouped audit entries for a single POI, newest first."""
    conn = get_db()
    cur = conn.cursor(cursor_factory=RealDictCursor)
    cur.execute(
        """SELECT id, action, field_name, old_value, new_value, reviewer,
                  created_at
           FROM poi_audit_log
           WHERE global_id = %s
           ORDER BY created_at DESC, id DESC
           LIMIT 200""",
        (globalid,)
    )
    rows = cur.fetchall()
    cur.close()
    conn.close()

    # Group consecutive rows with same (action, reviewer, timestamp bucket)
    events = []
    for r in rows:
        ts = r['created_at']
        if isinstance(ts, datetime.datetime):
            ts = ts.isoformat()
        entry = {
            'id': r['id'],
            'action': r['action'] or 'edit',
            'field': r['field_name'],
            'old_value': r['old_value'],
            'new_value': r['new_value'],
            'reviewer': r['reviewer'] or '',
            'timestamp': ts
        }
        # Group into same event if same action+reviewer within 2 seconds
        if events and events[-1]['action'] == entry['action'] and events[-1]['reviewer'] == entry['reviewer']:
            last_ts = events[-1]['timestamp']
            try:
                t1 = datetime.datetime.fromisoformat(last_ts.replace('Z', '+00:00')) if isinstance(last_ts, str) else last_ts
                t2 = datetime.datetime.fromisoformat(ts.replace('Z', '+00:00')) if isinstance(ts, str) else ts
                if abs((t1 - t2).total_seconds()) < 2:
                    events[-1]['changes'].append(entry)
                    continue
            except Exception:
                pass
        events.append({
            'action': entry['action'],
            'reviewer': entry['reviewer'],
            'timestamp': ts,
            'changes': [entry]
        })

    return api_success({'events': events, 'total': len(rows)})

# ===== API: Delivery Readiness Stats =====
@api.route('/stats/delivery-readiness', methods=['GET'])
def delivery_readiness():
    """Aggregate delivery-readiness metrics across all POIs."""
    conn = get_db()
    cur = conn.cursor(cursor_factory=RealDictCursor)
    cur.execute("""
        SELECT "Review_Status", "Category", "District_EN", flagged,
               "Name_AR", "Name_EN", "Latitude", "Longitude",
               "Phone_Number", "District_AR",
               "Exterior_Photo_URL", "Interior_Photo_URL"
        FROM final_delivery
    """)
    rows = cur.fetchall()
    cur.close()
    conn.close()

    total = len(rows)
    draft = reviewed = rejected = archived = flagged_cnt = missing_media = 0
    cats = {}
    dists = {}
    for r in rows:
        st = r.get('Review_Status') or 'Draft'
        if st == 'Draft':
            draft += 1
        elif st == 'Reviewed':
            reviewed += 1
        elif st == 'Rejected':
            rejected += 1
        elif st == 'Archived':
            archived += 1
        if r.get('flagged'):
            flagged_cnt += 1
        ext = r.get('Exterior_Photo_URL') or ''
        intr = r.get('Interior_Photo_URL') or ''
        if (not ext or ext == 'UNAVAILABLE') and (not intr or intr == 'UNAVAILABLE'):
            missing_media += 1
        cat = r.get('Category') or 'Uncategorized'
        if cat not in cats:
            cats[cat] = {'total': 0, 'reviewed': 0, 'draft': 0}
        cats[cat]['total'] += 1
        if st == 'Reviewed':
            cats[cat]['reviewed'] += 1
        if st == 'Draft':
            cats[cat]['draft'] += 1
        dist = r.get('District_EN') or 'Unknown'
        if dist not in dists:
            dists[dist] = {'total': 0, 'reviewed': 0, 'draft': 0}
        dists[dist]['total'] += 1
        if st == 'Reviewed':
            dists[dist]['reviewed'] += 1
        if st == 'Draft':
            dists[dist]['draft'] += 1

    cat_list = [{'name': k, **v} for k, v in sorted(cats.items(), key=lambda x: -x[1]['total'])]
    dist_list = [{'name': k, **v} for k, v in sorted(dists.items(), key=lambda x: -x[1]['total'])]

    return api_success({
        'total': total,
        'draft': draft,
        'reviewed': reviewed,
        'rejected': rejected,
        'archived': archived,
        'flagged': flagged_cnt,
        'missing_media': missing_media,
        'categories': cat_list,
        'districts': dist_list
    })


@api.route('/stats/reviewer-productivity', methods=['GET'])
def reviewer_productivity():
    """Per-reviewer productivity stats from audit log."""
    conn = get_db()
    cur = conn.cursor(cursor_factory=RealDictCursor)
    cur.execute("""
        SELECT reviewer,
               COUNT(*) as total_actions,
               COUNT(*) FILTER (WHERE action = 'approve' OR (action = 'status_change' AND new_value = 'Reviewed')) as approvals,
               COUNT(*) FILTER (WHERE action = 'reject' OR (action = 'status_change' AND new_value = 'Rejected')) as rejections,
               COUNT(*) FILTER (WHERE action = 'edit') as edits,
               COUNT(DISTINCT global_id) as pois_touched,
               MIN(created_at)::text as first_activity,
               MAX(created_at)::text as last_activity,
               COUNT(DISTINCT created_at::date) as active_days
        FROM poi_audit_log
        WHERE reviewer IS NOT NULL AND reviewer != ''
        GROUP BY reviewer
        ORDER BY total_actions DESC
    """)
    reviewers = cur.fetchall()
    cur.execute("""
        SELECT created_at::date as day, reviewer, COUNT(*) as actions
        FROM poi_audit_log
        WHERE created_at >= NOW() - INTERVAL '14 days'
          AND reviewer IS NOT NULL AND reviewer != ''
        GROUP BY day, reviewer
        ORDER BY day
    """)
    daily = cur.fetchall()
    cur.close()
    conn.close()
    return api_success({'reviewers': reviewers, 'daily': daily})


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
        return api_error('Not found', 404, code=NOT_FOUND)
    sync_to_arcgis('delete', globalid)
    return api_success({'deleted': deleted})

# ===== API: Archive POI =====
@api.route('/pois/<globalid>/archive', methods=['POST'])
def archive_poi(globalid):
    """Archive a POI with reason."""
    conn = get_db()
    cur = conn.cursor(cursor_factory=RealDictCursor)
    cur.execute('SELECT "Review_Status", "Name_EN", "Name_AR" FROM final_delivery WHERE "GlobalID" = %s', (globalid,))
    row = cur.fetchone()
    if not row:
        cur.close(); conn.close()
        return api_error('Not found', 404, code=NOT_FOUND)

    body = request.get_json(silent=True) or {}
    reviewer = body.get('reviewer', 'unknown')
    reason = body.get('reason', '')

    cur2 = conn.cursor()
    cur2.execute(
        '''UPDATE final_delivery SET "Review_Status" = 'Archived', "archived_reason" = %s, "updated_at" = NOW()
           WHERE "GlobalID" = %s''',
        (reason, globalid)
    )
    poi_name = row.get('Name_EN') or row.get('Name_AR') or ''
    log_audit(conn, globalid, poi_name, reviewer, 'archive',
              {'Review_Status': 'Archived', 'archived_reason': reason},
              old_data={'Review_Status': row.get('Review_Status', '')},
              action_reason=reason)
    conn.commit()
    cur.close(); cur2.close(); conn.close()
    return api_success({'status': 'Archived', 'reason': reason})

# ===== API: Reject POI (terminal state) =====
@api.route('/pois/<globalid>/reject', methods=['POST'])
def reject_poi(globalid):
    """Reject a POI — terminal state for bad/invalid records."""
    conn = get_db()
    cur = conn.cursor(cursor_factory=RealDictCursor)
    cur.execute('SELECT "Review_Status", "Name_EN", "Name_AR" FROM final_delivery WHERE "GlobalID" = %s', (globalid,))
    row = cur.fetchone()
    if not row:
        cur.close(); conn.close()
        return api_error('Not found', 404, code=NOT_FOUND)

    if (row.get('Review_Status') or '') == 'Rejected':
        cur.close(); conn.close()
        return api_error('Already rejected', 400, code=VALIDATION_ERROR)

    body = request.get_json(silent=True) or {}
    reviewer = body.get('reviewer', 'unknown')
    reason = body.get('reason', '')
    if not reason:
        cur.close(); conn.close()
        return api_error('Rejection reason is required', 400, code=VALIDATION_ERROR)

    cur2 = conn.cursor()
    cur2.execute(
        '''UPDATE final_delivery SET "Review_Status" = 'Rejected', "rejected_reason" = %s, "updated_at" = NOW()
           WHERE "GlobalID" = %s''',
        (reason, globalid)
    )
    poi_name = row.get('Name_EN') or row.get('Name_AR') or ''
    log_audit(conn, globalid, poi_name, reviewer, 'reject',
              {'Review_Status': 'Rejected', 'rejected_reason': reason},
              old_data={'Review_Status': row.get('Review_Status', '')},
              action_reason=reason)
    conn.commit()
    cur.close(); cur2.close(); conn.close()
    return api_success({'status': 'Rejected', 'reason': reason})

# ===== API: Flag/Unflag POI (overlay, not status change) =====
@api.route('/pois/<globalid>/flag', methods=['PATCH'])
def flag_poi_endpoint(globalid):
    """Set or clear the flagged overlay without changing Review_Status."""
    conn = get_db()
    cur = conn.cursor(cursor_factory=RealDictCursor)
    cur.execute('SELECT * FROM final_delivery WHERE "GlobalID" = %s', (globalid,))
    row = cur.fetchone()
    if not row:
        cur.close(); conn.close()
        return api_error('Not found', 404, code=NOT_FOUND)

    body = request.get_json(silent=True) or {}
    reviewer = body.get('reviewer', 'unknown')
    flagged = body.get('flagged', True)
    flag_reason = body.get('flag_reason', '')

    cur2 = conn.cursor()
    cur2.execute(
        '''UPDATE final_delivery
           SET "flagged" = %s, "flag_reason" = %s, "Review_Flag" = %s, "updated_at" = NOW()
           WHERE "GlobalID" = %s''',
        (flagged, flag_reason if flagged else '', flag_reason if flagged else '', globalid)
    )
    poi_name = row.get('Name_EN') or row.get('Name_AR') or ''
    action = 'flag' if flagged else 'unflag'
    log_audit(conn, globalid, poi_name, reviewer, action,
              {'flagged': str(flagged), 'flag_reason': flag_reason},
              old_data={'flagged': str(row.get('flagged', False)), 'flag_reason': row.get('flag_reason', '')})
    conn.commit()
    cur.close(); cur2.close(); conn.close()
    return api_success({'flagged': flagged, 'flag_reason': flag_reason})

# ===== API: Approval Check =====
@api.route('/pois/<globalid>/approval-check', methods=['GET'])
def approval_check(globalid):
    """Check if a POI can be approved. Returns blockers list."""
    conn = get_db()
    cur = conn.cursor(cursor_factory=RealDictCursor)
    cur.execute('SELECT * FROM final_delivery WHERE "GlobalID" = %s', (globalid,))
    row = cur.fetchone()
    cur.close()
    conn.close()
    if not row:
        return api_error('Not found', 404, code=NOT_FOUND)
    blockers = get_approval_blockers(dict(row))
    return jsonify({
        'can_approve': len(blockers) == 0,
        'blockers': blockers,
        'current_status': (row.get('Review_Status') or 'Draft').strip()
    })

# ===== API: ArcGIS Token Proxy =====
@api.route('/arcgis-token', methods=['GET'])
def arcgis_token():
    username = os.environ.get('ARCGIS_USERNAME', 'nagadco0000')
    password = os.environ.get('ARCGIS_PASSWORD', 'Nagad$1390')
    referer = os.environ.get('ARCGIS_REFERER', 'https://media-review-app.vercel.app')
    try:
        r = req_lib.post('https://www.arcgis.com/sharing/rest/generateToken', data={
            'username': username, 'password': password,
            'client': 'referer', 'referer': referer,
            'expiration': 120, 'f': 'json'
        }, timeout=30)
        d = r.json()
        if 'token' in d:
            return jsonify({'token': d['token']})
        return api_error(d.get('error', {}).get('message', 'Unknown error'), 401)
    except Exception as e:
        return api_error(str(e), 500, code=INTERNAL_ERROR)

# ===== API: ArcGIS Image Proxy (HEIC → JPEG conversion) =====
_agol_token_cache = {'token': None, 'expires': 0}

def _get_agol_token():
    now = time.time() * 1000
    if _agol_token_cache['token'] and _agol_token_cache['expires'] > now + 60000:
        return _agol_token_cache['token']
    username = os.environ.get('ARCGIS_USERNAME', 'nagadco0000')
    password = os.environ.get('ARCGIS_PASSWORD', 'Nagad$1390')
    referer = os.environ.get('ARCGIS_REFERER', 'https://media-review-app.vercel.app')
    r = req_lib.post('https://www.arcgis.com/sharing/rest/generateToken', data={
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
    url = request.args.get('url', '')
    if not url or 'arcgis.com' not in url:
        return 'Bad URL', 400

    token = _get_agol_token()
    if not token:
        return 'Token failed', 500

    try:
        r = req_lib.get(url, params={'token': token}, timeout=30, stream=True)
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
    q = request.args.get('q', '').strip()
    if not q or len(q) < 2:
        return api_error('Query too short (min 2 chars)', 400, code=VALIDATION_ERROR)

    token = _get_agol_token()
    if not token:
        return api_error('Token failed', 500, code=INTERNAL_ERROR)

    base = 'https://services5.arcgis.com/pYlVm2T6SvR7ytZv/arcgis/rest/services/survey123_1ed04c063d54418b893c165594e88840_results/FeatureServer/0'

    where_clause = f"poi_name_en LIKE '%{q}%' OR poi_name_ar LIKE '%{q}%' OR place_name LIKE '%{q}%'"
    try:
        r = req_lib.get(f'{base}/query', params={
            'where': where_clause,
            'outFields': 'objectid,globalid,poi_name_en,poi_name_ar,place_name',
            'resultRecordCount': 50,
            'f': 'json',
            'token': token
        }, timeout=30)
        data = r.json()
        features = data.get('features', [])
    except Exception as e:
        return api_error(f'Query failed: {e}', 500, code=INTERNAL_ERROR)

    if not features:
        return jsonify({'results': []})

    # Get attachments for matching features
    oids = [f['attributes']['objectid'] for f in features if f['attributes'].get('objectid')]
    att_map = {}
    for i in range(0, len(oids), 50):
        batch = oids[i:i+50]
        try:
            ar = req_lib.get(f'{base}/queryAttachments', params={
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

# ===== API: Fetch Survey123 feature and create POI =====
@api.route('/survey123-to-poi/<objectid>', methods=['POST'])
def survey123_to_poi(objectid):
    """Fetch a Survey123 feature by objectid and create a new POI in the DB."""
    token = _get_agol_token()
    if not token:
        return api_error('ArcGIS token failed', 500, code=INTERNAL_ERROR)

    base = 'https://services5.arcgis.com/pYlVm2T6SvR7ytZv/arcgis/rest/services/survey123_1ed04c063d54418b893c165594e88840_results/FeatureServer/0'

    # Query feature by objectid
    try:
        r = req_lib.get(f'{base}/query', params={
            'where': f'objectid={int(objectid)}',
            'outFields': '*',
            'returnGeometry': 'true',
            'f': 'json',
            'token': token
        }, timeout=30)
        data = r.json()
        features = data.get('features', [])
    except Exception as e:
        return api_error(f'Query failed: {e}', 500, code=INTERNAL_ERROR)

    if not features:
        return api_error('Feature not found in Survey123', 404, code=NOT_FOUND)

    feat = features[0]
    attrs = feat.get('attributes', {})
    geom = feat.get('geometry', {})

    # Map Survey123 fields to DB schema
    poi_data = {}
    for s123_field, db_field in SURVEY123_FIELD_MAP.items():
        val = attrs.get(s123_field)
        if val and str(val).strip():
            poi_data[db_field] = str(val).strip()

    # Extract geometry
    if geom:
        if geom.get('x') and not poi_data.get('Longitude'):
            poi_data['Longitude'] = str(geom['x'])
        if geom.get('y') and not poi_data.get('Latitude'):
            poi_data['Latitude'] = str(geom['y'])

    if not poi_data.get('Name_EN') and not poi_data.get('Name_AR'):
        poi_data['Name_EN'] = f'Survey123 Import #{objectid}'

    poi_data['Source'] = 'survey123_import'

    # Check if POI already exists by name match
    conn = get_db()
    cur = conn.cursor(cursor_factory=RealDictCursor)
    name_en = poi_data.get('Name_EN', '')
    name_ar = poi_data.get('Name_AR', '')
    if name_en:
        cur.execute('SELECT "GlobalID" FROM final_delivery WHERE "Name_EN" = %s LIMIT 1', (name_en,))
        existing = cur.fetchone()
        if existing:
            cur.close(); conn.close()
            return api_error('POI already exists', 409, code=CONFLICT,
                           details={'GlobalID': existing['GlobalID'], 'name': name_en})

    # Generate new GlobalID and insert
    gid = '{' + str(uuid.uuid4()).upper() + '}'
    poi_data['GlobalID'] = gid

    cur.execute("SELECT column_name FROM information_schema.columns WHERE table_name = 'final_delivery' ORDER BY ordinal_position;")
    all_cols = [r['column_name'] for r in cur.fetchall()]
    skip = {'created_at', 'updated_at', 'delivery_date'}

    cols = ['"GlobalID"']
    vals = [gid]
    placeholders = ['%s']

    for col in all_cols:
        if col in skip or col == 'GlobalID':
            continue
        if col in poi_data:
            cols.append(f'"{col}"')
            vals.append(poi_data[col])
            placeholders.append('%s')

    cols.append('"created_at"'); placeholders.append('NOW()')
    cols.append('"updated_at"'); placeholders.append('NOW()')

    sql = f'INSERT INTO final_delivery ({", ".join(cols)}) VALUES ({", ".join(placeholders)})'
    try:
        cur.execute(sql, vals)
        conn.commit()
    except Exception as e:
        conn.rollback(); cur.close(); conn.close()
        return api_error(str(e), 500, code=INTERNAL_ERROR)

    cur.close(); conn.close()
    sync_to_arcgis('create', gid, poi_data)
    return api_success({'GlobalID': gid, 'data': poi_data}, status=201)

# ===== API: Create new POI =====
@api.route('/pois', methods=['POST'])
def create_poi():
    data = request.get_json()
    if not data:
        return api_error('No data', 400, code=VALIDATION_ERROR)

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

    # New POIs start as Draft unless explicitly set
    if 'Review_Status' not in data:
        cols.append('"Review_Status"')
        vals.append('Draft')
        placeholders.append('%s')
        cols.append('"draft_reason"')
        vals.append('new')
        placeholders.append('%s')
        cols.append('"review_version"')
        vals.append(0)
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
        return api_error(str(e), 500, code=INTERNAL_ERROR)

    cur.close()
    conn.close()
    data['GlobalID'] = gid
    sync_to_arcgis('create', gid, data)
    return api_success({'GlobalID': gid}, status=201)

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
        return api_error('No data', 400, code=VALIDATION_ERROR)

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
        return api_error('No mappable fields', 400, code=VALIDATION_ERROR)

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
        return api_success({'action': 'updated', 'GlobalID': gid, 'fields': len(changed)})
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
            return api_error(str(e), 500, code=INTERNAL_ERROR)

        cur.close()
        conn.close()
        sync_to_arcgis('create', gid, mapped)
        return api_success({'action': 'created', 'GlobalID': gid}, status=201)

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
    return api_success({'acknowledged': count})

# ===== API: Category Migration =====
_CAT_MAP = {
    'Services & Industry': 'Corporate',
    'Shopping & Distribution': 'Shopping',
    'Real Estate': 'Corporate',
    'Life & Convenience': 'Corporate',
    'Health & Medical': 'Hospitals',
}
_SUB_OVERRIDE = {
    ('Services & Industry', 'Laundry'): ('Corporate', 'Laundries and Dry-Cleaning'),
    ('Services & Industry', 'Attorney'): ('Corporate', 'Attorney'),
    ('Services & Industry', 'Building Contractor'): ('Corporate', 'Building Contractor'),
    ('Services & Industry', 'Insurance'): ('Corporate', 'Insurance'),
    ('Services & Industry', 'Equipment Rental'): ('Corporate', 'Equipment Rental'),
    ('Services & Industry', 'Real Estate'): ('Corporate', 'Real Estate Company'),
    ('Services & Industry', 'Government Services'): ('Government Services', 'Government Office'),
    ('Services & Industry', 'Park'): ('Public Parks', 'Park'),
    ('Services & Industry', 'Mending'): ('Corporate', 'Machine repair service'),
    ('Services & Industry', 'mending'): ('Corporate', 'Machine repair service'),
    ('Services & Industry', 'Retail'): ('Shopping', 'General store'),
    ('Services & Industry', 'Support & Outsourcing Services'): ('Corporate', 'Business Services Office'),
    ('Shopping & Distribution', 'Retail'): ('Shopping', 'General store'),
    ('Shopping & Distribution', 'Automotive & Car Accessories'): ('Automotive Services', 'Car Accessories'),
    ('Shopping & Distribution', 'Fashion'): ('Shopping', 'Fashion accessories store'),
    ('Shopping & Distribution', 'Wholesale & Retail'): ('Shopping', 'Wholesaler'),
    ('Real Estate', 'Real Estate Company'): ('Corporate', 'Real Estate Company'),
    ('Real Estate', 'Projects & Developments'): ('Corporate', 'Projects & Developments'),
    ('Life & Convenience', 'Cleaning Service'): ('Corporate', 'Cleaning Service'),
    ('Life & Convenience', 'Retail'): ('Shopping', 'General store'),
    ('Life & Convenience', 'Car Wash'): ('Automotive Services', 'Car Wash Services'),
    ('Life & Convenience', 'Mending'): ('Corporate', 'Machine repair service'),
    ('Life & Convenience', 'Repair Services'): ('Corporate', 'Machine repair service'),
    ('Life & Convenience', 'Life & Convenience'): ('Corporate', 'General Contractor'),
    ('Health & Medical', 'Hospitals & Clinics'): ('Hospitals', 'Clinic'),
    ('Health & Medical', 'Support & Outsourcing Services'): ('Hospitals', 'Clinic'),
    ('Shopping', 'Shopping'): ('Shopping', 'General store'),
    ('Restaurants', 'Restaurants'): ('Restaurants', 'International Restaurant'),
    ('Beauty and Spa', 'Beauty and Spa'): ('Beauty and Spa', 'Beauty Salon'),
    ('Coffee Shops', 'Coffee Shops'): ('Coffee Shops', 'Specialty Coffee'),
    ('Corporate', 'Corporate'): ('Corporate', 'Business Services Office'),
    ('Automotive Services', 'Automotive Services'): ('Automotive Services', 'Car Repair Workshop'),
    ('Home Goods', 'Home Goods'): ('Home Goods', 'Appliance Store'),
    ('Food and Beverages', 'Food and Beverages'): ('Food and Beverages', 'Food Court'),
    ('Grocery', 'Grocery'): ('Grocery', 'Grocery Store'),
    ('Banks', 'Banks'): ('Banks', 'Islamic Bank'),
    ('Sports', 'Sports'): ('Sports', 'Sport Club'),
    ('Hospitals', 'Hospitals'): ('Hospitals', 'Hospital'),
    ('Hotels and Accommodations', 'Hotels and Accommodations'): ('Hotels and Accommodations', 'Hotel'),
    ('Pharmacies', 'Pharmacies'): ('Pharmacies', 'Pharmacy'),
    ('Cultural Sites', 'Cultural Sites'): ('Cultural Sites', 'Cultural Centers'),
    ('Fuel Stations', 'Fuel Stations'): ('Fuel Stations', 'Gas Station'),
    ('Transportation', 'Transportation'): ('Transportation', 'Taxi Service'),
    ('Entertainment', 'Entertainment'): ('Entertainment', 'Family Entertainment Centers'),
    ('Education', 'Education'): ('Education', 'School'),
    ('Government Services', 'Government Services'): ('Government Services', 'Government Office'),
    ('Nature', 'Nature'): ('Nature', 'Nature Reserves'),
    ('Public Parks', 'Public Parks'): ('Public Parks', 'Park'),
    ('Public Services', 'Public Services'): ('Public Services', 'Charity'),
    ('Restaurants', 'Arab Cuisine'): ('Restaurants', 'Traditional Saudi'),
    ('Restaurants', 'Cafes & Desserts'): ('Coffee Shops', 'Brunch Cafes'),
    ('Shopping', 'General Wholesale & Retail'): ('Shopping', 'Wholesaler'),
    ('Home Goods', 'Household Goods'): ('Home Goods', 'Appliance Store'),
    ('Home Goods', 'Furniture & Interior'): ('Home Goods', 'Furniture Stores'),
    ('Sports', "Men's Gym"): ('Sports', 'Gym'),
    ('Beauty and Spa', "Men's Barber"): ('Beauty and Spa', 'Barbershops'),
    ('Shopping', 'Optical'): ('Shopping', 'Glasses Store'),
    ('Grocery', 'Convenience Store'): ('Grocery', 'Grocery Store'),
    ('Hotels and Accommodations', 'Support & Outsourcing Services'): ('Hotels and Accommodations', 'Hotel'),
    ('Transportation', 'Parking'): ('Transportation', 'Parking Facilities'),
    ('Transportation', 'Retail'): ('Transportation', 'Taxi Service'),
    ('Shopping', 'Fashion'): ('Shopping', 'Fashion accessories store'),
}

def _migrate_cat(cat, sub):
    key = (cat, sub)
    if key in _SUB_OVERRIDE:
        return _SUB_OVERRIDE[key]
    if cat in _CAT_MAP:
        return (_CAT_MAP[cat], sub)
    return (cat, sub)

@api.route('/migrate-categories', methods=['POST'])
def migrate_categories():
    """Migrate old categories/subcategories to new taxonomy. POST with ?apply=true to execute."""
    try:
        do_apply = request.args.get('apply', '').lower() == 'true'
        conn = psycopg2.connect(DATABASE_URL)
        cur = conn.cursor(cursor_factory=RealDictCursor)
        cur.execute('SELECT "GlobalID", "Name_EN", "Category", "Subcategory" FROM final_delivery')
        pois = cur.fetchall()

        changes = []
        for p in pois:
            old_cat = (p['Category'] or '').strip()
            old_sub = (p['Subcategory'] or '').strip()
            if not old_cat:
                continue
            new_cat, new_sub = _migrate_cat(old_cat, old_sub)
            if new_cat != old_cat or new_sub != old_sub:
                changes.append({
                    'gid': p['GlobalID'],
                    'name': p['Name_EN'] or '',
                    'old_cat': old_cat, 'old_sub': old_sub,
                    'new_cat': new_cat, 'new_sub': new_sub,
                })

        if do_apply and changes:
            for c in changes:
                cur.execute('UPDATE final_delivery SET "Category" = %s, "Subcategory" = %s WHERE "GlobalID" = %s',
                            (c['new_cat'], c['new_sub'], c['gid']))
            conn.commit()

        cur.close()
        conn.close()

        # Summarize by mapping type
        from collections import Counter
        summary = Counter()
        for c in changes:
            key = f"{c['old_cat']}>{c['old_sub']} -> {c['new_cat']}>{c['new_sub']}"
            summary[key] += 1

        return jsonify({
            'mode': 'applied' if do_apply else 'dry_run',
            'total_pois': len(pois),
            'changes_count': len(changes),
            'summary': [{'mapping': k, 'count': v} for k, v in summary.most_common()],
        })
    except Exception as e:
        return api_error(str(e), 500, code=INTERNAL_ERROR)


# ===== API: POI Validation (21-Error QA Pipeline) =====
import re as _re

_FNB_CATS = {'Restaurants','Coffee Shops','Food and Beverages','Hospitality','Bakery','Fast Food',
             'Cafe','Cafes','Restaurant','Coffee Shop','Food & Beverage','Fine Dining','Buffet',
             'Food Truck','Juice Bar','Ice Cream','Dessert','Catering'}
_MOSQUE_CATS = {'Mosques','Mosque'}
_ATTRACTION_CATS = {'Entertainment','Sports','Cultural Sites','Nature','Public Parks',
                     'Entertainment and Recreation','Amusement Park','Cinema','Stadium','Park'}

_FNB_ONLY_BOOLS = {'Menu','Drive_Thru','Dine_In','Only_Delivery','Shisha','Order_from_Car',
                    'Live_Sports','Family_Seating','Large_Groups','Waiting_Area','Private_Dining',
                    'Smoking_Area','Iftar_Menu','Open_Suhoor','Cuisine','Menu_Barcode_URL','Menu_Photo_URL'}
_MOSQUE_ONLY_BOOLS = {'Women_Prayer_Room','Iftar_Tent'}
_ATTRACTION_ONLY_BOOLS = {'Require_Ticket','Is_Landmark','Free_Entry'}
_ALL_BOOLS = {'Menu','Drive_Thru','Dine_In','Only_Delivery','Reservation','Require_Ticket',
              'Order_from_Car','Pickup_Point','WiFi','Music','Valet_Parking','Has_Parking_Lot',
              'Wheelchair_Accessible','Family_Seating','Waiting_Area','Private_Dining',
              'Smoking_Area','Children_Area','Shisha','Live_Sports','Is_Landmark','Is_Trending',
              'Large_Groups','Women_Prayer_Room','Iftar_Tent','Iftar_Menu','Open_Suhoor','Free_Entry'}

_AR_CATEGORY_WORDS = {'مطعم','صيدلية','مقهى','مغسلة','بقالة','مسجد','مدرسة','مستشفى','فندق','مقاولات','محل'}
_EN_CATEGORY_WORDS = {'restaurant','pharmacy','cafe','laundry','grocery','mosque','school','hospital','hotel','shop','store'}

_SAUDI_PHONE = _re.compile(r'^(\+9665\d{8}|05\d{8}|\+9661[1-9]\d{6,7}|01[1-9]\d{6,7}|800\d{7}|900\d{7}|920\d{6}|911)$')
_EMAIL_RE = _re.compile(r'^[^@]+@[^@]+\.[^@]+$')

_BAD_SENTINELS = {'n/a', 'na', 'none', 'null', '-', '--', '---', 'unknown', 'tbd',
                  'not available', 'not applicable', 'nil', '.', '..', 'empty', 'no data'}
_SENTINEL_TEXT_FIELDS = ['Name_EN', 'Name_AR', 'Legal_Name', 'Phone_Number', 'Email',
                         'Website', 'Social_Media', 'District_EN', 'District_AR',
                         'Working_Hours', 'Working_Days', 'Building_Number']

_WEBSITE_SOCIAL_BLOCKLIST = ['facebook.com', 'instagram.com', 'twitter.com', 'x.com',
                              'tiktok.com', 'snapchat.com', 'wa.me', 't.me', 'linkedin.com']

# Phonetic transliteration: English -> approximate Arabic
_EN_TO_AR_MAP = [
    ('sh', '\u0634'), ('ch', '\u062a\u0634'), ('th', '\u062b'), ('kh', '\u062e'), ('ph', '\u0641'),
    ('tion', '\u0634\u0646'), ('oo', '\u0648'), ('ee', '\u064a'), ('ou', '\u0648'), ('ai', '\u064a'),
    ('a', '\u0627'), ('b', '\u0628'), ('c', '\u0643'), ('d', '\u062f'), ('e', '\u064a'), ('f', '\u0641'),
    ('g', '\u062c'), ('h', '\u0647'), ('i', '\u064a'), ('j', '\u062c'), ('k', '\u0643'), ('l', '\u0644'),
    ('m', '\u0645'), ('n', '\u0646'), ('o', '\u0648'), ('p', '\u0628'), ('q', '\u0643'), ('r', '\u0631'),
    ('s', '\u0633'), ('t', '\u062a'), ('u', '\u0648'), ('v', '\u0641'), ('w', '\u0648'), ('x', '\u0643\u0633'),
    ('y', '\u064a'), ('z', '\u0632'),
]

def _transliterate_en_to_ar(en_text):
    result = ''
    en_lower = en_text.lower()
    i = 0
    while i < len(en_lower):
        matched = False
        for length in (4, 3, 2, 1):
            chunk = en_lower[i:i+length]
            for en, ar in _EN_TO_AR_MAP:
                if len(en) == length and chunk == en:
                    result += ar
                    i += length
                    matched = True
                    break
            if matched:
                break
        if not matched:
            ch = en_lower[i]
            if ch == ' ':
                result += ' '
            i += 1
    return result

def _ar_bigram_similarity(a, b):
    a = a.replace(' ', ''); b = b.replace(' ', '')
    if not a or not b:
        return 0
    bg = lambda s: {s[i:i+2] for i in range(len(s)-1)} if len(s) >= 2 else {s}
    bg1, bg2 = bg(a), bg(b)
    if not bg1 or not bg2:
        return 0
    inter = len(bg1 & bg2)
    return (2 * inter / (len(bg1) + len(bg2))) * 100

# Load taxonomy for category hierarchy validation
import json as _json
_TAXONOMY_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'scripts', 'taxonomy.json')
try:
    with open(_TAXONOMY_PATH, 'r', encoding='utf-8') as _f:
        _TAXONOMY = _json.load(_f)
except Exception:
    _TAXONOMY = {}
_VALID_CATEGORIES = set(_TAXONOMY.keys())

def _validate_poi_core(poi):
    """Core validation logic. Returns (corrected, blockers, warnings, changes)."""
    corrected = dict(poi)
    blockers = []
    warnings = []
    changes = []

    cat = (poi.get('Category') or '').strip()
    is_fnb = cat in _FNB_CATS or any(w in cat.lower() for w in ['food','restaurant','cafe','coffee'])
    is_mosque = cat in _MOSQUE_CATS
    is_attraction = cat in _ATTRACTION_CATS

    def flag_b(rule, field, issue, fix=''):
        blockers.append({'rule_id': rule, 'field': field, 'issue': issue, 'suggested_fix': fix})
    def flag_w(rule, field, issue, fix=''):
        warnings.append({'rule_id': rule, 'field': field, 'issue': issue, 'suggested_fix': fix})
    def change(field, old, new, reason):
        corrected[field] = new
        changes.append({'field': field, 'from': old, 'to': new, 'reason': reason})

    # A) Name_AR
    name_ar = (poi.get('Name_AR') or '').strip()
    if not name_ar or len(name_ar) < 2:
        flag_b('GATE-A1', 'Name_AR', 'Missing or too short', 'Provide Arabic name (2+ chars)')
    elif _re.search(r'[A-Za-z]', name_ar):
        flag_w('GATE-A2', 'Name_AR', 'Contains English characters', 'Remove English from Arabic name')
    elif name_ar in _AR_CATEGORY_WORDS:
        flag_b('GATE-A3', 'Name_AR', 'Name is just a category word', 'Provide specific business name')

    # B) Name_EN
    name_en = (poi.get('Name_EN') or '').strip()
    if not name_en or len(name_en) < 2:
        flag_b('GATE-B1', 'Name_EN', 'Missing or too short', 'Provide English name (2+ chars)')
    elif _re.search(r'[\u0600-\u06FF]', name_en):
        flag_w('GATE-B2', 'Name_EN', 'Contains Arabic characters', 'Remove Arabic from English name')
    elif name_en.lower() in _EN_CATEGORY_WORDS:
        flag_b('GATE-B3', 'Name_EN', 'Name is just a category word', 'Provide specific business name')

    # B4/B5) ALL CAPS / all lowercase detection
    if name_en and len(name_en) >= 2:
        alpha_chars = [c for c in name_en if c.isalpha()]
        if len(alpha_chars) >= 4 and all(c.isupper() for c in alpha_chars):
            flag_w('GATE-B4', 'Name_EN', 'Name is ALL CAPS', 'Use Title Case')
            change('Name_EN', name_en, name_en.title(), 'Converted ALL CAPS to Title Case')
        elif len(alpha_chars) >= 4 and all(c.islower() for c in alpha_chars):
            flag_w('GATE-B5', 'Name_EN', 'Name is all lowercase', 'Use Title Case')
            change('Name_EN', name_en, name_en.title(), 'Converted lowercase to Title Case')

    # A4) Phonetic transliteration detection
    if name_ar and name_en and len(name_ar) >= 3 and len(name_en) >= 3:
        ar_chars = sum(1 for c in name_ar if '\u0600' <= c <= '\u06FF')
        if ar_chars >= len(name_ar.replace(' ', '')) * 0.7:
            transliterated = _transliterate_en_to_ar(name_en)
            sim = _ar_bigram_similarity(name_ar, transliterated)
            if sim > 70:
                flag_w('GATE-A4', 'Name_AR',
                       f'Arabic name appears to be phonetic transliteration of English (similarity: {sim:.0f}%)',
                       'Provide proper Arabic name, not transliteration')

    # A5) Arabic-English brand correspondence
    if name_ar and name_en and len(name_en) >= 4:
        en_words = name_en.split()
        brand_words = [w for w in en_words if len(w) >= 3 and w[0].isupper()
                       and w.lower() not in _EN_CATEGORY_WORDS]
        if brand_words:
            brand = brand_words[0]
            transliterated_brand = _transliterate_en_to_ar(brand)
            if (transliterated_brand not in name_ar and
                brand.lower() not in name_ar.lower() and
                _ar_bigram_similarity(name_ar, transliterated_brand) < 30):
                flag_w('GATE-A5', 'Name_AR',
                       f'Brand "{brand}" from English name not found in Arabic name',
                       f'Arabic name should include brand: {transliterated_brand} or {brand}')

    # A6) Arabic and English must describe same business type
    _AR_DESC_MAP = {
        '\u0635\u064a\u062f\u0644\u064a\u0629': _re.compile(r'pharmacy|pharma', _re.I),        # صيدلية
        '\u0645\u063a\u0633\u0644\u0629': _re.compile(r'laundry|dry.?clean', _re.I),            # مغسلة
        '\u0645\u0637\u0639\u0645': _re.compile(r'restaurant', _re.I),                          # مطعم
        '\u0645\u0642\u0647\u0649': _re.compile(r'cafe|coffee', _re.I),                         # مقهى
        '\u0645\u0633\u062a\u0634\u0641\u0649': _re.compile(r'hospital', _re.I),                # مستشفى
        '\u0641\u0646\u062f\u0642': _re.compile(r'hotel', _re.I),                               # فندق
        '\u0645\u062f\u0631\u0633\u0629': _re.compile(r'school|academy', _re.I),                # مدرسة
    }
    _EN_DESCRIPTORS = _re.compile(r'pharmacy|laundry|restaurant|cafe|coffee|hospital|hotel|school|academy', _re.I)
    if name_ar and name_en:
        for ar_word, en_pattern in _AR_DESC_MAP.items():
            if ar_word in name_ar and not en_pattern.search(name_en):
                if _EN_DESCRIPTORS.search(name_en):
                    flag_b('GATE-A6', 'Name_AR',
                           f'Arabic has "{ar_word}" but English name describes a different business type',
                           'Arabic and English names must refer to the same business')
                    break

    # C) Legal Name
    legal = (poi.get('Legal_Name') or '').strip()
    if not legal or len(legal) < 3:
        change('Legal_Name', legal, 'UNAVAILABLE', 'Legal name missing/too short')
        flag_w('GATE-C1', 'Legal_Name', 'Missing or too short', 'Set UNAVAILABLE')

    # D) Media URLs
    ext_url = (poi.get('Exterior_Photo_URL') or '').strip()
    int_url = (poi.get('Interior_Photo_URL') or '').strip()
    menu_url = (poi.get('Menu_Photo_URL') or '').strip()
    video_url = (poi.get('Video_URL') or '').strip()

    if not ext_url or ext_url == 'UNAVAILABLE':
        flag_b('GATE-D1', 'Exterior_Photo_URL', 'Missing exterior photo', 'Add valid exterior photo URL')
    if not int_url or int_url == 'UNAVAILABLE':
        flag_b('GATE-D2', 'Interior_Photo_URL', 'Missing interior photo', 'Add valid interior photo URL')
    if ext_url and int_url and ext_url == int_url:
        flag_b('GATE-D3', 'Interior_Photo_URL', 'Exterior and interior photos are identical', 'Use different photos')
        change('Interior_Photo_URL', int_url, 'UNAVAILABLE', 'Duplicate of exterior photo')

    if not is_fnb:
        if menu_url and menu_url not in ('UNAVAILABLE', 'UNAPPLICABLE'):
            change('Menu_Photo_URL', menu_url, 'UNAPPLICABLE', 'Not F&B category')
        if not menu_url:
            change('Menu_Photo_URL', '', 'UNAPPLICABLE', 'Not F&B category')

    if video_url and video_url not in ('UNAVAILABLE', 'UNAPPLICABLE', ''):
        if not _re.search(r'\.(mp4|mov)$', video_url, _re.I) and 'youtube' not in video_url and 'youtu.be' not in video_url:
            flag_w('GATE-D4', 'Video_URL', 'Invalid video format (must be mp4/mov/youtube)', 'Fix URL or set UNAVAILABLE')
            change('Video_URL', video_url, 'UNAVAILABLE', 'Invalid video format')

    # E) Category
    if not cat:
        flag_b('GATE-E1', 'Category', 'Category is empty', 'Select a valid category')
    # Keyword mismatch detection
    name_lower = (name_ar + ' ' + name_en).lower()
    if 'صيدلية' in name_lower or 'pharmacy' in name_lower:
        if cat and 'health' not in cat.lower() and 'clinic' not in cat.lower() and 'pharma' not in cat.lower():
            flag_w('GATE-E2', 'Category', f'Name suggests pharmacy but category is {cat}', 'Consider Pharmacies')
    if 'مطعم' in name_lower or 'restaurant' in name_lower:
        if cat and not is_fnb:
            flag_w('GATE-E3', 'Category', f'Name suggests restaurant but category is {cat}', 'Consider Restaurants')

    # F) Company Status
    status = (poi.get('Company_Status') or '').strip()
    valid_statuses = {'Open', 'Temporarily Closed', 'Permanently Closed', 'Closed'}
    if status and status not in valid_statuses:
        flag_w('GATE-F1', 'Company_Status', f'Invalid status: {status}', 'Use Open/Temporarily Closed/Permanently Closed')
    if status == 'Closed':
        change('Company_Status', 'Closed', 'Permanently Closed', 'Normalized Closed → Permanently Closed')

    # G) Coordinates
    try:
        lat = float(poi.get('Latitude', 0) or 0)
        lon = float(poi.get('Longitude', 0) or 0)
        if lat < 15 or lat > 35:
            flag_b('GATE-G1', 'Latitude', f'Out of Saudi bounds: {lat}', 'Must be 15-35')
        if lon < 35 or lon > 60:
            flag_b('GATE-G2', 'Longitude', f'Out of Saudi bounds: {lon}', 'Must be 35-60')
    except (TypeError, ValueError):
        flag_b('GATE-G3', 'Latitude', 'Non-numeric coordinates', 'Provide valid lat/lon')

    # District
    district_en = (poi.get('District_EN') or '').strip()
    if not district_en:
        flag_w('GATE-G4', 'District_EN', 'District EN is empty', 'Provide district name')

    # H) Building/Floor/Entrance
    bldg = (poi.get('Building_Number') or '').strip()
    if bldg and bldg != 'UNAVAILABLE' and not _re.match(r'^\d{4}$', bldg):
        flag_w('GATE-H1', 'Building_Number', f'Not 4 digits: {bldg}', 'Must be 4-digit number or UNAVAILABLE')

    floor = (poi.get('Floor_Number') or '').strip()
    valid_floors = {'G', 'B1', '1', '2', '3', '4', '5', 'UNAVAILABLE', ''}
    if floor and floor not in valid_floors:
        flag_w('GATE-H2', 'Floor_Number', f'Invalid floor: {floor}', 'Use G/B1/1-5 or UNAVAILABLE')
        change('Floor_Number', floor, 'UNAVAILABLE', 'Invalid floor value')

    # I) Phone
    phone = (poi.get('Phone_Number') or '').strip()
    if phone and phone != 'UNAVAILABLE':
        if _re.match(r'.*[eE]\+', phone):  # Scientific notation
            flag_w('GATE-I1', 'Phone_Number', 'Phone in scientific notation', 'Fix format or UNAVAILABLE')
            change('Phone_Number', phone, 'UNAVAILABLE', 'Scientific notation detected')
        elif not _SAUDI_PHONE.match(phone.replace(' ', '').replace('-', '')):
            flag_w('GATE-I2', 'Phone_Number', f'Invalid phone format: {phone}', 'Must be Saudi format')

    # Email
    email = (poi.get('Email') or '').strip()
    if email and email != 'UNAVAILABLE' and not _EMAIL_RE.match(email):
        flag_w('GATE-I3', 'Email', f'Invalid email: {email}', 'Fix format or set UNAVAILABLE')
        change('Email', email, 'UNAVAILABLE', 'Invalid email format')

    # Website - no Google Maps
    website = (poi.get('Website') or '').strip()
    if website and ('google.com/maps' in website or 'goo.gl/maps' in website or 'maps.google.com' in website):
        flag_w('GATE-I4', 'Website', 'Website is a Google Maps link', 'Move to Google_Map_URL, set Website=UNAVAILABLE')
        if not poi.get('Google_Map_URL'):
            change('Google_Map_URL', '', website, 'Moved Google Maps link from Website')
        change('Website', website, 'UNAVAILABLE', 'Was Google Maps link')

    # Website - no social media links
    if website and website != 'UNAVAILABLE' and corrected.get('Website') != 'UNAVAILABLE':
        for domain in _WEBSITE_SOCIAL_BLOCKLIST:
            if domain in website.lower():
                flag_w('GATE-I4b', 'Website', f'Website is a social media link ({domain})',
                       'Move to Social_Media, set Website=UNAVAILABLE')
                social_val = (poi.get('Social_Media') or '').strip()
                if not social_val or social_val == 'UNAVAILABLE':
                    change('Social_Media', social_val or '', website, 'Moved social link from Website')
                change('Website', website, 'UNAVAILABLE', f'Was social media link ({domain})')
                break

    # Social Media - no WhatsApp / no phone numbers
    social = (poi.get('Social_Media') or '').strip()
    if social and social != 'UNAVAILABLE':
        if 'wa.me' in social or 'whatsapp' in social.lower():
            flag_w('GATE-I5', 'Social_Media', 'Contains WhatsApp link', 'Use social profile URL only')
        if _re.match(r'^\+?\d{10,}$', social.replace(' ', '')):
            flag_w('GATE-I6', 'Social_Media', 'Contains phone number instead of social profile', 'Use profile URL')
            change('Social_Media', social, 'UNAVAILABLE', 'Was phone number, not social profile')

    # J) Working Hours
    hours = (poi.get('Working_Hours') or '').strip()
    if not hours:
        flag_b('GATE-J1', 'Working_Hours', 'Working hours missing', 'Provide working hours')
    elif hours not in ('UNAVAILABLE', 'Open 24 Hours'):
        if not _re.search(r'\d{1,2}:\d{2}\s*[-\u2013]\s*\d{1,2}:\d{2}', hours):
            flag_w('GATE-J2', 'Working_Hours', f'Non-standard hours format: "{hours}"',
                   'Use HH:MM - HH:MM format (e.g., Mon: 08:00-22:00)')
        else:
            # J3) Opening must be before closing
            for m in _re.finditer(r'(\d{1,2}):(\d{2})\s*[-\u2013]\s*(\d{1,2}):(\d{2})', hours):
                open_min = int(m.group(1)) * 60 + int(m.group(2))
                close_min = int(m.group(3)) * 60 + int(m.group(4))
                if open_min > close_min and (open_min - close_min) > 180:
                    flag_w('GATE-J3', 'Working_Hours',
                           f'Opening time after closing: {m.group(0)}',
                           'Swap opening and closing times')
                    break

    # K) Boolean fields - category logic
    for field in _ALL_BOOLS:
        val = (poi.get(field) or '').strip()
        if val and val not in ('Yes', 'No', 'UNAVAILABLE', 'UNAPPLICABLE'):
            change(field, val, 'UNAVAILABLE', f'Invalid boolean value: {val}')
            flag_w('GATE-K1', field, f'Invalid value: {val}', 'Must be Yes/No/UNAVAILABLE/UNAPPLICABLE')

        # F&B-only fields for non-F&B
        if field in _FNB_ONLY_BOOLS and not is_fnb:
            if val and val not in ('UNAPPLICABLE', ''):
                change(field, val, 'UNAPPLICABLE', 'Not F&B category')
        # Mosque-only for non-mosque
        if field in _MOSQUE_ONLY_BOOLS and not is_mosque:
            if val and val not in ('UNAPPLICABLE', ''):
                change(field, val, 'UNAPPLICABLE', 'Not Mosque category')
        # Attraction-only for non-attraction
        if field in _ATTRACTION_ONLY_BOOLS and not is_attraction:
            if val and val not in ('UNAPPLICABLE', ''):
                change(field, val, 'UNAPPLICABLE', 'Not Attraction category')

    # Commercial License — exactly 10 digits per Saudi CR format
    lic = (poi.get('Commercial_License') or '').strip()
    if lic and lic != 'UNAVAILABLE' and not _re.match(r'^\d{10}$', lic):
        flag_w('GATE-L1', 'Commercial_License', f'Not exactly 10 digits: {lic}', 'Provide 10-digit license number')

    # SV) Sentinel value rejection — reject placeholder text
    for sv_field in _SENTINEL_TEXT_FIELDS:
        fv = (corrected.get(sv_field) or '').strip()
        if fv and fv.lower() in _BAD_SENTINELS:
            flag_w('GATE-SV1', sv_field, f'Sentinel value detected: "{fv}"', 'Set to UNAVAILABLE or provide real data')
            change(sv_field, fv, 'UNAVAILABLE', f'Bad sentinel "{fv}" replaced')

    # E4/E5/E6) Category hierarchy validation against taxonomy
    if cat and _VALID_CATEGORIES:
        if cat not in _VALID_CATEGORIES:
            flag_w('GATE-E4', 'Category', f'Category "{cat}" not in taxonomy', 'Use a valid category')
        else:
            sub = (poi.get('Subcategory') or '').strip()
            l3 = (poi.get('Category_Level_3') or '').strip()
            valid_subs = set(_TAXONOMY[cat].get('subs', {}).keys())
            if sub and valid_subs and sub not in valid_subs:
                first5 = ', '.join(sorted(list(valid_subs))[:5])
                flag_w('GATE-E5', 'Subcategory', f'Subcategory "{sub}" not valid under "{cat}"',
                       f'Valid: {first5}...')
            if sub and l3:
                sub_data = _TAXONOMY[cat].get('subs', {}).get(sub, {})
                valid_l3_list = sub_data.get('l3', [])
                valid_l3_names = {item.get('name', item) if isinstance(item, dict) else item for item in valid_l3_list}
                if valid_l3_names and l3 not in valid_l3_names:
                    first5 = ', '.join(sorted(list(valid_l3_names))[:5])
                    flag_w('GATE-E6', 'Category_Level_3', f'L3 "{l3}" not valid under "{cat} > {sub}"',
                           f'Valid: {first5}...')

    # Duplicate media detection (errors 3/16/20)
    urls_seen = {}
    for mfield in ['Exterior_Photo_URL', 'Interior_Photo_URL', 'Menu_Photo_URL', 'Video_URL', 'License_Photo_URL']:
        u = (corrected.get(mfield) or '').strip()
        if u and u not in ('UNAVAILABLE', 'UNAPPLICABLE', ''):
            if u in urls_seen:
                flag_w('GATE-DUP', mfield, f'Duplicate URL (same as {urls_seen[u]})', 'Use unique media per field')
                change(mfield, u, 'UNAVAILABLE', f'Duplicate of {urls_seen[u]}')
            else:
                urls_seen[u] = mfield

    # Determine status
    status_val = 'PASS'
    if blockers:
        status_val = 'FAIL_BLOCKER'
    elif warnings or changes:
        status_val = 'PASS_WITH_WARNINGS'

    return corrected, status_val, blockers, warnings, changes


@api.route('/validate-poi', methods=['POST'])
def validate_poi():
    """Full QA validation for a single POI record. Returns corrected record + QA report."""
    poi = request.get_json()
    if not poi:
        return api_error('No data', 400, code=VALIDATION_ERROR)
    corrected, status_val, blockers, warnings, changes = _validate_poi_core(poi)
    return jsonify({
        'poi_final': corrected,
        'qa_report': {
            'status': status_val,
            'blockers': blockers,
            'warnings': warnings,
            'changes_made': changes
        }
    })


@api.route('/validate-all', methods=['POST'])
def validate_all_pois():
    """Validate ALL POIs in the database. Optionally apply auto-fixes.

    POST body: { "apply_fixes": true/false, "flag_violations": true/false }
    - apply_fixes: write auto-corrected values back to DB
    - flag_violations: set flagged=true + flag_reason for POIs with blockers
    """
    body = request.get_json() or {}
    apply_fixes = body.get('apply_fixes', False)
    flag_violations = body.get('flag_violations', False)
    reviewer = body.get('_reviewer', 'system-validation')

    conn = get_db()
    cur = conn.cursor(cursor_factory=RealDictCursor)
    cur.execute('SELECT * FROM final_delivery')
    rows = cur.fetchall()

    # Cross-POI media duplicate check: URL -> list of GlobalIDs
    media_url_owners = {}
    for row in rows:
        for mf in ['Exterior_Photo_URL', 'Interior_Photo_URL', 'Video_URL']:
            url = (row.get(mf) or '').strip()
            if url and url not in ('UNAVAILABLE', 'UNAPPLICABLE', '') and url.startswith('http'):
                media_url_owners.setdefault(url, []).append(
                    {'gid': row['GlobalID'], 'field': mf, 'name': row.get('Name_EN', '')})

    results = []
    fixed_count = 0
    flagged_count = 0
    total_blockers = 0
    total_warnings = 0

    for row in rows:
        poi_dict = dict(row)
        # Convert non-serializable types
        for k, v in poi_dict.items():
            if hasattr(v, 'isoformat'):
                poi_dict[k] = v.isoformat()
            elif isinstance(v, (bytes, memoryview)):
                poi_dict[k] = str(v)

        corrected, status_val, blockers, warnings, changes = _validate_poi_core(poi_dict)

        # Cross-POI media duplicate detection
        for mf in ['Exterior_Photo_URL', 'Interior_Photo_URL', 'Video_URL']:
            url = (poi_dict.get(mf) or '').strip()
            if url and url.startswith('http') and url in media_url_owners:
                others = [x for x in media_url_owners[url] if x['gid'] != poi_dict.get('GlobalID')]
                if others:
                    warnings.append({
                        'rule': 'CROSS-M3', 'field': mf,
                        'message': f'Media shared with {len(others)} other POI(s): '
                                   f'{", ".join(x["name"] for x in others[:3])}',
                        'fix': 'Each POI must have unique media'
                    })

        gid = poi_dict.get('GlobalID')
        total_blockers += len(blockers)
        total_warnings += len(warnings)

        entry = {
            'GlobalID': gid,
            'Name_EN': poi_dict.get('Name_EN', ''),
            'status': status_val,
            'blockers': len(blockers),
            'warnings': len(warnings),
            'fixes_available': len(changes),
        }

        if apply_fixes and changes:
            update_fields = {}
            for ch in changes:
                field_name = ch.get('field')
                new_val = ch.get('new')
                if field_name and new_val is not None:
                    update_fields[field_name] = new_val
            if update_fields:
                set_clauses = ', '.join(f'"{k}" = %s' for k in update_fields.keys())
                vals = list(update_fields.values()) + [gid]
                cur.execute(f'UPDATE final_delivery SET {set_clauses} WHERE "GlobalID" = %s', vals)
                fixed_count += 1
                entry['fixes_applied'] = len(update_fields)

        if flag_violations and blockers:
            blocker_reasons = '; '.join(b.get('message', b.get('rule', ''))[:60] for b in blockers[:3])
            reason = f'Auto-validation: {len(blockers)} blocker(s) - {blocker_reasons}'[:200]
            cur.execute(
                'UPDATE final_delivery SET flagged = TRUE, flag_reason = %s WHERE "GlobalID" = %s',
                (reason, gid))
            flagged_count += 1
            entry['flagged'] = True
            entry['flag_reason'] = reason

        if blockers or warnings:
            results.append(entry)

    conn.commit()
    cur.close()
    conn.close()

    return api_success({
        'total_pois': len(rows),
        'pois_with_issues': len(results),
        'total_blockers': total_blockers,
        'total_warnings': total_warnings,
        'fixes_applied': fixed_count if apply_fixes else 0,
        'pois_flagged': flagged_count if flag_violations else 0,
        'issues': results[:500],  # Limit response size
    })


# ===== API: Duplicate Detection (Hybrid Weighted Scoring) =====
@api.route('/detect-duplicates', methods=['POST'])
def detect_duplicates_endpoint():
    """Server-side duplicate detection using hybrid weighted scoring.
    Combines spatial proximity, bilingual fuzzy names, phone/license/website
    signals, and category validation into a weighted score."""
    from duplicate_matcher import detect_duplicates as run_detection

    body = request.get_json() or {}
    max_distance = body.get('max_distance', body.get('distance_threshold', 100))
    match_threshold = body.get('match_threshold', body.get('name_threshold', 85))
    possible_threshold = body.get('possible_threshold', 70)
    include_possible = body.get('include_possible', True)

    conn = get_db()
    ensure_tables()
    cur = conn.cursor(cursor_factory=RealDictCursor)
    cur.execute('''SELECT "GlobalID", "Name_EN", "Name_AR", "Phone_Number",
                   "Category", "Latitude", "Longitude", "Building_Number",
                   "Floor_Number", "Commercial_License", "Website",
                   "Google_Map_URL"
                   FROM final_delivery''')
    pois = cur.fetchall()
    cur.close()
    conn.close()

    result = run_detection(
        pois,
        max_distance=max_distance,
        match_threshold=match_threshold,
        possible_threshold=possible_threshold,
        include_possible=include_possible,
    )

    return jsonify(result)

# ===== API: Match Review (Human Labelling for ML Training) =====
@api.route('/match-reviews', methods=['POST'])
def save_match_review():
    """Save a human review decision for a duplicate pair."""
    ensure_tables()
    data = request.get_json()
    if not data:
        return api_error('No data', 400, code=VALIDATION_ERROR)

    required = ['source_gid', 'candidate_gid', 'reviewer', 'verdict']
    for field in required:
        if not data.get(field):
            return api_error(f'Missing required field: {field}', 400, code=VALIDATION_ERROR)

    verdict = data['verdict'].upper()
    if verdict not in ('MATCH', 'NOT_MATCH'):
        return api_error('Verdict must be MATCH or NOT_MATCH', 400, code=VALIDATION_ERROR)

    conn = get_db()
    cur = conn.cursor(cursor_factory=RealDictCursor)
    try:
        # Upsert: if same reviewer already reviewed this pair, update
        cur.execute("""
            INSERT INTO match_reviews (
                source_gid, candidate_gid, source_name, candidate_name,
                reviewer, verdict, final_score, name_score, distance_score,
                category_score, phone_score, auxiliary_score, distance_m,
                source_category, candidate_category,
                source_lat, source_lng, candidate_lat, candidate_lng,
                match_reasons, tier1_match, notes
            ) VALUES (
                %(source_gid)s, %(candidate_gid)s, %(source_name)s, %(candidate_name)s,
                %(reviewer)s, %(verdict)s, %(final_score)s, %(name_score)s, %(distance_score)s,
                %(category_score)s, %(phone_score)s, %(auxiliary_score)s, %(distance_m)s,
                %(source_category)s, %(candidate_category)s,
                %(source_lat)s, %(source_lng)s, %(candidate_lat)s, %(candidate_lng)s,
                %(match_reasons)s, %(tier1_match)s, %(notes)s
            )
            ON CONFLICT (source_gid, candidate_gid, reviewer)
            DO UPDATE SET
                verdict = EXCLUDED.verdict,
                notes = EXCLUDED.notes,
                created_at = NOW()
            RETURNING id, created_at::text;
        """, {
            'source_gid': data['source_gid'],
            'candidate_gid': data['candidate_gid'],
            'source_name': data.get('source_name', ''),
            'candidate_name': data.get('candidate_name', ''),
            'reviewer': data['reviewer'],
            'verdict': verdict,
            'final_score': data.get('final_score'),
            'name_score': data.get('name_score'),
            'distance_score': data.get('distance_score'),
            'category_score': data.get('category_score'),
            'phone_score': data.get('phone_score'),
            'auxiliary_score': data.get('auxiliary_score'),
            'distance_m': data.get('distance_m'),
            'source_category': data.get('source_category', ''),
            'candidate_category': data.get('candidate_category', ''),
            'source_lat': data.get('source_lat'),
            'source_lng': data.get('source_lng'),
            'candidate_lat': data.get('candidate_lat'),
            'candidate_lng': data.get('candidate_lng'),
            'match_reasons': data.get('match_reasons', ''),
            'tier1_match': data.get('tier1_match', False),
            'notes': data.get('notes', ''),
        })
        row = cur.fetchone()
        conn.commit()
        return api_success({'id': row['id'], 'created_at': row['created_at']})
    except Exception as e:
        conn.rollback()
        return api_error(f'Failed to save review: {e}', 500)
    finally:
        cur.close()
        conn.close()


@api.route('/match-reviews', methods=['GET'])
def get_match_reviews():
    """Get all match reviews, optionally filtered by reviewer or pair."""
    ensure_tables()
    reviewer = request.args.get('reviewer', '')
    source_gid = request.args.get('source_gid', '')
    verdict = request.args.get('verdict', '')
    limit = min(int(request.args.get('limit', 500)), 5000)
    offset = int(request.args.get('offset', 0))

    conn = get_db()
    cur = conn.cursor(cursor_factory=RealDictCursor)

    where_clauses = []
    params = []
    if reviewer:
        where_clauses.append("reviewer = %s")
        params.append(reviewer)
    if source_gid:
        where_clauses.append("(source_gid = %s OR candidate_gid = %s)")
        params.extend([source_gid, source_gid])
    if verdict:
        where_clauses.append("verdict = %s")
        params.append(verdict.upper())

    where_sql = ''
    if where_clauses:
        where_sql = 'WHERE ' + ' AND '.join(where_clauses)

    cur.execute(f"""
        SELECT id, source_gid, candidate_gid, source_name, candidate_name,
               reviewer, verdict, final_score, name_score, distance_score,
               category_score, phone_score, auxiliary_score, distance_m,
               source_category, candidate_category,
               source_lat, source_lng, candidate_lat, candidate_lng,
               match_reasons, tier1_match, notes, created_at::text
        FROM match_reviews
        {where_sql}
        ORDER BY created_at DESC
        LIMIT %s OFFSET %s;
    """, params + [limit, offset])
    rows = cur.fetchall()

    cur.execute(f"SELECT COUNT(*) FROM match_reviews {where_sql};", params)
    total = cur.fetchone()['count']

    cur.close()
    conn.close()
    return jsonify({'reviews': rows, 'total': total})


@api.route('/match-reviews/reviewed-pairs', methods=['GET'])
def get_reviewed_pair_ids():
    """Get set of already-reviewed pair keys for the current reviewer (to skip in UI)."""
    ensure_tables()
    reviewer = request.args.get('reviewer', '')
    if not reviewer:
        return api_error('reviewer parameter required', 400, code=VALIDATION_ERROR)

    conn = get_db()
    cur = conn.cursor()
    cur.execute("""
        SELECT source_gid || '|' || candidate_gid AS pair_key, verdict
        FROM match_reviews WHERE reviewer = %s;
    """, (reviewer,))
    pairs = {row[0]: row[1] for row in cur.fetchall()}
    cur.close()
    conn.close()
    return jsonify(pairs)


@api.route('/match-reviews/export-training', methods=['GET'])
def export_training_data():
    """Export all reviewed pairs as ML training data (CSV or JSON)."""
    ensure_tables()
    fmt = request.args.get('format', 'json').lower()

    conn = get_db()
    cur = conn.cursor(cursor_factory=RealDictCursor)
    cur.execute("""
        SELECT source_gid, candidate_gid, source_name, candidate_name,
               verdict, final_score, name_score, distance_score,
               category_score, phone_score, auxiliary_score, distance_m,
               source_category, candidate_category,
               source_lat, source_lng, candidate_lat, candidate_lng,
               match_reasons, tier1_match, reviewer, created_at::text
        FROM match_reviews
        ORDER BY created_at;
    """)
    rows = cur.fetchall()
    cur.close()
    conn.close()

    if fmt == 'csv':
        import csv, io
        if not rows:
            return ('', 200, {'Content-Type': 'text/csv'})
        output = io.StringIO()
        writer = csv.DictWriter(output, fieldnames=rows[0].keys())
        writer.writeheader()
        writer.writerows(rows)
        return (output.getvalue(), 200, {
            'Content-Type': 'text/csv',
            'Content-Disposition': 'attachment; filename=match_training_data.csv'
        })

    return jsonify({
        'training_data': rows,
        'total_samples': len(rows),
        'match_count': sum(1 for r in rows if r['verdict'] == 'MATCH'),
        'not_match_count': sum(1 for r in rows if r['verdict'] == 'NOT_MATCH'),
    })


@api.route('/match-reviews/stats', methods=['GET'])
def match_review_stats():
    """Get review progress statistics."""
    ensure_tables()
    conn = get_db()
    cur = conn.cursor(cursor_factory=RealDictCursor)
    cur.execute("""
        SELECT
            COUNT(*) as total_reviews,
            COUNT(*) FILTER (WHERE verdict = 'MATCH') as match_count,
            COUNT(*) FILTER (WHERE verdict = 'NOT_MATCH') as not_match_count,
            COUNT(DISTINCT reviewer) as reviewer_count,
            COUNT(DISTINCT source_gid || '|' || candidate_gid) as unique_pairs
        FROM match_reviews;
    """)
    stats = cur.fetchone()
    cur.close()
    conn.close()
    return jsonify(stats)


# ===== API: Reviewer Login =====
@api.route('/login', methods=['POST'])
def reviewer_login():
    data = request.get_json()
    if not data:
        return api_error('No data', 400, code=VALIDATION_ERROR)
    username = (data.get('username') or '').strip().lower()
    password = data.get('password') or ''
    if not username or not password:
        return api_error('Username and password required', 400, code=VALIDATION_ERROR)

    conn = get_db()
    ensure_tables()
    cur = conn.cursor(cursor_factory=RealDictCursor)
    cur.execute("SELECT * FROM reviewers WHERE username = %s AND active = TRUE", (username,))
    user = cur.fetchone()
    cur.close()
    conn.close()

    if not user or user['password_hash'] != _hash_pw(password):
        return api_error('Invalid credentials', 401)

    return api_success({
        'username': user['username'],
        'display_name': user['display_name'],
        'role': user['role']
    })

# ===== API: List reviewers =====
@api.route('/reviewers', methods=['GET'])
def list_reviewers():
    conn = get_db()
    ensure_tables()
    cur = conn.cursor(cursor_factory=RealDictCursor)
    cur.execute("SELECT id, username, display_name, role, active, created_at::text FROM reviewers ORDER BY id;")
    rows = cur.fetchall()
    cur.close()
    conn.close()
    return jsonify(rows)

# ===== API: Audit Log =====
@api.route('/audit-log', methods=['GET'])
def get_audit_log():
    ensure_tables()
    reviewer = request.args.get('reviewer', '')
    global_id = request.args.get('global_id', '')
    limit = min(int(request.args.get('limit', 200)), 1000)
    offset = int(request.args.get('offset', 0))

    conn = get_db()
    cur = conn.cursor(cursor_factory=RealDictCursor)

    where_clauses = []
    params = []
    if reviewer:
        where_clauses.append("reviewer = %s")
        params.append(reviewer)
    if global_id:
        where_clauses.append("global_id = %s")
        params.append(global_id)

    where_sql = ''
    if where_clauses:
        where_sql = 'WHERE ' + ' AND '.join(where_clauses)

    cur.execute(f"""
        SELECT id, global_id, poi_name, reviewer, action, field_name,
               old_value, new_value, created_at::text
        FROM poi_audit_log
        {where_sql}
        ORDER BY created_at DESC
        LIMIT %s OFFSET %s;
    """, params + [limit, offset])
    rows = cur.fetchall()

    # Get total count
    cur.execute(f"SELECT COUNT(*) FROM poi_audit_log {where_sql};", params)
    total = cur.fetchone()['count']

    cur.close()
    conn.close()
    return jsonify({'logs': rows, 'total': total})

# ===== API: Audit Log Stats (per reviewer) =====
@api.route('/audit-log/stats', methods=['GET'])
def audit_stats():
    ensure_tables()
    conn = get_db()
    cur = conn.cursor(cursor_factory=RealDictCursor)
    cur.execute("""
        SELECT reviewer,
               COUNT(DISTINCT global_id) as pois_edited,
               COUNT(*) as total_changes,
               MAX(created_at)::text as last_activity
        FROM poi_audit_log
        GROUP BY reviewer
        ORDER BY total_changes DESC;
    """)
    rows = cur.fetchall()
    cur.close()
    conn.close()
    return jsonify(rows)

# ===== Draft POI Category Mapping =====
_DRAFT_CAT_MAP = {
    'Restaurants': 'Restaurants', 'Restaurant': 'Restaurants', 'restaurants': 'Restaurants',
    'Coffee Shops': 'Coffee Shops', 'Coffee Shop': 'Coffee Shops', 'Cafe': 'Coffee Shops',
    'Café': 'Coffee Shops', 'Cafes': 'Coffee Shops',
    'Shopping': 'Shopping', 'Retail': 'Shopping', 'Shopping & Distribution': 'Shopping',
    'shopping_distribution': 'Shopping', 'Mall / Shopping Center': 'Shopping',
    'Corporate': 'Corporate', 'Corporate Office': 'Corporate',
    'Services & Industry': 'Corporate', 'services_industry': 'Corporate',
    'Professional Services': 'Corporate', 'Business Consulting': 'Corporate',
    'Legal Services': 'Corporate', 'Contracting': 'Corporate', 'Contractor': 'Corporate',
    'Construction': 'Corporate', 'Construction Services': 'Corporate',
    'Facilities Services': 'Corporate', 'Translation Service': 'Corporate',
    'Environmental Services': 'Corporate', 'Engineering Consultancy': 'Corporate',
    'Coworking Space': 'Corporate', 'Event Planners': 'Corporate', 'Event Planning': 'Corporate',
    'Event Venue': 'Corporate', 'Media company': 'Corporate', 'Services': 'Corporate',
    'Insurance Company': 'Corporate', 'HVAC Services': 'Corporate',
    'Beauty and Spa': 'Beauty and Spa', 'Beauty & Spa': 'Beauty and Spa',
    'Salon': 'Beauty and Spa', 'Beauty Clinic': 'Beauty and Spa',
    'Automotive Services': 'Automotive Services', 'Automotive Repair': 'Automotive Services',
    'Car Rental': 'Automotive Services',
    'Home Goods': 'Home Goods', 'Home Services': 'Home Goods',
    'Food and Beverages': 'Food and Beverages', 'Bakery': 'Food and Beverages',
    'Dessert Shop': 'Food and Beverages',
    'Grocery': 'Grocery',
    'Banks': 'Banks', 'Bank': 'Banks', 'finance_insurance': 'Banks',
    'Sports': 'Sports', 'Sports & Recreation': 'Sports', 'Sports Club': 'Sports', 'Gym': 'Sports',
    'Hospitals': 'Hospitals', 'Health & Medical': 'Hospitals', 'health_medical': 'Hospitals',
    'Healthcare': 'Hospitals', 'Medical Center': 'Hospitals', 'Medical Clinic': 'Hospitals',
    'Clinic': 'Hospitals', 'Health & Wellness Center': 'Hospitals',
    'Hotels and Accommodations': 'Hotels and Accommodations', 'Hotel': 'Hotels and Accommodations',
    'accommodation': 'Hotels and Accommodations', 'Accommodation': 'Hotels and Accommodations',
    'Residential Compound': 'Hotels and Accommodations',
    'Pharmacies': 'Pharmacies', 'Pharmacy': 'Pharmacies',
    'Education': 'Education', 'School': 'Education', 'Educational Institution': 'Education',
    'Childcare': 'Education',
    'Government Services': 'Government Services', 'Government': 'Government Services',
    'Entertainment': 'Entertainment', 'Photography Studio': 'Entertainment',
    'Transportation': 'Transportation',
    'Fuel Stations': 'Fuel Stations',
    'Cultural Sites': 'Cultural Sites',
    'Nature': 'Nature', 'Park': 'Nature',
    'Public Parks': 'Public Parks',
    'Public Services': 'Public Services', 'Non-profit organization': 'Public Services',
    'Non-Profit Organization': 'Public Services', 'Emergency Services': 'Public Services',
    'Mosques': 'Mosques', 'Mosque': 'Mosques',
    'Life & Convenience': 'Corporate', 'life_convenience': 'Corporate',
    'Real Estate': 'Corporate', 'Real Estate Agency': 'Corporate',
    'Laundry': 'Corporate', 'Laundry Service': 'Corporate',
    'Cleaning Service': 'Corporate', 'Repair Workshop': 'Corporate',
    'Telecommunication': 'Corporate', 'Telecommunications': 'Corporate',
    'Travel Agency': 'Corporate', 'Neighborhood': 'Public Services',
    'الفنادق والإقامة': 'Hotels and Accommodations',
    'Energy and Utilities': 'Corporate',
}

def _map_draft_cat(raw_cat):
    """Map a CSV category string to one of the 25 taxonomy categories."""
    raw = (raw_cat or '').strip()
    if not raw:
        return ''
    if raw in _DRAFT_CAT_MAP:
        return _DRAFT_CAT_MAP[raw]
    return raw  # keep as-is if unknown

def _quick_qa(draft):
    """Lightweight QA: count blockers and warnings for a draft POI."""
    b, w = 0, 0
    name_ar = (draft.get('Name_AR') or '').strip()
    name_en = (draft.get('Name_EN') or '').strip()
    if not name_ar or len(name_ar) < 2: b += 1
    if not name_en or len(name_en) < 2: b += 1
    cat = (draft.get('Category') or '').strip()
    if not cat: b += 1
    lat = draft.get('Latitude') or ''
    lon = draft.get('Longitude') or ''
    try:
        la = float(lat); lo = float(lon)
        if la < 15 or la > 35: b += 1
        if lo < 35 or lo > 60: b += 1
    except (ValueError, TypeError):
        if lat or lon: b += 1
        else: b += 1  # missing coords
    if not (draft.get('Phone_Number') or '').strip(): w += 1
    if not (draft.get('Website') or '').strip(): w += 1
    return b, w


# ===== API: Draft POIs =====

@api.route('/drafts/import', methods=['POST'])
def import_drafts():
    """Bulk import draft POIs from CSV file."""
    ensure_tables()
    if 'file' not in request.files:
        return api_error('No file provided. Use multipart form with key "file".', 400, code=VALIDATION_ERROR)

    file = request.files['file']
    batch_id = str(uuid.uuid4())[:8]

    content = file.read().decode('utf-8-sig')
    reader = csv.DictReader(io.StringIO(content))

    conn = get_db()
    cur = conn.cursor()

    imported = 0
    skipped = 0
    errs = []

    for i, row in enumerate(reader):
        try:
            name_en = (row.get('Name_EN') or '').strip()
            name_ar = (row.get('Name_AR') or '').strip()
            if not name_en and not name_ar:
                skipped += 1
                continue

            raw_cat = (row.get('Category') or '').strip()
            raw_sub = (row.get('Subcategory') or '').strip()
            mapped_cat = _map_draft_cat(raw_cat)

            lat = (row.get('Latitude') or '').strip()
            lon = (row.get('Longitude') or '').strip()
            if lat.lower() == 'none': lat = ''
            if lon.lower() == 'none': lon = ''

            phone = (row.get('Phone') or '').strip()
            website = (row.get('Website') or '').strip()
            gmap = (row.get('Google_Map') or '').strip()
            if not gmap and lat and lon:
                gmap = f'https://www.google.com/maps?q={lat},{lon}'

            # Extract cuisine from Extra_Info if available
            extra = (row.get('Extra_Info') or '').strip()
            cuisine = ''
            if 'cuisine=' in extra:
                import re as _r
                m = _r.search(r'cuisine=\{([^}]*)\}', extra)
                if m:
                    cuisine = m.group(1).replace('"', '').strip()

            draft = {
                'Name_EN': name_en, 'Name_AR': name_ar,
                'Category': mapped_cat, 'Subcategory': raw_sub,
                'Original_Category': raw_cat, 'Original_Subcategory': raw_sub,
                'Latitude': lat, 'Longitude': lon,
                'Phone_Number': phone, 'Website': website,
                'Google_Map_URL': gmap, 'Cuisine': cuisine,
                'Source_CSV': (row.get('Source') or '').strip(),
                'Dup_Verdict': (row.get('Dup_Verdict') or '').strip(),
                'Dup_Score': (row.get('Dup_Score') or '').strip(),
                'Match_Type': (row.get('Match_Type') or '').strip(),
                'Similarity': (row.get('Similarity') or '').strip(),
                'Distance_m': (row.get('Distance_m') or '').strip(),
                'Matched_Name': (row.get('Matched_Name') or '').strip(),
                'Matched_GID': (row.get('Matched_GID') or '').strip(),
                'Review_Notes': extra,
                'Import_Batch': batch_id,
                'Draft_Status': 'pending',
            }
            gid = '{DRAFT-' + str(uuid.uuid4()).upper()[:8] + '}'
            draft['GlobalID'] = gid

            blockers, warnings = _quick_qa(draft)
            draft['QA_Blockers'] = blockers
            draft['QA_Warnings'] = warnings

            cols = [f'"{k}"' for k in draft.keys()]
            placeholders = ['%s'] * len(draft)
            cur.execute(
                f'INSERT INTO draft_pois ({", ".join(cols)}) VALUES ({", ".join(placeholders)})',
                list(draft.values())
            )
            imported += 1
        except Exception as e:
            errs.append(f'Row {i+2}: {str(e)[:100]}')
            if len(errs) > 100:
                break

    conn.commit()
    cur.close()
    conn.close()
    return api_success({'batch_id': batch_id, 'imported': imported, 'skipped': skipped, 'errors': errs[:50]})


@api.route('/drafts', methods=['GET'])
def get_drafts():
    """List draft POIs with filters."""
    ensure_tables()
    conn = get_db()
    cur = conn.cursor(cursor_factory=RealDictCursor)

    where = []
    params = []
    status = request.args.get('status')
    if status:
        where.append('"Draft_Status" = %s')
        params.append(status)
    verdict = request.args.get('verdict')
    if verdict:
        where.append('"Dup_Verdict" = %s')
        params.append(verdict)
    search = request.args.get('search')
    if search:
        where.append('("Name_EN" ILIKE %s OR "Name_AR" ILIKE %s)')
        params.extend([f'%{search}%', f'%{search}%'])
    category = request.args.get('category')
    if category == '__empty__':
        where.append("(\"Category\" IS NULL OR \"Category\" = '')")
    elif category:
        where.append('"Category" = %s')
        params.append(category)

    where_sql = (' WHERE ' + ' AND '.join(where)) if where else ''
    cur.execute(f'SELECT COUNT(*) as total FROM draft_pois{where_sql}', params)
    total = cur.fetchone()['total']

    page = int(request.args.get('page', 0))
    limit = min(int(request.args.get('limit', 100)), 500)
    offset = page * limit

    cur.execute(
        f'SELECT * FROM draft_pois{where_sql} ORDER BY id LIMIT %s OFFSET %s',
        params + [limit, offset]
    )
    rows = cur.fetchall()
    cur.close()
    conn.close()

    for r in rows:
        for k, v in r.items():
            if hasattr(v, 'isoformat'):
                r[k] = v.isoformat()

    return jsonify({'drafts': rows, 'total': total, 'page': page, 'limit': limit})


@api.route('/drafts/<globalid>', methods=['PATCH'])
def update_draft(globalid):
    """Update fields on a draft POI."""
    ensure_tables()
    data = request.get_json()
    if not data:
        return api_error('No data', 400, code=VALIDATION_ERROR)

    conn = get_db()
    cur = conn.cursor()

    sets = []
    vals = []
    skip = {'GlobalID', 'id', 'created_at', 'Draft_Status', 'Import_Batch'}
    for k, v in data.items():
        if k in skip:
            continue
        sets.append(f'"{k}" = %s')
        vals.append(v)

    if not sets:
        cur.close(); conn.close()
        return api_error('No valid fields', 400, code=VALIDATION_ERROR)

    sets.append('"updated_at" = NOW()')
    vals.append(globalid)

    cur.execute(f'UPDATE draft_pois SET {", ".join(sets)} WHERE "GlobalID" = %s', vals)
    updated = cur.rowcount
    conn.commit()
    cur.close()
    conn.close()
    return api_success({'updated': updated})


@api.route('/drafts/<globalid>/confirm', methods=['POST'])
def confirm_draft(globalid):
    """Confirm a draft POI — copy to final_delivery."""
    ensure_tables()
    force = request.args.get('force', '').lower() == 'true'
    body = request.get_json(silent=True) or {}

    conn = get_db()
    cur = conn.cursor(cursor_factory=RealDictCursor)

    cur.execute('SELECT * FROM draft_pois WHERE "GlobalID" = %s', (globalid,))
    draft = cur.fetchone()
    if not draft:
        cur.close(); conn.close()
        return api_error('Draft not found', 404, code=NOT_FOUND)
    if draft['Draft_Status'] != 'pending':
        cur.close(); conn.close()
        return api_error(f'Draft already {draft["Draft_Status"]}', 400, code=VALIDATION_ERROR)

    # Duplicate name check
    name_en = (draft.get('Name_EN') or '').strip()
    if name_en and not force:
        cur.execute('SELECT "GlobalID" FROM final_delivery WHERE "Name_EN" = %s LIMIT 1', (name_en,))
        dup = cur.fetchone()
        if dup:
            cur.close(); conn.close()
            return api_error(f'Duplicate: Name_EN "{name_en}" already exists (GID={dup["GlobalID"]}). Use ?force=true to override.', 409, code=CONFLICT)

    prod_gid = '{' + str(uuid.uuid4()).upper() + '}'

    # Get final_delivery columns
    cur.execute("SELECT column_name FROM information_schema.columns WHERE table_name = 'final_delivery'")
    fd_cols = {r['column_name'] for r in cur.fetchall()}

    draft_only = {'id', 'Draft_Status', 'Dup_Verdict', 'Dup_Score', 'Match_Type',
                  'Similarity', 'Distance_m', 'Matched_Name', 'Matched_GID',
                  'Original_Category', 'Original_Subcategory', 'Source_CSV',
                  'Import_Batch', 'QA_Blockers', 'QA_Warnings',
                  'Reviewed_By', 'Reviewed_At', 'created_at', 'updated_at'}

    cols = ['"GlobalID"']
    vals = [prod_gid]
    placeholders = ['%s']

    for key, val in draft.items():
        if key in draft_only or key == 'GlobalID':
            continue
        if key in fd_cols and key not in ('created_at', 'updated_at', 'delivery_date'):
            cols.append(f'"{key}"')
            vals.append(val or '')
            placeholders.append('%s')

    # Tag source
    cols.append('"Source"')
    vals.append(f'draft:{draft.get("Source_CSV", "")}')
    placeholders.append('%s')
    # Confirmed drafts start as Draft status in production (need review)
    cols.append('"Review_Status"')
    vals.append('Draft')
    placeholders.append('%s')
    cols.append('"draft_reason"')
    vals.append('imported')
    placeholders.append('%s')
    cols.append('"review_version"')
    vals.append(0)
    placeholders.append('%s')
    cols.append('"created_at"'); placeholders.append('NOW()')
    cols.append('"updated_at"'); placeholders.append('NOW()')

    try:
        cur.execute(f'INSERT INTO final_delivery ({", ".join(cols)}) VALUES ({", ".join(placeholders)})', vals)
    except Exception as e:
        conn.rollback(); cur.close(); conn.close()
        return api_error(str(e), 500, code=INTERNAL_ERROR)

    reviewer = body.get('reviewer', 'unknown')
    cur.execute(
        '''UPDATE draft_pois SET "Draft_Status" = 'confirmed', "Reviewed_By" = %s, "Reviewed_At" = NOW()
           WHERE "GlobalID" = %s''',
        (reviewer, globalid)
    )
    conn.commit()
    cur.close()
    conn.close()

    sync_to_arcgis('create', prod_gid, dict(draft))
    return api_success({'draft_gid': globalid, 'production_gid': prod_gid})


@api.route('/drafts/<globalid>/reject', methods=['POST'])
def reject_draft(globalid):
    """Reject a draft POI."""
    ensure_tables()
    body = request.get_json(silent=True) or {}
    conn = get_db()
    cur = conn.cursor()
    cur.execute(
        '''UPDATE draft_pois SET "Draft_Status" = 'rejected',
           "Reviewed_By" = %s, "Reviewed_At" = NOW(), "Review_Notes" = COALESCE("Review_Notes",'') || %s
           WHERE "GlobalID" = %s AND "Draft_Status" = 'pending' ''',
        (body.get('reviewer', 'unknown'), '\n[REJECTED] ' + body.get('reason', ''), globalid)
    )
    updated = cur.rowcount
    conn.commit()
    cur.close()
    conn.close()
    if not updated:
        return api_error('Draft not found or already processed', 404, code=NOT_FOUND)
    return api_success()


@api.route('/drafts/bulk-action', methods=['POST'])
def bulk_draft_action():
    """Bulk confirm or reject drafts."""
    ensure_tables()
    body = request.get_json()
    if not body:
        return api_error('No data', 400, code=VALIDATION_ERROR)

    action = body.get('action')
    gids = body.get('globalIds', [])
    reviewer = body.get('reviewer', 'unknown')

    if action not in ('confirm', 'reject') or not gids:
        return api_error('Need action (confirm/reject) and globalIds array', 400, code=VALIDATION_ERROR)

    if action == 'reject':
        conn = get_db()
        cur = conn.cursor()
        reason = body.get('reason', 'Bulk rejected')
        for gid in gids:
            cur.execute(
                '''UPDATE draft_pois SET "Draft_Status" = 'rejected',
                   "Reviewed_By" = %s, "Reviewed_At" = NOW()
                   WHERE "GlobalID" = %s AND "Draft_Status" = 'pending' ''',
                (reviewer, gid)
            )
        conn.commit()
        count = cur.rowcount
        cur.close()
        conn.close()
        return api_success({'processed': len(gids)})

    # Bulk confirm — process each one
    results = []
    for gid in gids:
        try:
            conn = get_db()
            cur = conn.cursor(cursor_factory=RealDictCursor)
            cur.execute('SELECT * FROM draft_pois WHERE "GlobalID" = %s AND "Draft_Status" = \'pending\'', (gid,))
            draft = cur.fetchone()
            if not draft:
                results.append({'gid': gid, 'ok': False, 'error': 'not found/already processed'})
                cur.close(); conn.close()
                continue

            prod_gid = '{' + str(uuid.uuid4()).upper() + '}'
            cur.execute("SELECT column_name FROM information_schema.columns WHERE table_name = 'final_delivery'")
            fd_cols = {r['column_name'] for r in cur.fetchall()}
            draft_only = {'id', 'Draft_Status', 'Dup_Verdict', 'Dup_Score', 'Match_Type',
                          'Similarity', 'Distance_m', 'Matched_Name', 'Matched_GID',
                          'Original_Category', 'Original_Subcategory', 'Source_CSV',
                          'Import_Batch', 'QA_Blockers', 'QA_Warnings',
                          'Reviewed_By', 'Reviewed_At', 'created_at', 'updated_at'}

            cols = ['"GlobalID"']; vals = [prod_gid]; ph = ['%s']
            for key, val in draft.items():
                if key in draft_only or key == 'GlobalID': continue
                if key in fd_cols and key not in ('created_at', 'updated_at', 'delivery_date'):
                    cols.append(f'"{key}"'); vals.append(val or ''); ph.append('%s')
            cols.append('"Source"'); vals.append(f'draft:{draft.get("Source_CSV","")}'); ph.append('%s')
            cols.append('"created_at"'); ph.append('NOW()')
            cols.append('"updated_at"'); ph.append('NOW()')

            cur.execute(f'INSERT INTO final_delivery ({", ".join(cols)}) VALUES ({", ".join(ph)})', vals)
            cur.execute(
                '''UPDATE draft_pois SET "Draft_Status" = 'confirmed', "Reviewed_By" = %s, "Reviewed_At" = NOW()
                   WHERE "GlobalID" = %s''', (reviewer, gid)
            )
            conn.commit()
            results.append({'gid': gid, 'ok': True, 'production_gid': prod_gid})
            cur.close(); conn.close()
        except Exception as e:
            results.append({'gid': gid, 'ok': False, 'error': str(e)[:100]})

    return api_success({'results': results})


@api.route('/drafts/stats', methods=['GET'])
def draft_stats():
    """Return draft POI statistics."""
    ensure_tables()
    conn = get_db()
    cur = conn.cursor(cursor_factory=RealDictCursor)

    cur.execute('SELECT COUNT(*) as total FROM draft_pois')
    total = cur.fetchone()['total']

    cur.execute('''SELECT "Draft_Status", COUNT(*) as count FROM draft_pois GROUP BY "Draft_Status"''')
    by_status = {r['Draft_Status']: r['count'] for r in cur.fetchall()}

    cur.execute('''SELECT "Dup_Verdict", COUNT(*) as count FROM draft_pois GROUP BY "Dup_Verdict"''')
    by_verdict = {r['Dup_Verdict']: r['count'] for r in cur.fetchall()}

    cur.execute('''SELECT "Category", COUNT(*) as count FROM draft_pois WHERE "Draft_Status" = 'pending' GROUP BY "Category" ORDER BY count DESC LIMIT 30''')
    by_category = {(r['Category'] or '(empty)'): r['count'] for r in cur.fetchall()}

    cur.execute('''SELECT COUNT(*) as c FROM draft_pois WHERE "Draft_Status" = 'pending' AND "QA_Blockers" = 0''')
    qa_pass = cur.fetchone()['c']
    cur.execute('''SELECT COUNT(*) as c FROM draft_pois WHERE "Draft_Status" = 'pending' AND "QA_Blockers" > 0''')
    qa_fail = cur.fetchone()['c']

    cur.close()
    conn.close()
    return jsonify({
        'total': total,
        'by_status': by_status,
        'by_verdict': by_verdict,
        'by_category': by_category,
        'qa_pass': qa_pass,
        'qa_fail': qa_fail,
    })


# ===== Presence / Live Users =====
_presence = {}  # {username: {last_seen: timestamp, view: str, poi: str}}
_PRESENCE_TIMEOUT = 60  # seconds before considered offline

@api.route('/presence/heartbeat', methods=['POST'])
def presence_heartbeat():
    """Record a user heartbeat. Body: {username, view?, poi?}"""
    data = request.get_json(silent=True) or {}
    username = data.get('username', '').strip()
    if not username:
        return api_error('username required', status=400)
    _presence[username] = {
        'last_seen': time.time(),
        'view': data.get('view', ''),
        'poi': data.get('poi', ''),
    }
    return api_success({'ok': True})

@api.route('/presence/active', methods=['GET'])
def presence_active():
    """Return currently active users (seen within PRESENCE_TIMEOUT)."""
    now = time.time()
    active = []
    expired = []
    for user, info in _presence.items():
        if now - info['last_seen'] <= _PRESENCE_TIMEOUT:
            active.append({
                'username': user,
                'view': info.get('view', ''),
                'poi': info.get('poi', ''),
                'seconds_ago': int(now - info['last_seen']),
            })
        else:
            expired.append(user)
    for u in expired:
        del _presence[u]
    return api_success({'users': active, 'count': len(active)})


# ===== Admin: reset all review_versions =====
@api.route('/admin/reset-versions', methods=['POST'])
def reset_versions():
    """Reset review_version to 1 for all POIs."""
    conn = get_db()
    cur = conn.cursor()
    cur.execute('UPDATE final_delivery SET "review_version" = 1')
    count = cur.rowcount
    conn.commit()
    cur.close()
    conn.close()
    return api_success({'reset': count, 'new_version': 1})

# Register API blueprint
app.register_blueprint(api)

# Health check + init
@app.route('/')
def health():
    return jsonify({'status': 'ok', 'service': 'POI API Server'})

# Initialize tables and seed reviewers on startup
with app.app_context():
    try:
        ensure_tables()
        _seed_reviewers()
        print('Reviewer accounts seeded.')
    except Exception as e:
        print(f'Startup init: {e}')

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 8080))
    print(f'POI API Server starting on port {port}')
    app.run(host='0.0.0.0', port=port, debug=False)
