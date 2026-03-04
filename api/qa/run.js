import pg from 'pg';
const { Pool } = pg;

function getPool() {
  const conn = process.env.DATABASE_URL || process.env.External_Database_URL;
  if (!conn) throw new Error('DATABASE_URL or External_Database_URL not set');
  return new Pool({ connectionString: conn, ssl: { rejectUnauthorized: false } });
}

function isFilled(val) {
  if (val == null || val === '') return false;
  const s = String(val).trim().toUpperCase();
  return !['UNAVAILABLE', 'NAN', 'NULL', 'N/A', 'NA', 'UNAPPLICABLE'].includes(s);
}

function parseMediaUrls(str) {
  if (!str || String(str).toUpperCase() === 'UNAVAILABLE') return [];
  return String(str).split(/[\s,]+/).map(u => u.trim()).filter(u => u && !/UNAVAILABLE/i.test(u));
}

// Haversine distance in meters
function haversineM(lat1, lon1, lat2, lon2) {
  const R = 6371000;
  const dLat = (lat2 - lat1) * Math.PI / 180;
  const dLon = (lon2 - lon1) * Math.PI / 180;
  const a = Math.sin(dLat/2)**2 + Math.cos(lat1*Math.PI/180) * Math.cos(lat2*Math.PI/180) * Math.sin(dLon/2)**2;
  return 2 * R * Math.asin(Math.sqrt(a));
}

// Simple string similarity
function similarity(a, b) {
  if (!a || !b) return 0;
  a = String(a).toLowerCase(); b = String(b).toLowerCase();
  if (a === b) return 1;
  let matches = 0;
  const minLen = Math.min(a.length, b.length);
  for (let i = 0; i < minLen; i++) if (a[i] === b[i]) matches++;
  return matches / Math.max(a.length, b.length);
}

function normalizeName(s) {
  if (!s) return '';
  return String(s).replace(/[^\w\s\u0600-\u06FF]/g, '').toLowerCase().replace(/\s+/g, ' ').trim();
}

