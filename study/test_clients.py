from unittest.mock import patch

from django.test import TestCase, override_settings


class ClientSurfaceTests(TestCase):
    def test_web_mobile_and_desktop_pages_are_served(self):
        for path in ("/", "/mobile.html", "/desktop.html"):
            with self.subTest(path=path):
                response = self.client.get(path)
                self.assertEqual(response.status_code, 200)
                self.assertIn("text/html", response["Content-Type"])

    def test_client_assets_are_allowlisted_and_served(self):
        for path in (
            "/app.js", "/style.css", "/analysis.js", "/charts.js",
            "/mobile.js", "/mobile.css", "/desktop.js", "/desktop.css",
            "/vendor/echarts-6.0.0.min.js",
        ):
            with self.subTest(path=path):
                response = self.client.get(path)
                self.assertEqual(response.status_code, 200)
                self.assertGreater(len(response.content), 0)

    def test_unknown_assets_are_not_served(self):
        self.assertEqual(self.client.get("/.env").status_code, 404)
        self.assertEqual(self.client.get("/not-a-real-asset.js").status_code, 404)

    def test_read_only_data_endpoints_reject_mutating_methods(self):
        self.assertEqual(self.client.post("/dashboard.json").status_code, 405)
        self.assertEqual(self.client.post("/districts.geojson").status_code, 405)

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
