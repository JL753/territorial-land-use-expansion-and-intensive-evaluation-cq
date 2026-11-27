"""Write a checksummed manifest beside two reviewed research data files."""
import argparse
import hashlib
import json
from pathlib import Path


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("bundle", type=Path)
    directory = parser.parse_args().bundle
    files = {name: {"path": name, "sha256": hashlib.sha256((directory / name).read_bytes()).hexdigest()}
             for name in ("districts.geojson", "dashboard.json")}
    manifest = directory / "release-manifest.json"
    manifest.write_text(json.dumps({"schema": 1, "files": files}, indent=2) + "\n", encoding="utf-8")
    print(manifest)


if __name__ == "__main__":
    main()
