import tempfile
import unittest
from pathlib import Path

import numpy as np
import pandas as pd

from evaluate import evaluate, load_panel, topsis


def sample_panel():
    rows = []
    values = {
        "500101": (100, 200, 300),
        "500102": (200, 500, 700),
        "500103": (400, 900, 1100),
    }
    for code, (population, gdp, secondary) in values.items():
        for year, scale, built in [(2010, 1.0, 10.0), (2015, 1.2, 12.0)]:
            rows.append({
                "code": code, "district": code, "year": year,
                "admin_km2": 100.0, "built_km2": built,
                "population": population * scale,
                "gdp_10k_cny": gdp * scale,
                "secondary_10k_cny": secondary * scale,
            })
    return pd.DataFrame(rows)


class EvaluationTests(unittest.TestCase):
    def test_entropy_topsis_scores_weights_and_growth_are_valid(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "panel.csv"
            sample_panel().to_csv(path, index=False)
            result, weights = evaluate(load_panel(path))
        self.assertAlmostEqual(float(weights.sum()), 1.0, places=10)
        self.assertTrue((weights >= 0).all())
        self.assertTrue(np.isfinite(result["intensive_score"]).all())
        self.assertTrue(result["intensive_score"].between(0, 1).all())
        later = result[result.year == 2015]
        self.assertTrue(np.isfinite(later["annual_growth_pct"]).all())
        self.assertTrue((later["interval_start"] == 2010).all())
        self.assertTrue((later["expansion_km2"] == 2.0).all())

    def test_constant_indicator_is_excluded_without_corrupting_weights(self):
        panel = sample_panel()
        panel["population"] = panel["built_km2"] * 50
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "panel.csv"
            panel.to_csv(path, index=False)
            result, weights = evaluate(load_panel(path))
        self.assertEqual(float(weights["population_density"]), 0.0)
        self.assertAlmostEqual(float(weights.sum()), 1.0, places=10)
        self.assertTrue(result["intensive_score"].between(0, 1).all())

    def test_topsis_respects_positive_ideal_order(self):
        frame = pd.DataFrame({"a": [0.0, 0.5, 1.0], "b": [0.0, 0.5, 1.0]})
        score = topsis(frame, 0.5)
        self.assertTrue(score.iloc[0] < score.iloc[1] < score.iloc[2])
        self.assertAlmostEqual(float(score.iloc[0]), 0.0)
        self.assertAlmostEqual(float(score.iloc[2]), 1.0)

    def test_panel_rejects_duplicate_and_incomplete_district_years(self):
        duplicate = pd.concat([sample_panel(), sample_panel().iloc[[0]]], ignore_index=True)
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "panel.csv"
            duplicate.to_csv(path, index=False)
            with self.assertRaisesRegex(ValueError, "unique"):
                load_panel(path)
            incomplete = sample_panel().query("not (code == '500103' and year == 2015)")
            incomplete.to_csv(path, index=False)
            with self.assertRaisesRegex(ValueError, "same set of years"):
                load_panel(path)

    def test_panel_rejects_non_positive_denominators(self):
        panel = sample_panel()
        panel.loc[0, "built_km2"] = 0
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "panel.csv"
            panel.to_csv(path, index=False)
            with self.assertRaisesRegex(ValueError, "built_km2"):
                load_panel(path)


if __name__ == "__main__":
    unittest.main()
