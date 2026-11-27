"""Build the cross-platform Python desktop application with offline data."""
from pathlib import Path
from zipfile import ZIP_DEFLATED, ZipFile

root = Path(__file__).resolve().parents[2]
target = root / "downloads/cq-land-desktop.pyz"
target.parent.mkdir(exist_ok=True)
with ZipFile(target, "w", compression=ZIP_DEFLATED) as archive:
    archive.write(Path(__file__).with_name("desktop.py"), "__main__.py")
    for asset in sorted((root / "web").iterdir()):
        if asset.is_file():
            archive.write(asset, "assets/" + asset.name)
    for name in ("dashboard.json", "districts.geojson"):
        archive.write(root / "results/socioeconomic/four-year-exploratory" / name, "assets/" + name)
print(target.name)
