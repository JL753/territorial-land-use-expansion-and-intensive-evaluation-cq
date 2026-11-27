import json
from tempfile import TemporaryDirectory
from pathlib import Path
from unittest.mock import patch

from django.conf import settings
from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import Client, TestCase, override_settings

from .models import District, Observation


class StudyViewsTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        call_command("import_study", verbosity=0)

    def test_data_and_report_match_published_snapshot(self):
        self.assertEqual(self.client.get("/").status_code, 200)
        self.assertEqual(self.client.get("/vendor/echarts-6.0.0.min.js").status_code, 200)
        self.assertEqual(len(self.client.get("/dashboard.json").json()), 84)
        self.assertEqual(len(self.client.get("/districts.geojson").json()["features"]), 21)
        self.assertEqual(self.client.get("/api/v1/observations/?year=2022").json()["count"], 21)
        self.assertEqual(self.client.get("/api/v1/observations/?district=500112").json()["count"], 4)
        self.assertEqual(self.client.get("/api/v1/observations/?year=bad").status_code, 400)
        self.assertEqual(self.client.get("/api/v1/analysis/").json()["counts"]["flow"], 5103)
        health = self.client.get("/healthz")
        self.assertEqual(health.status_code, 200)
        self.assertEqual(health.json(), {
            "status": "ok", "districts": 21, "observations": 84,
            "years": [2010, 2015, 2020, 2022],
        })
        row = Observation.objects.first()
        row.payload["population"] = 0
        row.save()
        self.assertEqual(self.client.get("/api/v1/analysis/").status_code, 409)

    def test_health_rejects_incomplete_panel(self):
        with patch("study.views.snapshot", side_effect=[
            {"type": "FeatureCollection", "features": [
                {"properties": {"code": f"{500100 + index:06d}"}} for index in range(21)
            ]},
            [],
        ]):
            response = self.client.get("/healthz")
        self.assertEqual(response.status_code, 503)
        self.assertEqual(response.json()["status"], "not_ready")

    def test_invalid_import_keeps_previous_records(self):
        with TemporaryDirectory() as temp:
            source = Path(temp)
            src = settings.PUBLISHED_RESULTS
            (source / "districts.geojson").write_bytes((src / "districts.geojson").read_bytes())
            rows = json.loads((src / "dashboard.json").read_bytes())
            (source / "dashboard.json").write_text(json.dumps(rows + rows[:1]))
            with self.assertRaises(CommandError):
                call_command("import_study", source=source, verbosity=0)
        self.assertEqual(District.objects.count(), 21)
        self.assertEqual(Observation.objects.count(), 84)

    @override_settings(CLCD_SERIES_PATH=Path("/tmp/shancheng-test-clcd-series-missing.json"))
    def test_clcd_series_endpoint_is_explicit_when_not_processed(self):
        response = self.client.get("/api/v1/landcover-series/")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["status"], "not_built")
        self.assertEqual(response.json()["rows"], [])

    @override_settings(OSM_OUTPUT_DIR=Path("/tmp/shancheng-test-osm-missing"))
    def test_osm_layer_endpoint_does_not_claim_missing_coverage(self):
        self.assertEqual(self.client.get("/api/v1/osm-status/").json()["status"], "not_built")
        self.assertEqual(self.client.get("/api/v1/osm-layers/buildings/500105.geojson").status_code, 404)

    @override_settings(OLLAMA_MODEL="test")
    def test_csrf_and_json_validation(self):
        browser = Client(enforce_csrf_checks=True)
        payload = {"question": "不透水面积？", "evidence": "数据范围\n研究数据"}
        self.assertEqual(browser.post("/api/interpret", payload, content_type="application/json").status_code, 403)
        browser.get("/")
        token = browser.cookies["csrftoken"].value
        with patch("study.views.choose_evidence", return_value="研究数据"):
            response = browser.post("/api/interpret", payload, content_type="application/json", HTTP_X_CSRFTOKEN=token)
        self.assertEqual(response.json(), {"answer": "研究数据"})
