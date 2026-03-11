"""
سكربت اختبار سلامة البيانات - يتصل بقاعدة البيانات الإنتاجية
ويفحص:
1. عدد السجلات الموجودة
2. الحقول الفارغة والناقصة
3. اختبار إدخال بيانات جديدة واسترجاعها
4. مقارنة المدخلات بالمحفوظات
5. فحص فقدان البيانات
"""
import os
import sys

# Fix encoding for Windows
os.environ['PYTHONIOENCODING'] = 'utf-8'
if sys.stdout.encoding != 'utf-8':
    sys.stdout.reconfigure(encoding='utf-8')

import psycopg2
from psycopg2.extras import RealDictCursor
import uuid
import json
from datetime import datetime

DATABASE_URL = "postgresql://logs_2m50_user:iBcJOf3ULl6M4fPWyUqAlXOZ28H3eSQ9@dpg-d53qe0v5r7bs73e0b420-a.oregon-postgres.render.com/logs_2m50"

# الحقول الأساسية التي يجب أن تكون موجودة
CRITICAL_FIELDS = [
    'GlobalID', 'Name_AR', 'Name_EN', 'Category', 'Subcategory',
    'Latitude', 'Longitude', 'Phone_Number', 'District_AR', 'District_EN',
    'Review_Status', 'Company_Status'
]

# كل الحقول المتوقعة في الجدول
ALL_EXPECTED_FIELDS = [
    'GlobalID', 'Name_AR', 'Name_EN', 'Legal_Name', 'Category', 'Subcategory',
    'Category_Level_3', 'Company_Status', 'Latitude', 'Longitude', 'Google_Map_URL',
    'Building_Number', 'Floor_Number', 'Entrance_Location', 'Phone_Number',
    'Email', 'Website', 'Social_Media', 'Working_Days', 'Working_Hours',
    'Break_Time', 'Holidays', 'Menu_Barcode_URL', 'Language', 'Cuisine',
    'Payment_Methods', 'Commercial_License', 'Exterior_Photo_URL',
    'Interior_Photo_URL', 'Menu_Photo_URL', 'Video_URL', 'License_Photo_URL',
    'Additional_Photo_URLs', 'Amenities', 'District_AR', 'District_EN',
    'Delivery_Method', 'Menu', 'Drive_Thru', 'Dine_In', 'Only_Delivery',
    'Reservation', 'Require_Ticket', 'Order_from_Car', 'Pickup_Point',
    'WiFi', 'Music', 'Valet_Parking', 'Has_Parking_Lot', 'Wheelchair_Accessible',
    'Family_Seating', 'Waiting_Area', 'Private_Dining', 'Smoking_Area',
    'Children_Area', 'Shisha', 'Live_Sports', 'Is_Landmark', 'Is_Trending',
    'Large_Groups', 'Women_Prayer_Room', 'Iftar_Tent', 'Iftar_Menu',
    'Open_Suhoor', 'Free_Entry', 'Num_Menu_Photos', 'Num_Additional_Photos',
    'Confidence', 'Source', 'All_Sources', 'Importance_Score', 'QA_Score',
    'Review_Flag', 'Review_Notes', 'Review_Status',
    'flagged', 'flag_reason', 'draft_reason', 'archived_reason', 'rejected_reason',
    'last_reviewed_at', 'last_reviewed_by', 'review_version',
    'created_at', 'updated_at', 'delivery_date'
]

def print_header(title):
    print(f"\n{'='*60}")
    print(f"  {title}")
    print(f"{'='*60}")

def print_result(label, value, status=""):
    icon = "✅" if status == "pass" else "❌" if status == "fail" else "📊"
    print(f"  {icon} {label}: {value}")

def connect_db():
    """الاتصال بقاعدة البيانات"""
    try:
        conn = psycopg2.connect(DATABASE_URL)
        conn.set_client_encoding('UTF8')
        print_result("الاتصال بقاعدة البيانات", "ناجح", "pass")
        return conn
    except Exception as e:
        print_result("الاتصال بقاعدة البيانات", f"فشل: {e}", "fail")
        sys.exit(1)

def test_1_check_tables(conn):
    """فحص الجداول الموجودة"""
    print_header("1. فحص الجداول الموجودة في قاعدة البيانات")
    cur = conn.cursor()
    cur.execute("""
        SELECT table_name FROM information_schema.tables
        WHERE table_schema = 'public'
        ORDER BY table_name;
    """)
    tables = [r[0] for r in cur.fetchall()]
    print_result("الجداول الموجودة", ", ".join(tables))

    expected_tables = ['final_delivery', 'reviewers', 'poi_audit_log']
    for t in expected_tables:
        if t in tables:
            print_result(f"جدول {t}", "موجود", "pass")
        else:
            print_result(f"جدول {t}", "غير موجود!", "fail")
    cur.close()
    return tables

