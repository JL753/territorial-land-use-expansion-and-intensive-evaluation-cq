"""Check public source versions; schedule this command with cron or a task runner."""
from django.core.management.base import BaseCommand

from study.data_sources import SOURCES, check_source
from study.models import DataUpdateRun


class Command(BaseCommand):
    help = "Check latest public data source versions without overwriting research data."

    def add_arguments(self, parser):
        parser.add_argument("--source", default="clcd", help="Source key or 'all'.")

    def handle(self, *args, **options):
        key = options["source"]
        keys = [item["key"] for item in SOURCES] if key == "all" else [key]
        for source_key in keys:
            try:
                result = check_source(source_key)
                status = result.get("status", "manual")
                DataUpdateRun.objects.create(
                    source_key=source_key,
                    action="check",
                    status=status,
                    version=str(result.get("version") or result.get("latest_year") or ""),
                    details=result,
                    message=result.get("message", "数据源版本检查完成。"),
                )
                self.stdout.write(self.style.SUCCESS(f"{source_key}: {status}"))
            except Exception as exc:
                DataUpdateRun.objects.create(
                    source_key=source_key, action="check", status="error",
                    message=str(exc)[:500], details={},
                )
                self.stderr.write(self.style.ERROR(f"{source_key}: {exc}"))