export default async function handler(req, res) {
  if (req.method !== 'GET' && req.method !== 'POST') {
    res.setHeader('Allow', ['GET', 'POST']);
    return res.status(405).json({ error: 'Method not allowed' });
  }
  try {
    let pois = [];
    if (req.method === 'POST' && req.body) {
      const body = typeof req.body === 'string' ? JSON.parse(req.body || '[]') : req.body;
      if (Array.isArray(body)) pois = body;
    }
    if (!pois.length) {
      const pool = getPool();
      const r = await pool.query('SELECT objectid, globalid, name_ar, name_en, category, media, data FROM poi ORDER BY objectid');
      await pool.end();
      pois = r.rows.map(row => ({
        objectid: row.objectid,
        globalid: row.globalid,
        name_ar: row.name_ar,
        name_en: row.name_en,
        category: row.category,
        media: row.media || [],
        ...(row.data || {})
      }));
    }
    if (!pois.length) {
      return res.status(200).json({ summary: { total: 0, pass: 0, fail: 0, accuracy: 0 }, duplicates: [], phoneErrors: [], licenseErrors: [], mediaConflicts: [], hoursErrors: [], nameErrors: [], websiteErrors: [], categoryFlags: [], byPoi: {} });
    }

    const report = {
      summary: { total: pois.length, pass: 0, fail: 0, accuracy: 0 },
      duplicates: [],
      phoneErrors: [],
      licenseErrors: [],
      mediaConflicts: [],
      hoursErrors: [],
      nameErrors: [],
      websiteErrors: [],
      categoryFlags: [],
      byPoi: {}
    };

    // Build media URLs from media array + type (exterior/interior etc) if available
    const getMediaUrls = (poi, type) => {
      const urls = [];
      const media = poi.media || [];
      if (type) {
        media.forEach(m => {
          if (m.classification === type || m.autoType === type) urls.push(m.url);
        });
      }
      const col = type === 'exterior' ? 'exterior photo URL' : type === 'interior' ? 'interior photo URL' : type === 'menu' ? 'menu photo URL' : type === 'video' ? 'video' : null;
      if (col && isFilled(poi[col])) urls.push(...parseMediaUrls(poi[col]));
      return [...new Set(urls)];
    };

    const licenseCounts = {};
    pois.forEach(p => {
      const lv = (String(p['Commercial License Number'] || '')).replace(/\D/g, '');
      if (lv.length >= 8) licenseCounts[lv] = (licenseCounts[lv] || 0) + 1;
    });
    const dupLicenses = new Set(Object.entries(licenseCounts).filter(([, c]) => c > 1).map(([k]) => k));

    let passCount = 0;
    pois.forEach((poi, idx) => {
      const oid = poi.objectid || idx;
      const errors = [];
      report.byPoi[oid] = { errors: [], warnings: [] };

      // Phone
      const phoneVal = poi['Phone Number'];
      if (isFilled(phoneVal)) {
        let s = String(phoneVal).trim();
        if (/E\+/i.test(s)) {
          try { s = String(parseInt(parseFloat(s))); } catch (e) {}
        }
        const digits = s.replace(/\D/g, '');
        const len = digits.startsWith('966') ? digits.length : (digits.length >= 9 ? digits.length + 3 : digits.length);
        if (len < 9 || len > 12) {
          errors.push('INVALID_PHONE');
          report.phoneErrors.push({ objectid: oid, name: poi.name_en, value: phoneVal });
        }
      }

      // License
      const licVal = poi['Commercial License Number'];
      if (isFilled(licVal)) {
        const s = String(licVal).trim();
        if (/E\+/i.test(s) || /[a-zA-Z]/.test(s)) {
          errors.push('INVALID_LICENSE');
          report.licenseErrors.push({ objectid: oid, error: 'INVALID_LICENSE' });
        } else {
          const digits = s.replace(/\D/g, '');
          if (digits.length !== 10) {
            errors.push('LICENSE_NOT_10_DIGITS');
            report.licenseErrors.push({ objectid: oid, error: 'LICENSE_NOT_10_DIGITS' });
          } else if (dupLicenses.has(digits)) {
            errors.push('LICENSE_DUPLICATE');
            report.licenseErrors.push({ objectid: oid, error: 'LICENSE_DUPLICATE' });
          }
        }
      }

      // Media
      const extUrls = parseMediaUrls(poi['exterior photo URL'] || '');
      const intUrls = parseMediaUrls(poi['interior photo URL'] || '');
      const allUrls = extUrls.concat(intUrls, parseMediaUrls(poi['menu photo URL'] || ''), parseMediaUrls(poi['video'] || ''));
      if (allUrls.length !== new Set(allUrls).size) {
        errors.push('DUPLICATE_MEDIA_URLS');
        report.mediaConflicts.push({ objectid: oid, error: 'DUPLICATE_MEDIA_URLS' });
      }
      const extSet = new Set(extUrls);
      const intSet = new Set(intUrls);
      if (extSet.size && intSet.size && [...extSet].some(u => intSet.has(u))) {
        errors.push('EXTERIOR_INTERIOR_SAME_URL');
        report.mediaConflicts.push({ objectid: oid, error: 'EXTERIOR_INTERIOR_SAME_URL' });
      }

      // Working hours
      const hours = poi['Working Hours for Each Day'];
      if (isFilled(hours)) {
        const m = String(hours).match(/(\d{1,2}):(\d{2})\s*-\s*(\d{1,2}):(\d{2})/);
        if (m) {
          const t1 = parseInt(m[1]) * 60 + parseInt(m[2]);
          const t2 = parseInt(m[3]) * 60 + parseInt(m[4]);
          if (t2 < t1 && t2 > 0) {
            errors.push('HOURS_OPEN_AFTER_CLOSE');
            report.hoursErrors.push({ objectid: oid, error: 'HOURS_OPEN_AFTER_CLOSE' });
          }
        }
      }

      // Name
      const nameAr = String(poi.name_ar || '');
      const nameEn = String(poi.name_en || '');
      if (/\d{9,}/.test(nameAr) || /\d{9,}/.test(nameEn)) {
        errors.push('NAME_CONTAINS_PHONE');
        report.nameErrors.push({ objectid: oid, error: 'NAME_CONTAINS_PHONE' });
      }
      if (/فرع|branch/i.test(nameAr) || /فرع|branch/i.test(nameEn)) {
        report.byPoi[oid].warnings.push('NAME_CONTAINS_BRANCH');
      }

      // Website
      const web = String(poi.Website || '').toLowerCase();
      if (isFilled(web) && (/facebook\.com|google\.com|instagram\.com|twitter\.com|maps\./i.test(web))) {
        errors.push('INVALID_WEBSITE_DOMAIN');
        report.websiteErrors.push({ objectid: oid, error: 'INVALID_WEBSITE_DOMAIN' });
      }

      // Category - restaurant check
      const cat = String(poi.category || '').toLowerCase();
      if (cat.includes('restaurant') || cat === 'commercial') {
        const hasMenu = isFilled(poi['menu photo URL']) || (poi.media || []).some(m => (m.autoType || m.classification) === 'menu');
        const hasVideo = isFilled(poi.video) || (poi.media || []).some(m => (m.autoType || m.classification) === 'video');
        const hasSeating = isFilled(poi['Has Family Seating']) || isFilled(poi['Has a Waiting Area']) || isFilled(poi['Dine In']);
        if (!hasMenu && !hasVideo && !hasSeating) {
          report.byPoi[oid].warnings.push('RESTAURANT_NO_MENU_OR_SEATING');
          report.categoryFlags.push({ objectid: oid, error: 'RESTAURANT_NO_MENU_OR_SEATING' });
        }
      }

      report.byPoi[oid].errors = errors;
      if (errors.length === 0) passCount++;
    });

    // Duplicate detection (spatial binning to limit comparisons)
    const lat = p => parseFloat(p.Latitude || p.latitude || 0);
    const lon = p => parseFloat(p.Longitude || p.longitude || 0);
    const bins = {};
    pois.forEach((p, i) => {
      const lb = Math.floor(lat(p) / 0.001), lonb = Math.floor(lon(p) / 0.001);
      const k = `${lb}_${lonb}`;
      if (!bins[k]) bins[k] = [];
      bins[k].push(i);
    });
    for (let i = 0; i < pois.length; i++) {
      const lb = Math.floor(lat(pois[i]) / 0.001), lonb = Math.floor(lon(pois[i]) / 0.001);
      const candidates = [];
      for (let db = -1; db <= 1; db++) for (let db2 = -1; db2 <= 1; db2++)
        (bins[`${lb + db}_${lonb + db2}`] || []).forEach(j => { if (j > i) candidates.push(j); });
      for (const j of candidates) {
        const a = pois[i], b = pois[j];
        const lat1 = lat(a), lon1 = lon(a), lat2 = lat(b), lon2 = lon(b);
        if (!lat1 || !lat2) continue;
        const dist = haversineM(lat1, lon1, lat2, lon2);
        const nameMatch = normalizeName(a.name_en) === normalizeName(b.name_en);
        const sim = similarity(a.name_en, b.name_en);
        const phoneMatch = isFilled(a['Phone Number']) && a['Phone Number'] === b['Phone Number'];
        let rules = 0;
        if (nameMatch && dist < 30) rules++;
        if (phoneMatch && dist < 50) rules++;
        if (sim >= 0.9 && String(a.category) === String(b.category) && dist < 40) rules++;
        if (rules >= 2) {
          report.duplicates.push({ objectid1: a.objectid, objectid2: b.objectid, name: a.name_en, dist: Math.round(dist) });
        }
      }
    }

    report.summary.total = pois.length;
    report.summary.pass = passCount;
    report.summary.fail = pois.length - passCount;
    report.summary.accuracy = pois.length ? (passCount / pois.length * 100).toFixed(1) : 0;
    report.summary.duplicatePairs = report.duplicates.length;

    res.setHeader('Cache-Control', 'no-store');
    return res.status(200).json(report);
  } catch (e) {
    console.error('QA run error:', e);
    return res.status(500).json({ error: e.message });
  }
}
