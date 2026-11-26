import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

import numpy as np
import pandas as pd

from demo import generate
from evaluate import evaluate, load_panel
from spatial import AREA, run


class WorkflowTest(unittest.TestCase):
    def test_end_to_end(self):
        with TemporaryDirectory() as root:
            root = Path(root)
            inputs = generate(root / "inputs")
            output = root / "results"
            run(*inputs, 8, output, "demo")
            records = pd.read_csv(output / "district_year.csv", dtype={"code": str})
            self.assertEqual(len(records), 84)
            self.assertEqual(len(json.loads((output / "districts.geojson").read_text())["features"]), 21)
            self.assertTrue(records["intensive_score"].between(0, 1).all())
            self.assertTrue(records.query("year == 2010")["expansion_km2"].isna().all())
            active = records.query("year != 2010")
            np.testing.assert_allclose(active["added_km2"] - active["lost_km2"], active["expansion_km2"])
            np.testing.assert_allclose(active["adjacent_km2"] + active["nonadjacent_km2"], active["added_km2"])
            first = records.query("code == '500103' and year == 2015").iloc[0]
            self.assertAlmostEqual(first["built_km2"], 16 * AREA)
            self.assertAlmostEqual(first["added_km2"], 8 * AREA)
            self.assertAlmostEqual(first["lost_km2"], AREA)
            self.assertAlmostEqual(first["adjacent_km2"], 6 * AREA)
            self.assertAlmostEqual(first["nonadjacent_km2"], 2 * AREA)
            _, weights = evaluate(load_panel(output / "panel.csv"))
            self.assertAlmostEqual(weights.sum(), 1)
            self.assertEqual(len(pd.read_csv(output / "association.csv")), 3)

    def test_missing_observation_is_rejected(self):
        with TemporaryDirectory() as root:
            root = Path(root)
            boundaries, stats, catalog, rasters = generate(root)
            pd.read_csv(stats).iloc[:-1].to_csv(stats, index=False)
            with self.assertRaisesRegex(ValueError, "every district"):
                run(boundaries, stats, catalog, rasters, 8, root / "results", "demo")


if __name__ == "__main__":
    unittest.main()
