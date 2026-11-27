import unittest
from pathlib import Path

from audit_study import audit


ROOT = Path(__file__).resolve().parents[1]


class PublishedStudyAuditTests(unittest.TestCase):
    def test_published_study_is_internally_reconciled(self):
        report = audit(ROOT)
        self.assertEqual(report["status"], "passed_with_warnings", report["errors"])
        self.assertEqual(report["summary"]["errors"], 0)
        self.assertEqual(report["summary"]["warnings"], 4)
        checks = {item["name"]: item for item in report["checks"]}
        self.assertEqual(checks["district_catalog"]["districts"], 21)
        self.assertEqual(checks["landcover_panel"]["rows"], 84)
        self.assertEqual(checks["expansion_reconciliation"]["interval_rows"], 63)
        self.assertEqual(checks["transition_matrices"]["cells"], 5103)
        self.assertEqual(checks["transition_matrices"]["reconciliation_errors"], 0)
        self.assertTrue(checks["socioeconomic_panel"]["recent_all_grade_a"])
        self.assertEqual(checks["evaluation_outputs"]["dashboard_rows"], 84)
        self.assertEqual(checks["display_boundaries"]["features"], 21)


if __name__ == "__main__":
    unittest.main()
