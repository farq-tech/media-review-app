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

  if (req.method === 'GET') {
    try {
      const pool = getPool();
      const r = await pool.query(
        'SELECT attachment_id, classification_type FROM media_classifications WHERE poi_objectid = $1',
        [objectid]
      );
      await pool.end();
      const out = {};
      r.rows.forEach(row => { out[row.attachment_id] = row.classification_type; });
      res.setHeader('Cache-Control', 'no-store');
      return res.status(200).json(out);
    } catch (e) {
      console.error('GET classifications', e);
      return res.status(500).json({ error: e.message });
    }
  }

  if (req.method === 'POST' || req.method === 'PUT') {
    try {
      const body = typeof req.body === 'string' ? JSON.parse(req.body || '{}') : req.body || {};
      const classifications = body.classifications || body;
      if (typeof classifications !== 'object') return res.status(400).json({ error: 'Invalid body' });

      const pool = getPool();
      const entries = Object.entries(classifications).filter(([, v]) => v);
      for (const [attId, type] of entries) {
        await pool.query(`
          INSERT INTO media_classifications (poi_objectid, attachment_id, classification_type)
          VALUES ($1, $2, $3)
          ON CONFLICT (poi_objectid, attachment_id)
          DO UPDATE SET classification_type = $3, created_at = NOW()
        `, [objectid, parseInt(attId, 10), type]);
      }
      await pool.end();
      return res.status(200).json({ ok: true });
    } catch (e) {
      console.error('POST classifications', e);
      return res.status(500).json({ error: e.message });
    }
  }

  res.setHeader('Allow', ['GET', 'POST', 'PUT']);
  return res.status(405).json({ error: 'Method not allowed' });
}
