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
    const r = await pool.query(`
      SELECT objectid, globalid, name_ar, name_en, category, media, data
      FROM poi ORDER BY objectid
    `);
    await pool.end();
    const pois = r.rows.map(row => ({
      objectid: row.objectid,
      globalid: row.globalid,
      name_ar: row.name_ar,
      name_en: row.name_en,
      category: row.category,
      media: row.media || [],
      ...(row.data || {})
    }));
    res.setHeader('Cache-Control', 'no-store');
    return res.status(200).json(pois);
  } catch (e) {
    console.error('GET /api/poi', e);
    return res.status(500).json({ error: e.message });
  }
}
