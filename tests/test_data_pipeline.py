import io
import json
import unittest

from tools.build_chongqing_osm_layers import FeatureCollectionWriter, building_properties, number
from tools.build_clcd_district_series import year_of


class SpatialDataPipelineTests(unittest.TestCase):
    def test_geojson_writer_emits_valid_empty_collection(self):
        stream = io.StringIO()
        writer = FeatureCollectionWriter(stream)
        writer.finish()
        self.assertEqual(json.loads(stream.getvalue()), {
            "type": "FeatureCollection", "features": []
        })

    def test_geojson_writer_emits_multiple_features_without_trailing_comma(self):
        stream = io.StringIO()
        writer = FeatureCollectionWriter(stream)
        writer.write({"type": "Feature", "geometry": None, "properties": {"id": 1}})
        writer.write({"type": "Feature", "geometry": None, "properties": {"id": 2}})
        writer.finish()
        result = json.loads(stream.getvalue())
        self.assertEqual([f["properties"]["id"] for f in result["features"]], [1, 2])

    def test_building_height_is_provenanced(self):
        self.assertEqual(building_properties({"height": "18 m"})["height_source"], "OSM height tag")
        estimated = building_properties({"building:levels": "5"})
        self.assertEqual(estimated["height_m"], 15.0)
        self.assertIn("estimate", estimated["height_source"])
        self.assertIn("estimate", building_properties({})["height_source"])

    def test_height_parser_rejects_unrecognized_units(self):
        self.assertIsNone(number("10 ft"))
        self.assertEqual(number("12.5 m"), 12.5)

    def test_clcd_filename_year_detection(self):
        self.assertEqual(year_of("CLCD_v01_2025_albert.tif"), 2025)
        self.assertIsNone(year_of("CLCD_classificationsystem.xlsx"))


if __name__ == "__main__":
    unittest.main()