def test_2_check_record_counts(conn):
    """فحص عدد السجلات في كل جدول"""
    print_header("2. عدد السجلات في كل جدول")
    cur = conn.cursor()

    tables_to_check = ['final_delivery', 'reviewers', 'poi_audit_log']
    counts = {}
    for t in tables_to_check:
        try:
            cur.execute(f'SELECT COUNT(*) FROM {t};')
            count = cur.fetchone()[0]
            counts[t] = count
            print_result(f"سجلات {t}", count)
        except Exception as e:
            print_result(f"سجلات {t}", f"خطأ: {e}", "fail")
            conn.rollback()
    cur.close()
    return counts

def test_3_check_columns(conn):
    """فحص أعمدة جدول final_delivery"""
    print_header("3. فحص أعمدة جدول final_delivery")
    cur = conn.cursor()
    cur.execute("""
        SELECT column_name, data_type, is_nullable, column_default
        FROM information_schema.columns
        WHERE table_name = 'final_delivery'
        ORDER BY ordinal_position;
    """)
    columns = cur.fetchall()
    db_columns = [c[0] for c in columns]

    print_result("عدد الأعمدة في الجدول", len(db_columns))

    # فحص الأعمدة المفقودة
    missing = [f for f in ALL_EXPECTED_FIELDS if f not in db_columns]
    extra = [c for c in db_columns if c not in ALL_EXPECTED_FIELDS]

    if missing:
        print_result("أعمدة مفقودة من الجدول", ", ".join(missing), "fail")
    else:
        print_result("كل الأعمدة المتوقعة", "موجودة", "pass")

    if extra:
        print_result("أعمدة إضافية (غير متوقعة)", ", ".join(extra))

    cur.close()
    return db_columns

def test_4_check_data_quality(conn):
    """فحص جودة البيانات - الحقول الفارغة"""
    print_header("4. فحص جودة البيانات (الحقول الفارغة والناقصة)")
    cur = conn.cursor(cursor_factory=RealDictCursor)

    cur.execute('SELECT COUNT(*) as total FROM final_delivery;')
    total = cur.fetchone()['total']

    if total == 0:
        print_result("لا توجد بيانات", "الجدول فارغ - لا يمكن فحص الجودة")
        cur.close()
        return

    print_result("إجمالي السجلات", total)

    # فحص كل حقل أساسي
    for field in CRITICAL_FIELDS:
        try:
            cur.execute(f'''
                SELECT
                    COUNT(*) FILTER (WHERE "{field}" IS NULL OR "{field}" = '') as empty_count,
                    COUNT(*) as total
                FROM final_delivery;
            ''')
            result = cur.fetchone()
            empty = result['empty_count']
            pct = (empty / total * 100) if total > 0 else 0

            if empty == 0:
                print_result(f"{field}", f"مكتمل 100% ({total} سجل)", "pass")
            elif pct > 50:
                print_result(f"{field}", f"فارغ في {empty}/{total} سجل ({pct:.1f}%)", "fail")
            else:
                print_result(f"{field}", f"فارغ في {empty}/{total} سجل ({pct:.1f}%)")
        except Exception as e:
            print_result(f"{field}", f"خطأ: {e}", "fail")
            conn.rollback()

    cur.close()

def test_5_sample_records(conn):
    """عرض عينة من السجلات"""
    print_header("5. عينة من آخر 5 سجلات (للتحقق البصري)")
    cur = conn.cursor(cursor_factory=RealDictCursor)

    cur.execute('''
        SELECT "GlobalID", "Name_AR", "Name_EN", "Category", "Review_Status",
               "Latitude", "Longitude", "Phone_Number", "updated_at"
        FROM final_delivery
        ORDER BY "updated_at" DESC NULLS LAST
        LIMIT 5;
    ''')
    rows = cur.fetchall()

    if not rows:
        print_result("لا توجد سجلات", "الجدول فارغ")
        cur.close()
        return

    for i, row in enumerate(rows, 1):
        print(f"\n  --- سجل {i} ---")
        for key in ['GlobalID', 'Name_AR', 'Name_EN', 'Category', 'Review_Status',
                     'Latitude', 'Longitude', 'Phone_Number', 'updated_at']:
            val = row.get(key, 'N/A')
            print(f"    {key}: {val}")

    cur.close()

