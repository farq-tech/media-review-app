/**
 * Seed the database from POI_Surveyed_Final.csv and media_data.json
 * Run: node scripts/seed-db.js
 * Requires: DATABASE_URL or External_Database_URL
 */
const fs = require('fs');
const path = require('path');
const { Pool } = require('pg');

const ROOT = path.join(__dirname, '..');
const CSV_PATH = path.join(ROOT, 'POI_Surveyed_Final.csv');
const MEDIA_PATH = path.join(ROOT, 'media_data.json');

function parseCSVLine(line) {
  const out = [];
  let cur = '', inQ = false;
  for (let i = 0; i < line.length; i++) {
    const c = line[i];
    if (c === '"') { inQ = !inQ; continue; }
    if (!inQ && c === ',') { out.push(cur); cur = ''; continue; }
    if (c === '\\' && line[i+1] === '"') { cur += '"'; i++; continue; }
    cur += c;
  }
  out.push(cur);
  return out;
}

function parseCSV(text) {
  const lines = text.split(/\r?\n/).filter(Boolean);
  const headers = parseCSVLine(lines[0]);
  const rows = [];
  for (let i = 1; i < lines.length; i++) {
    const vals = parseCSVLine(lines[i]);
    const row = {};
    headers.forEach((h, j) => { row[h] = vals[j] || ''; });
    rows.push(row);
  }
  return rows;
}

function normalizeGuid(g) {
  if (!g) return '';
  return String(g).replace(/[{}]/g, '').toLowerCase().trim();
}

async function main() {
  const conn = process.env.DATABASE_URL || process.env.External_Database_URL;
  if (!conn) {
    console.error('Set DATABASE_URL or External_Database_URL');
    process.exit(1);
  }

  if (!fs.existsSync(CSV_PATH)) {
    console.error('POI_Surveyed_Final.csv not found at', CSV_PATH);
    process.exit(1);
  }
  if (!fs.existsSync(MEDIA_PATH)) {
    console.error('media_data.json not found at', MEDIA_PATH);
    process.exit(1);
  }

  const csvText = fs.readFileSync(CSV_PATH, 'utf8');
  const csvRows = parseCSV(csvText);
  const mediaList = JSON.parse(fs.readFileSync(MEDIA_PATH, 'utf8'));

  const byGuid = {};
  csvRows.forEach(r => {
    const g = normalizeGuid(r['GlobalID']);
    if (g) byGuid[g] = r;
  });

  const pool = new Pool({ connectionString: conn, ssl: { rejectUnauthorized: false } });

  try {
    console.log('Creating tables...');
    const sqlPath = path.join(__dirname, 'create-tables.sql');
    await pool.query(fs.readFileSync(sqlPath, 'utf8'));
  } catch (e) {
    console.log('Tables may already exist:', e.message);
  }

  const toData = (row) => {
    const d = {};
    const skip = ['ID', 'GlobalID', 'Name (AR)', 'Name (EN)', 'Category'];
    for (const [k, v] of Object.entries(row)) {
      if (skip.includes(k)) continue;
      d[k] = v;
    }
    return d;
  };

  console.log('Upserting POIs...');
  let ins = 0;
  for (const m of mediaList) {
    const g = normalizeGuid(m.globalid);
    const csvRow = byGuid[g];
    const data = csvRow ? toData(csvRow) : {};
    await pool.query(`
      INSERT INTO poi (objectid, globalid, name_ar, name_en, category, media, data, updated_at)
      VALUES ($1, $2, $3, $4, $5, $6::jsonb, $7::jsonb, NOW())
      ON CONFLICT (objectid) DO UPDATE SET
        globalid = EXCLUDED.globalid,
        name_ar = COALESCE(EXCLUDED.name_ar, poi.name_ar),
        name_en = COALESCE(EXCLUDED.name_en, poi.name_en),
        category = COALESCE(EXCLUDED.category, poi.category),
        media = EXCLUDED.media,
        data = poi.data || EXCLUDED.data,
        updated_at = NOW()
    `, [
      m.objectid,
      m.globalid,
      csvRow ? csvRow['Name (AR)'] : m.name_ar,
      csvRow ? csvRow['Name (EN)'] : m.name_en,
      csvRow ? csvRow['Category'] : m.category,
      JSON.stringify(m.media || []),
      JSON.stringify(data)
    ]);
    ins++;
    if (ins % 100 === 0) console.log('  ', ins, 'POIs');
  }

  console.log('Done. Total POIs:', ins);
  await pool.end();
}

main().catch(e => { console.error(e); process.exit(1); });
