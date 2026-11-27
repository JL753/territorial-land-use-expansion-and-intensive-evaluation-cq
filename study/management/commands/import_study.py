import json
from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from study.models import District, Observation


class Command(BaseCommand):
    help = "Validate and atomically import a published district-year panel."

    def add_arguments(self, parser):
        parser.add_argument("--source", type=Path, default=settings.PUBLISHED_RESULTS)

    def handle(self, *args, **options):
        source = options["source"]
        try:
            geo = json.loads((source / "districts.geojson").read_text(encoding="utf-8"))
            rows = json.loads((source / "dashboard.json").read_text(encoding="utf-8"))
            districts = {}
            for feature in geo["features"]:
                props, geometry = feature["properties"], feature["geometry"]
                code = str(props["code"])
                if not code.isascii() or len(code) != 6 or not code.isdigit() or code in districts:
                    raise ValueError(f"Invalid or duplicate district code: {code}")
                if geometry["type"] not in {"Polygon", "MultiPolygon"} or not geometry["coordinates"]:
                    raise ValueError(f"Invalid district geometry: {code}")
                districts[code] = District(code=code, name=props["district"], region=props["group"], geometry=geometry)
            if not districts or not rows:
                raise ValueError("Empty district geometry or observations.")
            keys, years, observations = set(), set(), []
            for row in rows:
                code, year = str(row["code"]), row["year"]
                district = districts.get(code)
                key = (code, year)
                if (not district or district.name != row["district"] or district.region != row["group"]
                        or type(year) is not int or not 1900 <= year <= 2200 or key in keys):
                    raise ValueError(f"Invalid or duplicate observation: {key}")
                keys.add(key)
                years.add(year)
                observations.append(Observation(district_id=code, year=year, payload={**row, "code": code}))
            if keys != {(code, year) for code in districts for year in years}:
                raise ValueError("Incomplete district-year panel.")
        except (OSError, KeyError, ValueError, TypeError) as exc:
            raise CommandError(str(exc)) from exc

        with transaction.atomic():
            Observation.objects.all().delete()
            District.objects.all().delete()
            District.objects.bulk_create(districts.values())
            Observation.objects.bulk_create(observations)
        self.stdout.write(self.style.SUCCESS(f"Imported {len(districts)} districts and {len(observations)} observations."))
