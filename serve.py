"""Serve the WebGIS from local exports or a PostGIS database."""
import argparse
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
from pathlib import Path
from urllib.parse import urlsplit
from urllib.request import Request, urlopen
from urllib.error import URLError

WEB = Path(__file__).resolve().parent / "web"
ASSETS = {"/": ("index.html", "text/html"), "/app.js": ("app.js", "text/javascript"),
          "/style.css": ("style.css", "text/css")}
for filename, mime in {
    "river-ink.webp": "image/webp",
    "mobile.html": "text/html", "desktop.html": "text/html",
    "mobile.css": "text/css", "desktop.css": "text/css",
    "mobile.js": "text/javascript", "desktop.js": "text/javascript",
    "client-utils.js": "text/javascript", "mobile.webmanifest": "application/manifest+json",
    "analysis.js": "text/javascript", "manifest.webmanifest": "application/manifest+json",
    "sw.js": "text/javascript", "icon192.png": "image/png", "icon512.png": "image/png",
}.items():
    ASSETS["/" + filename] = (filename, mime)

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
    parser.add_argument("--ollama-model", help="Enable summaries with an installed local Ollama model.")
    args = parser.parse_args()
    if args.postgis:
        import psycopg
        with psycopg.connect() as connection:
            if connection.execute("SELECT count(*) FROM land_use.observation").fetchone()[0] != 84:
                parser.error("Load the 84 study observations into PostGIS first.")
    elif any(not (args.results / path[1:]).is_file() for path in QUERIES):
        parser.error("Results directory must contain dashboard.json and districts.geojson.")

    class Handler(BaseHTTPRequestHandler):
        def json_response(self, status, value):
            body = json.dumps(value, ensure_ascii=False).encode()
            self.send_response(status)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def do_POST(self):
            if self.path != "/api/interpret" or not args.ollama_model:
                self.send_error(404)
                return
            origin = urlsplit(self.headers.get("Origin", ""))
            if origin.netloc != self.headers.get("Host") or self.headers.get_content_type() != "application/json":
                self.send_error(403)
                return
            try:
                size = int(self.headers.get("Content-Length", "0"))
                if not 0 < size <= 16000:
                    raise ValueError
                payload = json.loads(self.rfile.read(size))
                question, evidence = payload["question"], payload["evidence"]
                if not isinstance(question, str) or not isinstance(evidence, str):
                    raise ValueError
            except (ValueError, TypeError, KeyError):
                self.json_response(400, {"error": "请求内容无效"})
                return
            lines = [line.strip() for line in evidence.splitlines() if line.strip()][:40]
            if not lines:
                self.json_response(400, {"error": "没有可解读的计算依据"})
                return
            request = Request("http://127.0.0.1:11434/api/chat", data=json.dumps({
                "model": args.ollama_model, "stream": False, "think": False,
                "format": {"type": "object", "properties": {"lines": {
                    "type": "array", "items": {"type": "integer", "minimum": 1, "maximum": len(lines)},
                    "minItems": 1, "maxItems": 4,
                }}, "required": ["lines"]},
                "options": {"temperature": 0, "num_predict": 96},
                "messages": [
                    {"role": "system", "content": "按用户问题从计算依据中选择最相关的行编号，返回 {\"lines\":[编号]}。保留范围与单位，最多四行。"},
                    {"role": "user", "content": question + "\n" + "\n".join(
                        f"{i}. {line}" for i, line in enumerate(lines, 1)
                    )},
                ],
            }).encode(), headers={"Content-Type": "application/json"})
            try:
                with urlopen(request, timeout=45) as response:
                    raw = json.load(response)["message"]["content"]
                chosen = json.loads(raw)["lines"]
                if not isinstance(chosen, list) or not 1 <= len(chosen) <= 4 or any(
                    type(i) is not int or not 1 <= i <= len(lines) for i in chosen
                ):
                    raise ValueError("Invalid evidence selection")
                indices = sorted({1, *chosen})
                self.json_response(200, {"answer": "\n".join(lines[i-1] for i in indices)})
            except (URLError, TimeoutError, ValueError, KeyError, TypeError, OSError):
                self.json_response(503, {"error": "请检查本机 Ollama 服务和模型名称"})

        def do_GET(self):
            path = urlsplit(self.path).path
            if path == "/api/config":
                self.json_response(200, {"model": args.ollama_model})
                return
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
