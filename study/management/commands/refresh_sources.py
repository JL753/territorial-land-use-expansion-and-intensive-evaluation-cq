import json
from pathlib import Path
from time import sleep

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.db import DatabaseError
from shapely.errors import ShapelyError

from study.models import MapRelease, RefreshRun, ResearchRelease
from study.updates import load_remote_bundle, publish_research, refresh_map, restore_map, restore_research


class Command(BaseCommand):
    help = "Refresh selected sources or publish/restore a comparable study dataset."

    def add_arguments(self, parser):
        parser.add_argument("--osm", action="store_true", help="Fetch current OSM research-area geometry.")
        parser.add_argument("--bootstrap-osm", action="store_true", help="Seed the pinned open OSM snapshot.")
        parser.add_argument("--panel", action="store_true", help="Check CQ_RESEARCH_FEED_URL.")
        parser.add_argument("--bundle", type=Path, help="Publish a verified local research bundle.")
        parser.add_argument("--restore", type=int, metavar="ID", help="Restore a previously published research version.")
        parser.add_argument("--restore-map", type=int, metavar="ID", help="Restore a prior map release.")
        parser.add_argument("--interval", type=int, metavar="SECONDS", help="Poll selected network sources continuously.")

    def handle(self, *args, **options):
        selected = [k for k in ("osm", "bootstrap_osm", "panel", "bundle", "restore", "restore_map") if options[k]]
        interval = options["interval"]
        if not selected:
            raise CommandError("Select --osm, --bootstrap-osm, --panel, --bundle or --restore.")
        if interval and (interval < 900 or not set(selected) <= {"osm","panel"}):
            raise CommandError("Network polling intervals must be at least 900 seconds.")
        if "panel" in selected and not settings.RESEARCH_FEED_URL:
            raise CommandError("Set CQ_RESEARCH_FEED_URL to an approved HTTPS manifest.")
        while True:
            failed = False
            for action in selected:
                feed = "osm" if action in {"osm", "bootstrap_osm", "restore_map"} else "research"
                try:
                    if action == "restore_map":
                        release, changed = restore_map(options["restore_map"]), True
                    elif feed == "osm":
                        release, changed = refresh_map(bootstrap=action == "bootstrap_osm")
                    elif action == "restore":
                        release, changed = restore_research(options["restore"]), True
                    else:
                        if action == "bundle":
                            path = options["bundle"]
                            geo, rows = (json.loads((path/name).read_bytes()) for name in ("districts.geojson","dashboard.json"))
                            source = "local bundle: " + path.name
                        else:
                            geo, rows, source = load_remote_bundle(settings.RESEARCH_FEED_URL)
                        release, changed = publish_research(geo, rows, source)
                    state = "restored" if action in {"restore", "restore_map"} else "published" if changed else "unchanged"
                    detail = f"{action}: version {release.pk} ({release.digest[:12]})"
                except (OSError, ValueError, KeyError, TypeError, DatabaseError, ResearchRelease.DoesNotExist, MapRelease.DoesNotExist, ShapelyError) as exc:
                    failed = True
                    state = "failed"
                    detail = f"{action}: {type(exc).__name__}: {str(exc)[:320]}"
                RefreshRun.objects.create(feed=feed, status=state, detail=detail)
                if state == "failed":
                    self.stderr.write(detail)
                else:
                    self.stdout.write(detail)
            if not interval:
                if failed:
                    raise CommandError("A refresh failed. The last published snapshot remains active.")
                break
            sleep(interval)