def test_6_insert_and_verify(conn):
    """اختبار إدخال سجل جديد والتحقق من حفظه بالكامل"""
    print_header("6. اختبار الإدخال والاسترجاع (أهم اختبار)")

    test_gid = '{TEST-' + str(uuid.uuid4()).upper()[:8] + '}'

    # البيانات التي سندخلها
    test_data = {
        'GlobalID': test_gid,
        'Name_AR': 'مطعم اختبار سلامة البيانات',
        'Name_EN': 'Data Integrity Test Restaurant',
        'Legal_Name': 'Test Legal Name LLC',
        'Category': 'Restaurants',
        'Subcategory': 'Fine Dining',
        'Category_Level_3': 'Arabic Cuisine',
        'Company_Status': 'Open',
        'Latitude': '24.7136',
        'Longitude': '46.6753',
        'Phone_Number': '+966501234567',
        'Email': 'test@example.com',
        'Website': 'https://test.example.com',
        'District_AR': 'العليا',
        'District_EN': 'Al Olaya',
        'Working_Days': 'السبت - الخميس',
        'Working_Hours': '09:00-23:00',
        'WiFi': 'Yes',
        'Dine_In': 'Yes',
        'Menu': 'Yes',
        'Drive_Thru': 'No',
        'Family_Seating': 'Yes',
        'Smoking_Area': 'No',
        'Review_Status': 'Draft',
        'Review_Notes': 'سجل اختبار - يجب حذفه بعد الاختبار',
    }

    cur = conn.cursor()

    # 1. إدخال السجل
    cols = []
    vals = []
    placeholders = []
    for key, value in test_data.items():
        cols.append(f'"{key}"')
        vals.append(value)
        placeholders.append('%s')

    cols.append('"created_at"')
    placeholders.append('NOW()')
    cols.append('"updated_at"')
    placeholders.append('NOW()')

    sql = f'INSERT INTO final_delivery ({", ".join(cols)}) VALUES ({", ".join(placeholders)})'

    try:
        cur.execute(sql, vals)
        conn.commit()
        print_result("إدخال سجل الاختبار", "ناجح", "pass")
    except Exception as e:
        conn.rollback()
        print_result("إدخال سجل الاختبار", f"فشل: {e}", "fail")
        cur.close()
        return False

    # 2. استرجاع السجل والتحقق
    cur = conn.cursor(cursor_factory=RealDictCursor)
    cur.execute('SELECT * FROM final_delivery WHERE "GlobalID" = %s;', (test_gid,))
    saved_row = cur.fetchone()

    if not saved_row:
        print_result("استرجاع السجل", "لم يتم العثور على السجل!", "fail")
        cur.close()
        return False

    print_result("استرجاع السجل", "تم العثور عليه", "pass")

    # 3. مقارنة كل حقل
    lost_fields = []
    corrupted_fields = []
    saved_fields = []

    for field, expected_value in test_data.items():
        actual_value = saved_row.get(field)

        if actual_value is None or actual_value == '':
            if expected_value and expected_value != '':
                lost_fields.append(field)
                print_result(f"  {field}", f"مفقود! (أدخلنا: '{expected_value}' | حُفظ: '{actual_value}')", "fail")
        elif str(actual_value).strip() != str(expected_value).strip():
            corrupted_fields.append(field)
            print_result(f"  {field}", f"تغيّر! (أدخلنا: '{expected_value}' | حُفظ: '{actual_value}')", "fail")
        else:
            saved_fields.append(field)
            print_result(f"  {field}", f"محفوظ بشكل صحيح ✓", "pass")

    # 4. ملخص
    print(f"\n  --- ملخص الإدخال والاسترجاع ---")
    print_result("حقول محفوظة بنجاح", f"{len(saved_fields)}/{len(test_data)}",
                 "pass" if len(saved_fields) == len(test_data) else "fail")

    if lost_fields:
        print_result("حقول مفقودة (فقدان بيانات!)", ", ".join(lost_fields), "fail")
    else:
        print_result("فقدان بيانات", "لا يوجد فقدان", "pass")

    if corrupted_fields:
        print_result("حقول تالفة (تغيرت القيمة)", ", ".join(corrupted_fields), "fail")
    else:
        print_result("تلف بيانات", "لا يوجد تلف", "pass")

    # 5. اختبار التحديث
    print(f"\n  --- اختبار تحديث السجل ---")
    cur2 = conn.cursor()
    new_name = 'مطعم اختبار - تم التحديث'
    new_phone = '+966509876543'
    cur2.execute('''
        UPDATE final_delivery
        SET "Name_AR" = %s, "Phone_Number" = %s, "updated_at" = NOW()
        WHERE "GlobalID" = %s
    ''', (new_name, new_phone, test_gid))
    conn.commit()

    # استرجاع بعد التحديث
    cur2 = conn.cursor(cursor_factory=RealDictCursor)
    cur2.execute('SELECT * FROM final_delivery WHERE "GlobalID" = %s;', (test_gid,))
    updated_row = cur2.fetchone()

    update_ok = True
    if updated_row['Name_AR'] == new_name:
        print_result("تحديث Name_AR", f"ناجح: '{new_name}'", "pass")
    else:
        print_result("تحديث Name_AR", f"فشل! المتوقع: '{new_name}' | الفعلي: '{updated_row['Name_AR']}'", "fail")
        update_ok = False

    if updated_row['Phone_Number'] == new_phone:
        print_result("تحديث Phone_Number", f"ناجح: '{new_phone}'", "pass")
    else:
        print_result("تحديث Phone_Number", f"فشل!", "fail")
        update_ok = False

    # تأكد أن الحقول الأخرى لم تتأثر
    unchanged_check = ['Name_EN', 'Category', 'Latitude', 'Longitude', 'Email', 'Website', 'District_EN']
    fields_affected = []
    for field in unchanged_check:
        if str(updated_row.get(field, '')).strip() != str(test_data.get(field, '')).strip():
            fields_affected.append(field)
            print_result(f"  {field} تأثر بالتحديث!",
                        f"كان: '{test_data[field]}' | الآن: '{updated_row.get(field)}'", "fail")

    if not fields_affected:
        print_result("حقول أخرى (لم تتأثر)", "سليمة", "pass")

    # 6. حذف سجل الاختبار
    cur3 = conn.cursor()
    cur3.execute('DELETE FROM final_delivery WHERE "GlobalID" = %s;', (test_gid,))
    conn.commit()
    print_result("حذف سجل الاختبار", "تم", "pass")

    cur.close()
    cur2.close()
    cur3.close()

    return len(lost_fields) == 0 and len(corrupted_fields) == 0 and update_ok

