-- Run this in your Render Postgres to create the schema
-- Tables: poi (POI records + media), media_classifications (exterior/interior/menu/video etc)

CREATE TABLE IF NOT EXISTS poi (
  id SERIAL PRIMARY KEY,
  objectid INTEGER UNIQUE NOT NULL,
  globalid TEXT,
  name_ar TEXT,
  name_en TEXT,
  category TEXT,
  media JSONB DEFAULT '[]',
  data JSONB DEFAULT '{}',
  created_at TIMESTAMPTZ DEFAULT NOW(),
  updated_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS media_classifications (
  id SERIAL PRIMARY KEY,
  poi_objectid INTEGER NOT NULL REFERENCES poi(objectid) ON DELETE CASCADE,
  attachment_id INTEGER NOT NULL,
  classification_type TEXT NOT NULL,
  created_at TIMESTAMPTZ DEFAULT NOW(),
  UNIQUE(poi_objectid, attachment_id)
);

CREATE INDEX IF NOT EXISTS idx_poi_objectid ON poi(objectid);
CREATE INDEX IF NOT EXISTS idx_classifications_poi ON media_classifications(poi_objectid);
