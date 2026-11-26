\set ON_ERROR_STOP on
BEGIN;
CREATE EXTENSION IF NOT EXISTS postgis;
CREATE SCHEMA IF NOT EXISTS land_use;
CREATE TABLE IF NOT EXISTS land_use.district (
    code text PRIMARY KEY CHECK (code ~ '^[0-9]{6}$'),
    name text NOT NULL,
    district_group text NOT NULL,
    geom geometry(MultiPolygon, 4326) NOT NULL CHECK (ST_IsValid(geom))
);
CREATE INDEX IF NOT EXISTS district_geom_idx ON land_use.district USING gist (geom);
CREATE TABLE IF NOT EXISTS land_use.observation (
    code text REFERENCES land_use.district,
    year integer CHECK (year IN (2010, 2015, 2020, 2022)),
    data_kind text NOT NULL CHECK (data_kind IN ('demo', 'observed')),
    properties jsonb NOT NULL,
    PRIMARY KEY (code, year)
);
CREATE TEMP TABLE import_boundaries (payload jsonb);
CREATE TEMP TABLE import_observations (payload jsonb);
-- Run from the analysis output directory, using single-line JSON exports.
\copy import_boundaries FROM 'districts.geojson' WITH (FORMAT csv, DELIMITER E'\x01', QUOTE E'\x02')
\copy import_observations FROM 'dashboard.json' WITH (FORMAT csv, DELIMITER E'\x01', QUOTE E'\x02')
TRUNCATE land_use.observation, land_use.district;
INSERT INTO land_use.district
SELECT f->'properties'->>'code', f->'properties'->>'district', f->'properties'->>'group',
       ST_Multi(ST_SetSRID(ST_GeomFromGeoJSON(f->'geometry'), 4326))
FROM import_boundaries, LATERAL jsonb_array_elements(payload->'features') AS f;
INSERT INTO land_use.observation
SELECT f->>'code', (f->>'year')::integer, f->>'data_kind', f
FROM import_observations, LATERAL jsonb_array_elements(payload) AS f;
DO $$
BEGIN
    IF (SELECT count(*) FROM land_use.district) <> 21
        OR (SELECT count(*) FROM land_use.observation) <> 84
        OR (SELECT count(DISTINCT data_kind) FROM land_use.observation) <> 1
    THEN
        RAISE EXCEPTION 'Expected 21 districts and 84 observations from one dataset';
    END IF;
END $$;
COMMIT;
