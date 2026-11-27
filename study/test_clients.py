from django.test import TestCase


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
