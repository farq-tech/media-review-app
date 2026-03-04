import pg from 'pg';
const { Pool } = pg;

function getPool() {
  const conn = process.env.DATABASE_URL || process.env.External_Database_URL;
  if (!conn) throw new Error('DATABASE_URL or External_Database_URL not set');
  return new Pool({ connectionString: conn, ssl: { rejectUnauthorized: false } });
}

export default async function handler(req, res) {
  const objectid = parseInt(req.query.objectid, 10);
  if (!objectid) return res.status(400).json({ error: 'Invalid objectid' });

  if (req.method === 'PATCH') {
    try {
      const body = typeof req.body === 'string' ? JSON.parse(req.body || '{}') : req.body || {};
      const pool = getPool();
      const r = await pool.query(`
        UPDATE poi SET
          name_ar = COALESCE($2, name_ar),
          name_en = COALESCE($3, name_en),
          category = COALESCE($4, category),
          data = COALESCE(poi.data, '{}'::jsonb) || $5::jsonb,
          updated_at = NOW()
        WHERE objectid = $1
        RETURNING objectid, name_ar, name_en, category, data, updated_at
      `, [
        objectid,
        body.name_ar,
        body.name_en,
        body.category,
        JSON.stringify(body.data || {})
      ]);
      await pool.end();
      if (r.rowCount === 0) return res.status(404).json({ error: 'POI not found' });
      return res.status(200).json(r.rows[0]);
    } catch (e) {
      console.error('PATCH /api/poi/[objectid]', e);
      return res.status(500).json({ error: e.message });
    }
  }

  res.setHeader('Allow', ['PATCH']);
  return res.status(405).json({ error: 'Method not allowed' });
}
