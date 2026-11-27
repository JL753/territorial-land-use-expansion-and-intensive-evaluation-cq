QUERIES = {
    "/dashboard.json": """
        SELECT jsonb_agg(properties ORDER BY code, year) FROM land_use.observation
    """,
    "/districts.geojson": """
        SELECT jsonb_build_object('type', 'FeatureCollection', 'features',
           jsonb_agg(jsonb_build_object('type', 'Feature', 'geometry', ST_AsGeoJSON(geom)::jsonb,
             'properties', jsonb_build_object('code', code, 'district', name, 'group', district_group))
             ORDER BY code))
        FROM land_use.district
    """,
}


def published_data(resource):
    import psycopg

    from django.db import DatabaseError

    try:
        with psycopg.connect() as connection:
            return connection.execute(QUERIES["/" + resource]).fetchone()[0]
    except psycopg.Error as exc:
        raise DatabaseError("PostGIS snapshot unavailable") from exc
