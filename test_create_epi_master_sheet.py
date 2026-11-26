import unittest

import pandas as pd

from create_epi_master_sheet import build_cummulative


class CummulativeCoordinatesTest(unittest.TestCase):
    def test_coordinates_are_added_to_all_indicator_rows(self):
        names = ["Phop Phra", "Tha Song Yang", "Umphang", "Hpruso", "Unknown"]
        source = pd.DataFrame(
            [[name, 1, 2, 3, 4, 5, 6, 10, 20, 30, 40, 50] for name in names],
            columns=["Twp_MIMU", "a", "b", "c", "d", "e", "f", "v1", "v2", "v3", "v4", "v5"],
        )

        result = build_cummulative(source)
        expected = {
            "Phop Phra": "16.425721, 99.006660",
            "Tha Song Yang": "17.218119, 98.407257",
            "Umphang": "16.005041605243623, 98.90085562223892",
            "Hpruso": "19.41371920655298, 97.12808848224114",
        }
        for name, coordinates in expected.items():
            rows = result[result["Twp_MIMU"] == name]
            self.assertEqual(len(rows), 5)
            self.assertTrue(rows["Lat_Long"].eq(coordinates).all())
        self.assertTrue(result.loc[result["Twp_MIMU"] == "Unknown", "Lat_Long"].isna().all())
        self.assertEqual(len(result), 25)


if __name__ == "__main__":
    unittest.main()
