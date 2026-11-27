import json
from unittest.mock import patch

from django.test import TestCase, override_settings


class ClientSurfaceTests(TestCase):
    def test_web_mobile_and_desktop_pages_are_served(self):
        for path in ("/", "/mobile.html", "/desktop.html", "/city.html", "/dashboard3d.html", "/guide.html", "/data-center.html", "/district.html"):
            with self.subTest(path=path):
                response = self.client.get(path)
                self.assertEqual(response.status_code, 200)
                self.assertIn("text/html", response["Content-Type"])

    def test_client_assets_are_allowlisted_and_served(self):
        for path in (
            "/app.js", "/style.css", "/analysis.js", "/charts.js",
            "/mobile.js", "/mobile.css", "/desktop.js", "/desktop.css",
            "/vendor/echarts-6.0.0.min.js", "/vendor/maplibre-5.16.0.js",
            "/city.js", "/city/manifest.json", "/city/cover-2022.png", "/city/buildings.geojson",
            "/dashboard3d.js", "/dashboard3d.css", "/guide.js", "/guide.css",
            "/assistant.js", "/assistant.css", "/data-center.js", "/data-center.css", "/district.js", "/district.css",
        ):
            with self.subTest(path=path):
                response = self.client.get(path)
                self.assertEqual(response.status_code, 200)
                self.assertGreater(len(b"".join(response.streaming_content)), 0)

    def test_city_snapshot_counts_and_height_evidence(self):
        def exported(name):
            response = self.client.get("/city/" + name)
            self.assertEqual(response.status_code, 200)
            return json.loads(b"".join(response.streaming_content))

        manifest = exported("manifest.json")
        buildings = exported("buildings.geojson")["features"]
        self.assertEqual(len(buildings), manifest["osm"]["buildings"])
        self.assertEqual(len(exported("poi.geojson")["features"]), manifest["osm"]["poi"])
        self.assertEqual(sum(item["properties"]["levels"] > 0 for item in buildings), 4)
        self.assertEqual(manifest["land"]["years"], [2010, 2015, 2020, 2022])

    def test_unknown_assets_are_not_served(self):
        self.assertEqual(self.client.get("/.env").status_code, 404)
        self.assertEqual(self.client.get("/not-a-real-asset.js").status_code, 404)
        self.assertEqual(self.client.get("/api/v1/data-sources/").status_code, 200)

    def test_read_only_data_endpoints_reject_mutating_methods(self):
        self.assertEqual(self.client.post("/dashboard.json").status_code, 405)
        self.assertEqual(self.client.post("/districts.geojson").status_code, 405)
        self.assertEqual(self.client.post("/api/v1/recent-observations/").status_code, 405)
        self.assertEqual(self.client.get("/api/v1/assistant/").status_code, 405)

    def test_primary_comparison_sample_is_served_separately(self):
        response = self.client.get("/api/v1/recent-observations/")
        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["count"], 42)
        self.assertEqual({row["year"] for row in payload["results"]}, {"2020", "2022"})
        self.assertTrue(all(row["quality_gdp"] == "A" for row in payload["results"]))

    @override_settings(DEBUG=False, SECURE_SSL_REDIRECT=True, SECURE_REDIRECT_EXEMPT=[r"^healthz$"])
    def test_health_probe_is_available_to_container_runtime(self):
        codes = [f"{500100 + index:06d}" for index in range(21)]
        features = {"type": "FeatureCollection", "features": [
            {"properties": {"code": code}} for code in codes
        ]}
        rows = [{"code": code, "year": year} for code in codes
                for year in (2010, 2015, 2020, 2022)]
        with patch("study.views.snapshot", side_effect=[features, rows]):
            response = self.client.get("/healthz")
        self.assertEqual(response.status_code, 200)


class AssistantAndDataSourceTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        from django.core.management import call_command
        call_command("import_study", verbosity=0)

    def test_every_page_includes_shared_assistant(self):
        for path in ("/", "/mobile.html", "/desktop.html", "/city.html", "/dashboard3d.html", "/guide.html", "/data-center.html", "/district.html"):
            response = self.client.get(path)
            self.assertEqual(response.status_code, 200)
            self.assertContains(response, "/assistant.js")
            self.assertContains(response, "/assistant.css")

    def test_assistant_returns_grounded_data_without_llm(self):
        response = self.client.post("/api/v1/assistant/", data=json.dumps({"question": "2022 年江北区不透水面面积是多少？", "context": {"path": "/district.html", "year": 2022}}), content_type="application/json")
        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["mode"], "data")
        self.assertTrue(any("江北区" in line for line in payload["evidence"]))

    def test_assistant_rejects_invalid_payload(self):
        response = self.client.post("/api/v1/assistant/", data="{}", content_type="application/json")
        self.assertEqual(response.status_code, 400)

    def test_data_source_catalog_and_version_check(self):
        from unittest.mock import patch
        from study.models import DataUpdateRun
        catalog = self.client.get("/api/v1/data-sources/")
        self.assertEqual(catalog.status_code, 200)
        self.assertIn("clcd", {item["key"] for item in catalog.json()["sources"]})
        with patch("study.views.check_source", return_value={"status": "success", "version": "1.0.5", "latest_year": 2025}):
            response = self.client.post("/api/v1/data-updates/check/", data=json.dumps({"source_keys": ["clcd"]}), content_type="application/json")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["results"][0]["status"], "success")
        self.assertEqual(DataUpdateRun.objects.count(), 1)
