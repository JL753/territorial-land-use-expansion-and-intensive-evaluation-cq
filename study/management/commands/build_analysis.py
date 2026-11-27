from pathlib import Path
from tempfile import TemporaryDirectory

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError

from study.analytics import TABLES, build, sha


class Command(BaseCommand):
    help = "Rebuild the DuckDB/Parquet study mart and temporal ML report."

    def add_arguments(self, parser):
        parser.add_argument("--rasters", type=Path, help="Extracted cq_landcover/out directory; recompute from GeoTIFFs first.")
        parser.add_argument("--output", type=Path, default=settings.ANALYSIS_REPORT.parent)

    def handle(self, *args, **options):
        try:
            with TemporaryDirectory() as temp:
                publication = settings.ROOT / "results" / "landcover"
                land = publication
                if options["rasters"]:
                    from audit_landcover import analyze
                    land = Path(temp)
                    analyze(options["rasters"], land)
                    for name in TABLES.values():
                        if sha(land / name) != sha(publication / name):
                            raise ValueError(f"{name} differs from the published panel; reconcile the source first.")
                report = build(settings.ROOT, land, options["output"])
        except (OSError, ValueError) as exc:
            raise CommandError(str(exc)) from exc
        self.stdout.write(self.style.SUCCESS(f"ETL complete: {report['counts']}."))
        self.stdout.write(f"Temporal holdout MAE: {report['model']['scores']}")
