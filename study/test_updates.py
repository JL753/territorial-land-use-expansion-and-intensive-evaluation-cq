import hashlib
import json
from unittest.mock import patch

from django.conf import settings
from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import TestCase

from .models import Publication, RefreshRun, ResearchRelease
from .updates import check_clcd_version, load_remote_bundle, publish_research, restore_research


class PublicationTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        call_command("import_study", verbosity=0)
        cls.geo = json.loads((settings.PUBLISHED_RESULTS / "districts.geojson").read_bytes())
        cls.rows = json.loads((settings.PUBLISHED_RESULTS / "dashboard.json").read_bytes())

    def test_add_period_rebuilds_report_and_can_restore(self):
        fixture = [{**r, "year": 2024, "transition_km2": None,
                    "source_pop": "test fixture", "source_gdp": "test fixture"}
                   for r in self.rows if r["year"] == 2022]
        updated = self.rows + fixture
        release, changed = publish_research(self.geo, updated, "test-5-periods")
        self.assertTrue(changed)
        self.assertEqual(len(release.observations), 105)
        self.assertEqual(release.report["model"]["holdout_years"], [2022, 2024])
        self.assertEqual(self.client.get("/healthz").json()["observations"], 105)
        self.assertEqual(self.client.get("/api/v1/analysis/").json()["counts"]["cover"], 105)
        self.assertEqual(self.client.get("/api/v1/research/panel/").json()["version"], str(release.pk))
        self.assertFalse(publish_research(self.geo, updated, "test-5-periods")[1])
        with self.assertRaises(ValueError):
            publish_research(self.geo, updated[:-1], "incomplete")
        self.assertEqual(Publication.objects.get(pk=1).research_id, release.pk)
        restore_research(ResearchRelease.objects.get(source="仓库基线").pk)
        self.assertEqual(self.client.get("/healthz").json()["observations"], 84)

    def test_unavailable_source_logs_failure(self):
        with patch("study.management.commands.refresh_sources.refresh_map", side_effect=OSError("connection unavailable")):
            with self.assertRaises(CommandError):
                call_command("refresh_sources", "--osm")
        self.assertEqual(RefreshRun.objects.get(feed="osm").status, "failed")
        self.assertEqual(self.client.get("/api/v1/research/panel/").json()["version"], "base")

    def test_feed_rejects_corrupted_data(self):
        geo, data = (json.dumps(value).encode() for value in (self.geo, self.rows))
        manifest = json.dumps({"schema": 1, "files": {
            name: {"path": name, "sha256": hashlib.sha256(content).hexdigest()}
            for name, content in (("districts.geojson", geo), ("dashboard.json", data))
        }}).encode()
        with patch("study.updates.download", side_effect=[manifest, geo, b"[]"]):
            with self.assertRaisesRegex(ValueError, "Checksum mismatch"):
                load_remote_bundle("https://example.org/release/manifest.json")


class PublicSourceMonitoringTests(TestCase):
    def test_clcd_metadata_exposes_available_raster_years(self):
        from io import BytesIO
        seed = {"id": 18180184, "conceptrecid": 18180180}
        latest = {
            "id": 18180185, "conceptrecid": 18180180,
            "metadata": {"title": "CLCD 1985-2025", "version": "1.0.5", "publication_date": "2026-01-01"},
            "updated": "2026-01-02T00:00:00Z",
            "links": {"html": "https://zenodo.org/records/18180185"},
            "files": [
                {"key": "CLCD_v01_2010_albert.tif", "size": 100},
                {"key": "CLCD_v01_2022_albert.tif", "size": 200},
                {"key": "CLCD_v01_2025_albert.tif", "size": 300},
                {"key": "CLCD_v01_2025_albert_province.zip", "size": 500},
            ],
        }
        with patch("study.updates.urlopen", side_effect=[
            BytesIO(json.dumps(seed).encode()), BytesIO(json.dumps({"hits": {"hits": [latest]}}).encode())
        ]):
            result = check_clcd_version()
        self.assertEqual(result["latest_year"], 2025)
        self.assertEqual(result["available_years"], [2010, 2022, 2025])
        self.assertEqual(result["total_size_bytes"], 1100)

    def test_clcd_refresh_command_records_version_check(self):
        metadata = {"version": "1.0.5", "latest_year": 2025, "available_years": [2010, 2022, 2025]}
        with patch("study.management.commands.refresh_sources.check_clcd_version", return_value=metadata):
            call_command("refresh_sources", "--clcd")
        run = RefreshRun.objects.get(feed="clcd")
        self.assertEqual(run.status, "checked")
        self.assertIn("2025", run.detail)

    def test_data_center_api_and_manual_clcd_check(self):
        from .models import RefreshRun
        catalog = self.client.get("/api/v1/data-sources/")
        self.assertEqual(catalog.status_code, 200)
        self.assertIn("clcd", {source["key"] for source in catalog.json()["sources"]})
        metadata = {"version": "1.0.5", "latest_year": 2025, "available_years": [2010, 2022, 2025]}
        with patch("study.views.check_clcd_version", return_value=metadata):
            response = self.client.post("/api/v1/data-updates/check/", data="{}", content_type="application/json")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["status"], "checked")
        self.assertEqual(RefreshRun.objects.filter(feed="clcd").count(), 1)