def test_7_check_reviewers(conn):
    """فحص بيانات المراجعين"""
    print_header("7. فحص بيانات المراجعين (الموظفين)")
    cur = conn.cursor(cursor_factory=RealDictCursor)

    try:
        cur.execute('SELECT id, username, display_name, role, active, created_at FROM reviewers ORDER BY id;')
        reviewers = cur.fetchall()

        if not reviewers:
            print_result("المراجعين", "لا يوجد مراجعين مسجلين!", "fail")
            cur.close()
            return

        print_result("عدد المراجعين", len(reviewers))

        for r in reviewers:
            status = "نشط" if r['active'] else "معطّل"
            print_result(f"  {r['display_name']} ({r['username']})",
                        f"الدور: {r['role']} | الحالة: {status}")
    except Exception as e:
        print_result("فحص المراجعين", f"خطأ: {e}", "fail")
        conn.rollback()

    cur.close()

def test_8_check_audit_log(conn):
    """فحص سجل التدقيق"""
    print_header("8. فحص سجل التدقيق (Audit Log)")
    cur = conn.cursor(cursor_factory=RealDictCursor)

    try:
        cur.execute('SELECT COUNT(*) as total FROM poi_audit_log;')
        total = cur.fetchone()['total']
        print_result("إجمالي سجلات التدقيق", total)

        if total > 0:
            # آخر 5 عمليات
            cur.execute('''
                SELECT reviewer, action, poi_name, field_name, created_at
                FROM poi_audit_log
                ORDER BY created_at DESC
                LIMIT 5;
            ''')
            logs = cur.fetchall()
            print("\n  آخر 5 عمليات:")
            for log in logs:
                print(f"    [{log['created_at']}] {log['reviewer']} → {log['action']} on '{log['poi_name']}' (field: {log['field_name']})")

            # إحصائيات لكل مراجع
            cur.execute('''
                SELECT reviewer, COUNT(*) as count
                FROM poi_audit_log
                GROUP BY reviewer
                ORDER BY count DESC;
            ''')
            stats = cur.fetchall()
            print("\n  عمليات لكل مراجع:")
            for s in stats:
                print_result(f"    {s['reviewer']}", f"{s['count']} عملية")
    except Exception as e:
        print_result("فحص سجل التدقيق", f"خطأ: {e}", "fail")
        conn.rollback()

    cur.close()

