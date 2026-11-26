"""Serve the WebGIS from local exports or a PostGIS database."""
import argparse
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
from pathlib import Path
from urllib.parse import urlsplit

WEB = Path(__file__).resolve().parent / "web"
ASSETS = {"/": ("index.html", "text/html"), "/app.js": ("app.js", "text/javascript"),
          "/style.css": ("style.css", "text/css")}
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


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument("--results", type=Path)
    source.add_argument("--postgis", action="store_true", help="Use standard PostgreSQL PG* variables.")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8000)
    args = parser.parse_args()
    if args.postgis:
        import psycopg
        with psycopg.connect() as connection:
            if connection.execute("SELECT count(*) FROM land_use.observation").fetchone()[0] != 84:
                parser.error("Load the 84 study observations into PostGIS first.")
    elif any(not (args.results / path[1:]).is_file() for path in QUERIES):
        parser.error("Results directory must contain dashboard.json and districts.geojson.")

    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            path = urlsplit(self.path).path
            if path in ASSETS:
                filename, content_type = ASSETS[path]
                body = (WEB / filename).read_bytes()
            elif path in QUERIES:
                content_type = "application/json"
                if args.postgis:
                    try:
                        with psycopg.connect() as connection:
                            value = connection.execute(QUERIES[path]).fetchone()[0]
                        body = json.dumps(value, ensure_ascii=False).encode("utf-8")
                    except psycopg.Error:
                        self.send_error(503, "Database unavailable")
                        return
                else:
                    body = (args.results / path[1:]).read_bytes()
            else:
                self.send_error(404)
                return
            self.send_response(200)
            self.send_header("Content-Type", content_type + "; charset=utf-8")
            self.send_header("Content-Length", len(body))
            self.end_headers()
            self.wfile.write(body)

    with ThreadingHTTPServer((args.host, args.port), Handler) as server:
        server.serve_forever()


if __name__ == "__main__":
    main()
