"""Build the cross-platform Python desktop application with offline data."""
from pathlib import Path
from zipfile import ZIP_DEFLATED, ZipFile

root = Path(__file__).resolve().parents[2]
target = root / "downloads/cq-land-desktop.pyz"
target.parent.mkdir(exist_ok=True)
with ZipFile(target, "w", compression=ZIP_DEFLATED) as archive:
    archive.write(Path(__file__).with_name("desktop.py"), "__main__.py")
    web = root / "web"
    for asset in sorted(web.rglob("*")):
        if asset.is_file():
            archive.write(asset, "assets/" + asset.relative_to(web).as_posix())
    for name in ("dashboard.json", "districts.geojson"):
        archive.write(root / "results/socioeconomic/four-year-exploratory" / name, "assets/" + name)
    archive.write(root / "results/analysis/report.json", "assets/analysis-report.json")
    archive.write(root / "results/socioeconomic/recent-year-comparison/district_year.csv", "assets/recent-observations.csv")
print(target.name)
