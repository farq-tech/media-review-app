import pg from 'pg';
const { Pool } = pg;

function getPool() {
  const conn = process.env.DATABASE_URL || process.env.External_Database_URL;
  if (!conn) throw new Error('DATABASE_URL or External_Database_URL not set');
  return new Pool({ connectionString: conn, ssl: { rejectUnauthorized: false } });
}

export default async function handler(req, res) {
  if (req.method !== 'GET') {
    res.setHeader('Allow', ['GET']);
    return res.status(405).json({ error: 'Method not allowed' });
  }
  try {
    const pool = getPool();
    const r = await pool.query(
      'SELECT poi_objectid, attachment_id, classification_type FROM media_classifications'
    );
    await pool.end();
    const out = {};
    r.rows.forEach(row => {
      if (!out[row.poi_objectid]) out[row.poi_objectid] = {};
      out[row.poi_objectid][row.attachment_id] = row.classification_type;
    });
    res.setHeader('Cache-Control', 'no-store');
    return res.status(200).json(out);
  } catch (e) {
    console.error('GET /api/classifications', e);
    return res.status(500).json({ error: e.message });
  }
}
