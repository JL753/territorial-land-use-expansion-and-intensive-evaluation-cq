import hashlib
import json
from unittest.mock import patch

from django.conf import settings
from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import TestCase

from .models import Publication, RefreshRun, ResearchRelease
from .updates import load_remote_bundle, publish_research, restore_research


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
