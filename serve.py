"""Compatibility launcher for local file and PostGIS imports using Django."""
import argparse
import os
from pathlib import Path


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    source = parser.add_mutually_exclusive_group()
    source.add_argument("--results", type=Path)
    source.add_argument("--postgis", action="store_true")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8000)
    parser.add_argument("--ollama-model")
    args = parser.parse_args()
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "cqsite.settings")
    if args.results:
        for name in ("dashboard.json", "districts.geojson"):
            if not (args.results / name).is_file():
                parser.error(f"Missing {name} under {args.results}")
        os.environ["CQ_RESULTS"] = str(args.results.resolve())
    if args.postgis:
        os.environ["CQ_POSTGIS"] = "1"
    if args.ollama_model:
        os.environ["CQ_OLLAMA_MODEL"] = args.ollama_model

    from django.core.management import execute_from_command_line
    execute_from_command_line(["serve.py", "runserver", f"{args.host}:{args.port}", "--noreload"])


if __name__ == "__main__":
    main()