def test_9_review_status_distribution(conn):
    """توزيع حالات المراجعة"""
    print_header("9. توزيع حالات المراجعة")
    cur = conn.cursor(cursor_factory=RealDictCursor)

    try:
        cur.execute('''
            SELECT "Review_Status", COUNT(*) as count
            FROM final_delivery
            GROUP BY "Review_Status"
            ORDER BY count DESC;
        ''')
        statuses = cur.fetchall()

        if not statuses:
            print_result("لا توجد سجلات", "الجدول فارغ")
        else:
            for s in statuses:
                print_result(f"  {s['Review_Status'] or '(فارغ)'}", f"{s['count']} سجل")
    except Exception as e:
        print_result("توزيع الحالات", f"خطأ: {e}", "fail")
        conn.rollback()

    cur.close()

def test_10_duplicates_check(conn):
    """فحص السجلات المكررة"""
    print_header("10. فحص السجلات المكررة")
    cur = conn.cursor(cursor_factory=RealDictCursor)

    try:
        # كشف التكرار بالاسم الإنجليزي
        cur.execute('''
            SELECT "Name_EN", COUNT(*) as count
            FROM final_delivery
            WHERE "Name_EN" IS NOT NULL AND "Name_EN" != ''
            GROUP BY "Name_EN"
            HAVING COUNT(*) > 1
            ORDER BY count DESC
            LIMIT 10;
        ''')
        dups = cur.fetchall()

        if dups:
            print_result("سجلات مكررة بالاسم الإنجليزي", f"{len(dups)} اسم مكرر", "fail")
            for d in dups:
                print(f"    '{d['Name_EN']}' → {d['count']} مرات")
        else:
            print_result("تكرار بالاسم الإنجليزي", "لا يوجد تكرار", "pass")

        # كشف التكرار بالاسم العربي
        cur.execute('''
            SELECT "Name_AR", COUNT(*) as count
            FROM final_delivery
            WHERE "Name_AR" IS NOT NULL AND "Name_AR" != ''
            GROUP BY "Name_AR"
            HAVING COUNT(*) > 1
            ORDER BY count DESC
            LIMIT 10;
        ''')
        dups_ar = cur.fetchall()

        if dups_ar:
            print_result("سجلات مكررة بالاسم العربي", f"{len(dups_ar)} اسم مكرر", "fail")
            for d in dups_ar:
                print(f"    '{d['Name_AR']}' → {d['count']} مرات")
        else:
            print_result("تكرار بالاسم العربي", "لا يوجد تكرار", "pass")
    except Exception as e:
        print_result("فحص التكرار", f"خطأ: {e}", "fail")
        conn.rollback()

    cur.close()


if __name__ == '__main__':
    print("\n" + "🔍" * 30)
    print("  فحص سلامة البيانات - Media Review App")
    print("  " + datetime.now().strftime('%Y-%m-%d %H:%M:%S'))
    print("🔍" * 30)

    conn = connect_db()

    try:
        test_1_check_tables(conn)
        test_2_check_record_counts(conn)
        test_3_check_columns(conn)
        test_4_check_data_quality(conn)
        test_5_sample_records(conn)
        data_integrity_ok = test_6_insert_and_verify(conn)
        test_7_check_reviewers(conn)
        test_8_check_audit_log(conn)
        test_9_review_status_distribution(conn)
        test_10_duplicates_check(conn)

        print_header("النتيجة النهائية")
        if data_integrity_ok:
            print("  ✅ البيانات تُحفظ وتُسترجع بشكل سليم!")
            print("  ✅ لا يوجد فقدان بيانات عند الإدخال أو التحديث")
            print("  ✅ قاعدة البيانات تعمل بشكل صحيح")
        else:
            print("  ❌ يوجد مشاكل في حفظ أو استرجاع البيانات!")
            print("  ❌ راجع التفاصيل أعلاه لمعرفة الحقول المتأثرة")
    except Exception as e:
        print(f"\n  ❌ خطأ عام: {e}")
        import traceback
        traceback.print_exc()
    finally:
        conn.close()
        print(f"\n{'='*60}")
        print("  تم إغلاق الاتصال بقاعدة البيانات")
        print(f"{'='*60}\n")
